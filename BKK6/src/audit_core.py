"""Reproducible feasibility audit. No traffic-volume EDA or charts."""
from pathlib import Path
import argparse, datetime, hashlib, json, re, shutil, unicodedata
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VEHICLES = ['passenger_car','pickup_van','large_bus','small_bus','truck','tuk_tuk']
PERIODS = ['ก่อนโควิด','โควิด','หลังโควิด']
THAI_MONTHS = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.']

def normalize(value):
    if pd.isna(value): return ''
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC',str(value))).strip()

def survey_date(value):
    if pd.isna(value): return pd.NaT
    if isinstance(value,(datetime.date,datetime.datetime,pd.Timestamp)):
        return pd.Timestamp(value).normalize()
    text=normalize(value).translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))
    text=re.sub(r'\s*/\s*','/',text)
    match=re.search(r'(\d{1,2})\s*([ก-๙.]+)\s*(\d{2,4})',text)
    if match:
        day,month,year=match.groups(); year=int(year)
        if year<100: year+=2500
        if year>2400: year-=543
        try: return pd.Timestamp(year=year,month=THAI_MONTHS.index(month)+1,day=int(day))
        except ValueError: return pd.NaT
    # This workbook uses explicit day/month/year text (e.g. 29/5/2026).
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}",text):
        return pd.to_datetime(text,format="%d/%m/%Y",errors="coerce")
    # ISO dates remain supported.
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[ T].*)?',text):
        return pd.to_datetime(text,errors='coerce')
    return pd.NaT

def time_bounds(value):
    found=re.findall(r'(\d{1,2})[.:](\d{2})',normalize(value))
    if len(found)!=2: return None,None,None
    values=[int(h)*60+int(m) for h,m in found]
    if any(int(h)>23 or int(m)>59 for h,m in found) or values[1]<=values[0]:
        return None,None,None
    return f'{values[0]//60:02d}:{values[0]%60:02d}',f'{values[1]//60:02d}:{values[1]%60:02d}',(values[1]-values[0])/60

def save_csv(frame,path): frame.to_csv(path,index=False,encoding='utf-8-sig')

def matching(frame,keys):
    usable=frame.loc[frame.covid_period.isin(PERIODS)].dropna(subset=keys)
    matrix=usable.groupby(keys+['covid_period'],dropna=False).size().unstack(fill_value=0).reindex(columns=PERIODS,fill_value=0)
    complete=matrix.loc[matrix.gt(0).all(axis=1)]
    joined=usable.merge(complete.reset_index()[keys],on=keys,how='inner',validate='many_to_one')
    return matrix,complete,joined

def run_audit(source,output=None):
    source=Path(source).resolve()
    output=Path(output or ROOT/'outputs/current_audit').resolve();output.mkdir(parents=True,exist_ok=True)
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    snapshots=ROOT/'data/raw';snapshots.mkdir(parents=True,exist_ok=True)
    snapshot=snapshots/f'traffic_{source_hash[:12]}.xlsx'
    if not snapshot.exists(): shutil.copyfile(source,snapshot)
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==source_hash
    raw=pd.read_excel(snapshot,sheet_name='traffic_data')
    if raw.empty: raise ValueError('traffic_data is empty')
    if 'id' not in raw: raw.insert(0,'id',np.arange(1,len(raw)+1))
    required=['id','survey_date','Date','month','year','covid_period','intersection','road','time_period']+VEHICLES
    missing=set(required)-set(raw.columns)
    if missing: raise ValueError(f'Missing required columns: {sorted(missing)}')
    d=raw.copy();d.insert(0,'source_excel_row',np.arange(2,len(d)+2))
    d['source_sha256']=source_hash;d['source_sheet']='traffic_data'
    d['intersection_key']=d.intersection.map(normalize);d['road_key']=d.road.map(normalize)
    # Keep the supplied covid_period, including unexpected labels for the audit.
    d['report_day']=pd.to_numeric(d.Date,errors='coerce')
    d['report_month']=pd.to_numeric(d.month,errors='coerce')
    d['report_year']=pd.to_numeric(d.year,errors='coerce')
    d['report_date']=pd.to_datetime(dict(year=d.report_year,month=d.report_month,day=d.report_day),errors='coerce')
    d['survey_date_parsed']=d.survey_date.map(survey_date)
    d['survey_month']=d.survey_date_parsed.dt.month
    d['survey_year']=d.survey_date_parsed.dt.year
    d['report_quarter']=((d.report_month-1)//3+1).where(d.report_month.between(1,12))
    bounds=d.time_period.map(time_bounds)
    d[['start_time','end_time','period_hours']]=pd.DataFrame(bounds.tolist(),index=d.index)
    d['time_key']=d.start_time.fillna('')+'-'+d.end_time.fillna('')
    changes=[];numeric_profile=[]
    for col in VEHICLES:
        text=d[col].map(normalize)
        zero=d[col].isna() | text.isin(['','-'])
        cleaned=pd.to_numeric(text.str.replace(',','',regex=False).mask(zero,'0'),errors='coerce')
        d[col+'_clean']=cleaned;d[col+'_zero_assumed']=zero
        for row in d.index[zero]: changes.append({'source_excel_row':int(d.at[row,'source_excel_row']),'field':col,'original_value':d.at[row,col],'replacement':0,'reason':'user_rule_missing_or_dash_is_zero'})
        numeric_profile.append(dict(field=col,blank=int((d[col].isna()|text.eq('')).sum()),dash=int(text.eq('-').sum()),zero_assumed=int(zero.sum()),unresolved=int(cleaned.isna().sum()),negative=int(cleaned.lt(0).sum()),fractional=int((cleaned.notna()&cleaned.mod(1).ne(0)).sum())))
    numeric=d[[c+'_clean' for c in VEHICLES]]
    d['has_assumed_zero']=d[[c+'_zero_assumed' for c in VEHICLES]].any(axis=1)
    d['numeric_unresolved']=numeric.isna().any(axis=1)
    d['numeric_negative']=numeric.lt(0).any(axis=1)
    d['numeric_fractional']=(numeric.notna()&numeric.mod(1).ne(0)).any(axis=1)
    d['exact_repeat']=raw.drop(columns='id').duplicated(keep='first')
    # Repeated survey observations can appear in different reports: audit, do not silently delete.
    survey_key=['survey_date_parsed','intersection_key','road_key','time_key']
    d['repeated_survey_key']=d.survey_date_parsed.notna() & d.duplicated(survey_key,keep=False)
    report_key=['report_year','report_month','report_day','intersection_key','road_key','time_key']
    d['repeated_report_key']=d.duplicated(report_key,keep=False)
    # Distinct report and survey dates are legitimate; neither equality nor a valid report day
    # is needed to match by report month. Day validity is retained as a separate finding.
    d['candidate_eligible']=(d.covid_period.isin(PERIODS)&d.report_month.between(1,12)&d.report_year.ge(2017)&d.period_hours.notna()&d.intersection_key.ne('')&d.road_key.ne('')&~d.numeric_unresolved&~d.numeric_negative&~d.numeric_fractional&~d.exact_repeat&~d.repeated_survey_key)
    candidate=d.loc[d.candidate_eligible].copy()
    matrices={};matched={};rows={};stats=[]
    definitions=[('raw_location',d,['intersection_key','road_key']),('candidate_location',candidate,['intersection_key','road_key']),('candidate_location_time',candidate,['intersection_key','road_key','time_key']),('candidate_report_month_time',candidate,['intersection_key','road_key','report_month','time_key']),('candidate_report_quarter_time',candidate,['intersection_key','road_key','report_quarter','time_key']),('candidate_survey_month_time',candidate,['intersection_key','road_key','survey_month','time_key'])]
    for name,frame,keys in definitions:
        matrix,complete,selected=matching(frame,keys)
        matrices[name]=matrix;matched[name]=complete;rows[name]=selected
        save_csv(matrix.reset_index(),output/f'{name}_coverage.csv')
        save_csv(complete.reset_index(),output/f'{name}_matched.csv')
        save_csv(selected[['source_excel_row','covid_period','intersection','road','report_year','report_month','report_day','survey_date_parsed','time_key','has_assumed_zero']],output/f'{name}_rows.csv')
        stats.append(dict(design=name,groups=len(complete),locations=selected[['intersection_key','road_key']].drop_duplicates().shape[0],intersections=selected.intersection_key.nunique(),rows=len(selected),before_rows=int(selected.covid_period.eq(PERIODS[0]).sum()),during_rows=int(selected.covid_period.eq(PERIODS[1]).sum()),after_rows=int(selected.covid_period.eq(PERIODS[2]).sum())))
    year_rows=[]
    for year,g in d.groupby('report_year'):
        observed=sorted(int(m) for m in g.report_month.dropna().unique())
        first_y,last_y=d.report_year.min(),d.report_year.max()
        first_m=int(d.loc[d.report_year.eq(first_y),'report_month'].min());last_m=int(d.loc[d.report_year.eq(last_y),'report_month'].max())
        expected=list(range(first_m if year==first_y else 1,(last_m if year==last_y else 12)+1))
        year_rows.append(dict(report_year=int(year),rows=len(g),months_present=','.join(map(str,observed)),months_missing_within_scope=','.join(map(str,sorted(set(expected)-set(observed)))),locations=len(g[['intersection_key','road_key']].drop_duplicates()),assumed_zero_rows=int(g.has_assumed_zero.sum())))
    save_csv(pd.DataFrame(year_rows),output/'year_coverage.csv')
    save_csv(pd.DataFrame(stats),output/'matching_summary.csv')
    save_csv(pd.DataFrame(numeric_profile),output/'numeric_profile.csv')
    save_csv(pd.DataFrame(changes),output/'zero_assumption_log.csv')
    save_csv(d[['intersection','road','intersection_key','road_key']].drop_duplicates(),output/'location_normalization.csv')
    save_csv(d.loc[d.report_date.isna(),['source_excel_row','Date','month','year','survey_date']],output/'report_date_review.csv')
    save_csv(d.loc[d.numeric_unresolved|d.numeric_fractional|d.numeric_negative,['source_excel_row']+VEHICLES],output/'numeric_review.csv')
    save_csv(d.loc[d.repeated_survey_key|d.repeated_report_key|d.exact_repeat],output/'duplicate_review.csv')
    save_csv(d.groupby(['report_year','time_period','start_time','end_time','period_hours'],dropna=False).size().reset_index(name='rows'),output/'time_period_inventory.csv')
    save_csv(d,ROOT/'data/interim/traffic_audited.csv')
    save_csv(candidate,ROOT/'data/processed/traffic_candidates.csv')
    info=dict(source_filename=source.name,source_sha256=source_hash,snapshot=str(snapshot.relative_to(ROOT)),sheet='traffic_data',audited_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=len(d),columns=len(raw.columns),period_counts=d.covid_period.value_counts(dropna=False).to_dict(),unknown_period_rows=int((~d.covid_period.isin(PERIODS)).sum()),zero_assumed_cells=len(changes),zero_assumed_rows=int(d.has_assumed_zero.sum()),numeric_unresolved_rows=int(d.numeric_unresolved.sum()),numeric_fractional_rows=int(d.numeric_fractional.sum()),numeric_negative_rows=int(d.numeric_negative.sum()),exact_repeat_excess=int(d.exact_repeat.sum()),repeated_survey_key_rows=int(d.repeated_survey_key.sum()),repeated_report_key_rows=int(d.repeated_report_key.sum()),report_date_unparseable_rows=int(d.report_date.isna().sum()),survey_date_missing=int(d.survey_date.isna().sum()),survey_date_unparsed_nonblank=int((d.survey_date.notna()&d.survey_date_parsed.isna()).sum()),survey_date_min=str(d.survey_date_parsed.min()),survey_date_max=str(d.survey_date_parsed.max()),candidate_rows=len(candidate),matching=stats,year_coverage=year_rows,numeric_profile=numeric_profile)
    (output/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    assert d.covid_period.equals(raw.covid_period), 'Period labels changed'
    assert len(d)==len(raw), 'Rows dropped from audit staging'
    assert all(d.loc[d[c+'_zero_assumed'],c+'_clean'].eq(0).all() for c in VEHICLES)
    assert not candidate.numeric_unresolved.any()
    assert not candidate.repeated_survey_key.any()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,'Source changed during audit'
    return info

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output');args=parser.parse_args()
    result=run_audit(args.input,args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ['year_coverage','numeric_profile']},ensure_ascii=False,indent=2))
