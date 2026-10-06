"""V4: isolated, timestamped runs from a user-selected workbook. No old output reads."""
from pathlib import Path
import argparse,datetime,hashlib,json,html,shutil
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import audit_core as audit
PERIODS=audit.PERIODS;V=audit.VEHICLES;KEY=['intersection_key','road_key','time_key']
NAMES=['รถยนต์*','ตู้–ปิกอัพ','เมล์ใหญ่*','เมล์เล็ก','บรรทุก','สามล้อ']
EN=['Cars incl. taxis','Pickup/van','Large bus/coach','Small bus','Truck','Tuk-tuk']
PACKAGE=Path(__file__).resolve().parents[1]

def tab(d):
 d=d.round(3).fillna('—');return '\n'.join(['| '+' | '.join(map(str,d.columns))+' |','| '+' | '.join(['---']*len(d.columns))+' |']+['| '+' | '.join(str(x).replace('|','/') for x in r)+' |' for r in d.values])
def pair(d,keys):
 _,_,m=audit.matching(d,keys)
 w=m.groupby(keys+['covid_period']).vph.median().unstack().reindex(columns=PERIODS)
 return m,w,w.div(w[PERIODS[0]].where(w[PERIODS[0]]>0),axis=0)*100

def run(source,output_parent=None):
 source=Path(source).resolve();sha=hashlib.sha256(source.read_bytes()).hexdigest()
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
 out=Path(output_parent or PACKAGE/'runs')/(stamp+'_'+sha[:10]);out.mkdir(parents=True,exist_ok=False)
 for p in ['data/interim','data/processed','figures','tables']:(out/p).mkdir(parents=True,exist_ok=True)
 audit.ROOT=out;info=audit.run_audit(source)
 d=pd.read_csv(out/'data/processed/traffic_candidates.csv',low_memory=False)
 # Actual survey dates are required for V4's comparisons. Keep all rejected rows in the audit.
 rejected=d[d.survey_date_parsed.isna()|d.survey_year.lt(2017)].copy();rejected.to_csv(out/'tables/survey_date_exclusions.csv',index=False,encoding='utf-8-sig')
 d=d[d.survey_date_parsed.notna()&d.survey_year.ge(2017)].copy()
 d['total']=d[[v+'_clean' for v in V]].sum(axis=1);d['vph']=d.total/d.period_hours
 m,w,idx=pair(d,KEY)
 gate=f"# Data Feasibility / Matching Audit\n\nSource SHA256: {sha}\n\nRaw rows: {info['rows']}; usable rows: {len(d)}; matched rows: {len(m)}; units: {len(w)}.\n\nUnknown covid_period rows: {info['unknown_period_rows']}. Extra V4 survey-date exclusions: {len(rejected)}.\n\n"+tab(pd.read_csv(out/'outputs/current_audit/matching_summary.csv'))
 (out/'AUDIT.md').write_text(gate,encoding='utf-8')
 if info['unknown_period_rows'] or w.empty or not w[PERIODS[0]].gt(0).any():
  (out/'STATUS.json').write_text(json.dumps({'status':'audit_only','reason':'Unknown period labels or no positive-baseline complete matched units','source_sha256':sha}),encoding='utf-8');return out
 fontnames={f.name for f in font_manager.fontManager.ttflist};thai='Tahoma' in fontnames
 plt.rcParams.update({'font.family':'Tahoma' if thai else 'DejaVu Sans','axes.unicode_minus':False,'font.size':10})
 notes=[];charts=[]
 def csv(frame,name):frame.to_csv(out/'tables'/name,index=False,encoding='utf-8-sig')
 def finish(fig,name,title,read,interpret,limit,speech):
  fig.tight_layout(rect=(0,.04,1,.93));fig.savefig(out/'figures'/name,dpi=150);plt.close(fig)
  charts.append({'image':name,'title':title,'read':read,'finding':interpret,'limit':limit,'speech':speech})
 # 1: report coverage, not traffic volume.
 raw=pd.read_csv(out/'data/interim/traffic_audited.csv',low_memory=False)
 cov=raw.groupby(['report_year','report_month']).size().unstack().reindex(columns=range(1,13)).fillna(0);csv(cov.reset_index(),'coverage.csv')
 fig,ax=plt.subplots(figsize=(10,5));im=ax.imshow(cov,aspect='auto',cmap='Blues');ax.set_yticks(range(len(cov)),cov.index.astype(int));ax.set_xticks(range(12),range(1,13));ax.set_xlabel('Report month');ax.set_ylabel('Report year');fig.colorbar(im,ax=ax,label='Rows in workbook');ax.set_title('1. Coverage is uneven: rows are observations, not vehicles')
 finish(fig,'01_coverage.png','1. ขอบเขตข้อมูลก่อนตีความ','สีคือจำนวนแถวในเดือนรายงาน ไม่ใช่จำนวนรถ',f"ไฟล์มี {len(raw):,} แถว; ผ่านเกณฑ์ V4 {len(d):,} แถว; จับคู่หลัก {len(m):,} แถว / {len(w):,} หน่วย",'ช่องศูนย์หมายถึงไม่มีรายการในไฟล์ ไม่ใช่ไม่มีรถ; ขอบเขตที่ตรวจไม่รับรองว่าเป็นทุกเดือนที่หน่วยงานมี','เริ่มจากตรวจว่าเรามีข้อมูลจุดไหนและเมื่อไร แล้วเปรียบเทียบเฉพาะหน่วยเดียวกัน')
 # 2: overview distribution; explicitly conditional cluster bootstrap.
 positive=idx.dropna();clusters=positive.index.get_level_values('intersection_key').unique();rng=np.random.default_rng(5001);arrays=[positive.xs(c,level='intersection_key').values for c in clusters]
 reps=np.array([np.median(np.concatenate([arrays[i] for i in rng.integers(0,len(arrays),len(arrays))]),axis=0) for _ in range(1000)])
 med=positive.median();lo,hi=np.percentile(reps,[2.5,97.5],axis=0);summary=pd.DataFrame({'period':PERIODS,'median_index':med.values,'p025':lo,'p975':hi,'units':len(positive)});csv(summary,'overview.csv')
 fig,ax=plt.subplots(figsize=(9,4));ax.errorbar(med.values,[2,1,0],xerr=[med.values-lo,hi-med.values],fmt='o',capsize=6);ax.set_yticks([2,1,0],['Before','During','After']);ax.set_ylim(-.5,2.5);ax.axvline(100,color='gray',ls='--');ax.set_xlabel('Index; Before = 100');ax.set_title(f'2. Matched-unit indices (n={len(positive)}; clusters={len(clusters)})')
 for j,x in enumerate(med.values):ax.annotate(f'{x:.1f}',(x,2-j),xytext=(0,12),textcoords='offset points',ha='center')
 statement=f'During={med.iloc[1]:.1f}; After={med.iloc[2]:.1f}; Before=100'
 finish(fig,'02_overview.png','2. ภาพรวมของชุดที่จับคู่ได้','จุดคือมัธยฐานดัชนี เส้นคือ percentile 95% จาก cluster bootstrap 1,000 รอบ seed 5001; Before=100 ตามนิยาม ไม่ใช่ไม่มีความผิดการวัด',statement,'ไม่ใช่ผลเชิงสาเหตุ; bootstrap ไม่รวม selection bias และความผิดต้นทาง ไม่ได้ทดสอบ After–During โดยตรง',statement+' เป็นภาพรวมของตัวอย่าง ไม่ใช่รถทั้งหมดในกรุงเทพฯ')
 # 3: eligible morning locations; rank by absolute change, not cherry-picked narrative.
 am=d[d.time_key.eq('07:00-09:00')];am_m,aw,ai=pair(am,KEY[:2]);counts=am_m.groupby(KEY[:2]+['covid_period']).size().unstack().reindex(columns=PERIODS)
 eligible=aw[(counts>=2).all(axis=1)&aw[PERIODS[0]].gt(0)].copy();ei=eligible.div(eligible[PERIODS[0]],axis=0)*100
 top=ei.reindex((ei[PERIODS[2]]-100).abs().sort_values(ascending=False).index).head(12);lookup=top.reset_index();lookup.insert(0,'code',[f'L{x+1:02}' for x in range(len(top))]);csv(lookup,'location_lookup.csv')
 if len(top):
  fig,ax=plt.subplots(figsize=(10,max(4,len(top)*.35)));im=ax.imshow(top.values,aspect='auto',cmap='RdBu_r',vmin=0,vmax=200);ax.set_yticks(range(len(top)),[' / '.join(k) if thai else lookup.code.iloc[i] for i,k in enumerate(top.index)]);ax.set_xticks(range(3),['Before','During','After']);fig.colorbar(im,ax=ax,label='Index (colors clipped at 200)');ax.set_title(f'3. Largest absolute changes: {len(top)} of {len(ei)} eligible morning locations')
  for i,row in enumerate(top.values):
   for j,x in enumerate(row):ax.text(j,i,f'{x:.1f}',ha='center',va='center',fontsize=8)
  finish(fig,'03_locations.png','3. แต่ละสถานที่เปลี่ยนเหมือนกันหรือไม่','แต่ละแถวคือทางแยก–ถนน Before ของแต่ละแห่ง=100',f'มี {len(ei)} คู่เช้าที่สำรวจอย่างน้อยสองรายการทุกช่วง แสดง {len(top)} คู่ที่ผล After ต่างจาก 100 มากที่สุด','ตั้งใจเลือกผลต่างสูง จึงไม่ใช้ภาพนี้เป็นตัวแทนการกระจายทั้งเมือง; ปฏิทินไม่จำเป็นต้องตรงกัน','ดัชนีเปรียบเทียบกับฐานของแต่ละสถานที่ ไม่ใช่อันดับจำนวนรถ')
 else:notes.append('ไม่สร้างกราฟ 3: ไม่มีคู่เช้าที่มีอย่างน้อยสองรายการครบสามช่วง')
 # 4: preferred case identities retained only if eligible; no automatic replacement with different story.
 selected=[k for k in [('บางขุนนนท์','จรัญสนิทวงศ์'),('หลักสี่','แจ้งวัฒนะ'),('หลักสี่','กำแพงเพชร 6')] if k in eligible.index]
 notes.append('กรณีศึกษาผ่านการจับคู่ชื่อเดิมแบบตรงตัว '+str(len(selected))+' คู่; หากชื่อเปลี่ยนจะไม่รวมแบบ fuzzy โดยอัตโนมัติ ดู location_lookup.csv')
 case_records=[];parts=[];date_rows=[]
 for k in selected:
  g=am_m[(am_m.intersection_key==k[0])&(am_m.road_key==k[1])].copy();dt=pd.to_datetime(g.survey_date_parsed);g['survey_month_actual']=dt.dt.month
  sets=[set(g[g.covid_period.eq(p)].survey_month_actual) for p in PERIODS];common=sorted(set.intersection(*sets));n=g.groupby('covid_period').size();v=eligible.loc[k];no_latest=g[~(g.covid_period.eq(PERIODS[2])&dt.dt.year.eq(pd.to_datetime(d.survey_date_parsed).dt.year.max()))]
  minus=no_latest[no_latest.covid_period.eq(PERIODS[2])].vph.median()
  case_records.append({'intersection':k[0],'road':k[1],'before_n':n.iloc[0] if False else n[PERIODS[0]],'during_n':n[PERIODS[1]],'after_n':n[PERIODS[2]],'change_pct':(v[PERIODS[2]]/v[PERIODS[0]]-1)*100,'common_months':str(common),'zero_assumed_rows':int(g.has_assumed_zero.sum()),'after_excluding_latest_survey_year_change_pct':(minus/v[PERIODS[0]]-1)*100})
  for vehicle in V:
   b=(g[g.covid_period.eq(PERIODS[0])][vehicle+'_clean']/g[g.covid_period.eq(PERIODS[0])].period_hours).mean();a=(g[g.covid_period.eq(PERIODS[2])][vehicle+'_clean']/g[g.covid_period.eq(PERIODS[2])].period_hours).mean();parts.append({'intersection':k[0],'road':k[1],'vehicle':vehicle,'difference':a-b})
  date_rows.append(g)
 case=pd.DataFrame(case_records);csv(case,'case_audit.csv');parts=pd.DataFrame(parts);csv(parts,'case_components.csv')
 if selected:
  allcase=pd.concat(date_rows);csv(allcase[['intersection_key','road_key','covid_period','survey_date_parsed','report_date','vph','has_assumed_zero','source_excel_row']],'case_dates.csv')
  caselevels=[];fig,axs=plt.subplots(1,len(selected),figsize=(5*len(selected),6),sharex=True,squeeze=False)
  for i,k in enumerate(selected):
   ax=axs[0,i];g=allcase[(allcase.intersection_key==k[0])&(allcase.road_key==k[1])];yy=np.arange(len(V))
   for j,period in enumerate(PERIODS):
    q=g[g.covid_period.eq(period)];vals=[(q[v+'_clean']/q.period_hours).mean() for v in V]
    ax.barh(yy+(j-1)*.24,vals,height=.22,label=['Before','During','After'][j])
    for v,x in zip(V,vals):caselevels.append({'intersection':k[0],'road':k[1],'period':period,'vehicle':v,'mean_vph':x,'n':len(q)})
   ax.set_yticks(yy,NAMES if thai else EN);ax.invert_yaxis();ax.set_xlabel('Mean vehicles/hour');ax.set_title(' / '.join(k) if thai else f'Case {i+1}');ax.legend(fontsize=8)
  csv(pd.DataFrame(caselevels),'case_vehicle_three_periods.csv')
  finish(fig,'04_components.png','4. ประเภทรถในกรณีศึกษาที่ผ่านเกณฑ์ ครบสามช่วง','แต่ละประเภทรถมีสามแท่ง Before / During / After ใช้ค่าเฉลี่ยคันต่อชั่วโมง', '; '.join(f"{r['intersection']}/{r['road']} รถรวมเปลี่ยนมัธยฐาน After เทียบ Before {r['change_pct']:+.1f}%" for r in case_records),'กราฟใช้ค่าเฉลี่ย ส่วนเปอร์เซ็นต์ในข้อความใช้มัธยฐาน; รถยนต์รวมแท็กซี่ ไม่ใช่หลักฐานสาเหตุ','เปรียบเทียบทั้งสามแท่งในหมวดเดียวกันก่อนดูว่าประเภทใดเปลี่ยนสวนทางกัน')
 else:notes.append('ไม่สร้างกราฟ 4: กรณีศึกษาที่กำหนดไม่ผ่านเกณฑ์ ไม่ใช้ผลเก่าแทน')
 # 5: shares, equal unit weights only when positive totals exist in every period.
 sh=m[m.total.gt(0)].copy()
 for v in V:sh[v]=sh[v+'_clean']/sh.total*100
 u=sh.groupby(KEY+['covid_period'])[V].mean();wide=u.unstack('covid_period');complete=wide.dropna();mix=pd.DataFrame({p:complete.xs(p,axis=1,level=1).mean() for p in PERIODS});mix['change_pp']=mix[PERIODS[2]]-mix[PERIODS[0]];csv(mix.reset_index(names='vehicle'),'mix_change.csv')
 if len(complete):
  fig,ax=plt.subplots(figsize=(10,5));yy=np.arange(len(V))
  for j,pdname in enumerate(PERIODS):ax.barh(yy+(j-1)*.24,mix[pdname],height=.22,label=['Before','During','After'][j])
  ax.set_yticks(yy,NAMES if thai else EN);ax.invert_yaxis();ax.legend();ax.set_xlabel('Mean vehicle share (%)');ax.set_title(f'5. Vehicle composition across all three periods (n={len(complete)})')
  finish(fig,'05_mix.png','5. องค์ประกอบรถ Before–During–After','สัดส่วนรายรายการ → เฉลี่ยในหน่วย–ช่วง → เฉลี่ยข้ามหน่วยร่วม; แสดงสามช่วงในทุกหมวด',f"หมวดรถยนต์ Before={mix.loc['passenger_car',PERIODS[0]]:.2f}%, During={mix.loc['passenger_car',PERIODS[1]]:.2f}%, After={mix.loc['passenger_car',PERIODS[2]]:.2f}% จาก {len(complete)} หน่วย",'สัดส่วนเพิ่มไม่เท่ากับจำนวนเพิ่ม; หกหมวดไม่ใช่ทุกยานพาหนะและไม่ใช่ผู้โดยสาร','ดูว่าช่วง During และ After ต่างจาก Before อย่างไร ไม่ตีความเป็นการเปลี่ยนไปใช้รถส่วนตัว')
 # 6: sensitivity automatically recomputed; zero removal shown in table on same retained keys.
 sensitivity=[]
 for label,keys in [('Same location/time',KEY),('Same report quarter',KEY+['report_quarter']),('Same survey month',KEY+['survey_month'])]:
  mm,ww,ii=pair(d,keys);vals=ii.median();sensitivity.append({'design':label,'units':len(ww),'During':vals.get(PERIODS[1],np.nan),'After':vals.get(PERIODS[2],np.nan)})
 ss=pd.DataFrame(sensitivity);csv(ss,'sensitivity.csv');fig,ax=plt.subplots(figsize=(10,4.8));yy=np.arange(len(ss))
 for delta,p in [(-.1,'During'),(.1,'After')]:ax.scatter(ss[p],yy+delta,label=p,s=55)
 ax.set_yticks(yy,[f'{r.design} (n={r.units})' for r in ss.itertuples()]);ax.invert_yaxis();ax.axvline(100,color='gray',ls='--');ax.legend();ax.set_xlabel('Median paired index; Before = 100');ax.set_title('6. Matching conditions change both sample and estimates')
 finish(fig,'06_sensitivity.png','6. ข้อสรุปไวต่อเงื่อนไขหรือไม่','แต่ละแถวเป็นวิธีจับคู่ต่างกัน จำนวนหน่วยแสดงข้างชื่อ', '; '.join(f'{r.design}: n={r.units}, During={r.During:.1f}, After={r.After:.1f}' for r in ss.itertuples()),'สมาชิกเปลี่ยนเมื่อเพิ่มเงื่อนไข จึงไม่ใช่การทดลองเปลี่ยนเงื่อนไขบนกลุ่มเดิมทั้งหมด','ไม่เลือกเฉพาะวิธีที่ให้เรื่องราวสวย ต้องรายงานว่าทิศทางเทียบฐานและ After เทียบ During สอดคล้องหรือเปลี่ยนไปอย่างไร')
 cm,cw,ci=pair(d[~d.has_assumed_zero],KEY)
 restricted=d.merge(cw.reset_index()[KEY],on=KEY,how='inner');rm,rw,ri=pair(restricted,KEY)
 zero=pd.DataFrame([{'design':'original rows on complete-case units','units':len(rw),'During':ri[PERIODS[1]].median(),'After':ri[PERIODS[2]].median()},{'design':'complete numeric rows only','units':len(cw),'During':ci[PERIODS[1]].median(),'After':ci[PERIODS[2]].median()}]);csv(zero,'zero_sensitivity.csv')
 # 7: supplied Lockdown flags, during only. Reference windows are a separate sensitivity definition.
 flag_notes=[];lock_summary=[]
 raw_flags_present=all(x in raw.columns for x in ['Lockdown','Not Lockdown'])
 if raw_flags_present:
  flags=raw[['Lockdown','Not Lockdown']].apply(pd.to_numeric,errors='coerce');valid=flags.isin([0,1]).all(axis=1)&flags.sum(axis=1).eq(1)
  csv(raw.loc[~valid],'invalid_lockdown_flags.csv')
  raw_dt=pd.to_datetime(raw.survey_date_parsed,errors='coerce');reference=(raw_dt.between('2020-03-22','2020-04-12')|raw_dt.between('2021-07-12','2021-09-30'))
  mismatch=valid&raw_dt.notna()&flags.Lockdown.ne(reference.astype(int));review=raw.loc[mismatch,['source_excel_row','survey_date_parsed','report_date','Lockdown','Not Lockdown','intersection','road']].copy();review['reference_flag']=reference[mismatch].astype(int);csv(review,'lockdown_date_review.csv')
  flag_notes.append(f'Flag ในไฟล์ต่างจากกรอบวันที่อ้างอิง {int(mismatch.sum())} แถว; invalid binary/complement {int((~valid).sum())} แถว')
  if valid.all():
   ld=d[d.covid_period.eq(PERIODS[1])].copy();t=pd.to_datetime(ld.survey_date_parsed);ld['reference_flag']=(t.between('2020-03-22','2020-04-12')|t.between('2021-07-12','2021-09-30')).astype(int)
   main=None
   for label,field,keys in [('Supplied flags','Lockdown',KEY),('Reference windows','reference_flag',KEY),('Supplied + same month','Lockdown',KEY+['survey_month'])]:
    counts=ld.groupby(keys+[field]).size().unstack(fill_value=0).reindex(columns=[0,1],fill_value=0);keys_ok=counts[counts.gt(0).all(axis=1)].reset_index()[keys];matched=ld.merge(keys_ok,on=keys,how='inner');wide_ld=matched.groupby(keys+[field]).vph.median().unstack().reindex(columns=[0,1]);good=wide_ld[0].gt(0);indices=wide_ld.loc[good,1]/wide_ld.loc[good,0]*100
    lock_summary.append({'design':label,'units':len(wide_ld),'positive_baseline_units':int(good.sum()),'rows':len(matched),'median_index':indices.median(),'lockdown_rows':int(matched[field].eq(1).sum()),'not_lockdown_rows':int(matched[field].eq(0).sum())})
    csv(wide_ld.reset_index(),label.replace(' ','_').replace('+','and')+'_lockdown_units.csv')
    if field=='Lockdown' and keys==KEY:main=wide_ld;csv(matched[['source_excel_row','survey_date_parsed','intersection_key','road_key','time_key','Lockdown','vph']],'lockdown_matched_rows.csv')
   ls=pd.DataFrame(lock_summary);csv(ls,'lockdown_summary.csv')
   if main is not None and len(main):
    fig,axs=plt.subplots(1,2,figsize=(12,5));ax=axs[0];ax.scatter(main[0],main[1],s=24,alpha=.6);limit=max(main.max().max()*1.05,1);ax.plot([0,limit],[0,limit],ls='--',color='gray');ax.set_xlim(0,limit);ax.set_ylim(0,limit);ax.set_xlabel('Not Lockdown: median vehicles/hour');ax.set_ylabel('Lockdown: median vehicles/hour');ax.set_title(f'During only; matched units={len(main)}');ax=axs[1];ax.scatter(ls.median_index,np.arange(len(ls)),s=65);ax.set_yticks(range(len(ls)),[f'{r.design} (n={r.units})' for r in ls.itertuples()]);ax.axvline(100,color='gray',ls='--');ax.set_xlabel('Index: Not Lockdown = 100');ax.set_title('Definition / month sensitivity');ax.set_ylim(-.45,len(ls)-.35)
    for i,x in enumerate(ls.median_index):
     if np.isfinite(x):ax.annotate(f'{x:.1f}',(x,i),xytext=(0,10),textcoords='offset points',ha='center')
    finish(fig,'07_lockdown.png','7. Lockdown เทียบ Not Lockdown ภายใน During','ซ้าย: หน่วยเดิมเวลาเดิม จุดใต้เส้นมีค่า Lockdown ต่ำกว่า; ขวา: ดัชนีมัธยฐานเทียบ Not Lockdown=100',f"ตาม flag ผู้ใช้ จับคู่ {len(main)} หน่วย {lock_summary[0]['rows']} แถว ดัชนี={lock_summary[0]['median_index']:.1f}; "+flag_notes[0],'flag ยังมีแถวต่างจากกรอบวันที่; reference windows เป็นการทดสอบนิยาม ไม่ใช่การแก้ต้นฉบับหรือรับรองทุกช่วงมาตรการ จำนวนคู่ลดมากเมื่อคุมเดือน','นี่เป็นความสัมพันธ์ในชุดสำรวจปีโควิด ไม่ใช่ผลเชิงสาเหตุของ Lockdown; ไม่รวม Before/After เป็นกลุ่ม Not Lockdown')
   else:flag_notes.append('จับคู่ Lockdown ไม่ได้: ไม่สร้างกราฟ ไม่ใช้คนละสถานที่แทน')
  else:flag_notes.append('ไม่สร้างกราฟ Lockdown เพราะพบ flag ไม่ใช่ 0/1 หรือไม่เป็นค่าตรงข้าม')
 else:flag_notes.append('ไม่มีสองคอลัมน์ Lockdown: วิเคราะห์สามช่วงได้ แต่ไม่สร้างกราฟ Lockdown')
 notes.extend(flag_notes)
 source_note='ข้อมูลรุ่นนี้ยังเป็นฉบับร่าง: เคยพบแถว Excel 704 (มิตรไมตรี) หมวดบรรทุก/สามล้อไม่ตรง PDF ต้นทาง ยังไม่ได้แก้ในผลภาพรวมและ heatmap จึงต้องทวนก่อนส่งจริง' if sha=='6e1b556f353c66fec5c8a664f3e1e5b5e52e5a756f75c2ae28562c5c0fa6118b' else 'ข้อมูลไฟล์รุ่นใหม่: audit นี้ไม่ใช่การรับรองความตรงกับ PDF ต้องตรวจต้นทางแยก'
 header=f"# Bangkok Traffic V4 — ปริมาณรถและความต่างรายสถานที่\n\n{source_note}\n\nข้อมูลจาก `{source.name}` ชีต traffic_data | SHA256 `{sha}`\n\nวันสำรวจที่ผ่านเกณฑ์ {d.survey_date_parsed.min()} ถึง {d.survey_date_parsed.max()} | ชื่อช่วงใช้ covid_period จากไฟล์ ไม่จัดใหม่จากปี\n\n## ผลสำคัญ\n\n{statement}; กลุ่มหลัก {len(w)} หน่วย กรณีศึกษาที่ผ่านเกณฑ์ {len(selected)} คู่ ทุกผลคำนวณใหม่จากไฟล์นี้ ไม่อ่านผล V1/V2\n\n## ที่มาและวิธี\n\n[สำนักการจราจรและขนส่ง](https://traffic.bangkok.go.th/re_intersection/intersection/intersection.html) เผยแพร่ผลสำรวจจุดทางแยก ไม่ใช่ข้อมูลต่อเนื่องทุกวัน เป้าหมายคือเปรียบเทียบหน่วยเดียวกัน ดูความต่างพื้นที่ และองค์ประกอบรถ\n\nคัน/ชั่วโมง = ผลรวมรถหกหมวด / ชั่วโมงสำรวจ; ใช้มัธยฐานภายในหน่วย–ช่วง ก่อนหารฐาน Before ของหน่วยเดียวกัน; Before=0 ไม่สร้างดัชนี ไม่ลบปีล่าสุดจากผลหลัก ไม่อ้างเป็นยอดเต็มปี ค่าว่าง/ขีดแทนศูนย์ตามข้อตกลง ไม่เติมวันหรือจุดสำรวจที่ไม่มี\n\nV4 เพิ่มเงื่อนไขวันที่สำรวจต้องแปลได้และปีสำรวจ>=2017 จึงอาจต่างจากรุ่นเก่า ดู [audit](AUDIT.md) และ [รายการตัดออก](tables/survey_date_exclusions.csv)\n"
 text=header
 for c in charts:text+=f"\n## {c['title']}\n\n![{c['title']}](figures/{c['image']})\n\n**อ่านอย่างไร:** {c['read']}\n\n**ผลรอบนี้:** {c['finding']}\n\n**ข้อจำกัด:** {c['limit']}\n\n**แนวพูด:** {c['speech']}\n"
 text+='\n## ตัวเลขส่วนประกอบกรณีศึกษา (คัน/ชั่วโมง)\n\n'+tab(parts)+'\n\nค่าบวกคือเพิ่ม ค่าลบคือลด ไม่ใช่สาเหตุ และไม่ใช่จำนวนผู้โดยสาร\n'
 text+='\n## ตารางความน่าเชื่อถือกรณีศึกษา\n\n'+tab(case)+'\n\ncommon_months เป็นเดือนที่พบร่วม ไม่ได้หมายถึงผลหลักจับคู่เดือนแล้ว คอลัมน์ตัดปีล่าสุดเป็นผลประกอบ ไม่เสนอให้ลบปีนั้น; วันที่จริงและแถว Excel อยู่ใน tables/case_dates.csv หากมีกรณีผ่านเกณฑ์\n\n## สมมติฐานศูนย์บนหน่วยร่วม\n\n'+tab(zero)+'\n\nการลบแถวยังเปลี่ยนวันสำรวจ ไม่พิสูจน์ว่าศูนย์ถูกต้องทุกช่อง\n'
 text+='''\n## นิยามและข้อเสนอแนะ

[คู่มือ สจส. หน้าเลขพิมพ์ 133–137](https://traffic.bangkok.go.th/TechnicalManuals/TTD.pdf#page=139) ระบุหมวดรถยนต์รวมแท็กซี่/รถแวน และเมล์ใหญ่รวมรถทัวร์/สวัสดิการ ไม่ใช้คำว่ารถส่วนตัวหรือผู้ใช้ขนส่งสาธารณะทั้งหมด ไม่มีหมวดจักรยานยนต์ในหกหมวดนี้

เสนอให้สำรวจซ้ำจุดเดิม เวลาเดิม เดือนและประเภทวันใกล้เคียงกัน ทวนศูนย์กับต้นทาง และเพิ่มความเร็ว/เวลาเดินทาง/แถวคอยหากจะตอบเรื่องรถติด ไม่สรุปปลายทางหรือผลเชิงสาเหตุจากโควิด ใช้ [FHWA](https://www.fhwa.dot.gov/policyinformation/tmguide/tmg_2022/traffic-data-methodologies.cfm) เป็นบริบทการควบคุมวันและฤดูกาล ไม่ใช่อ้างว่า สจส. ใช้ทุกข้อ

## สิ่งที่ตัดจากชุดนำเสนอ

ไม่ใส่แผนที่พิกัดบางส่วน กราฟปีล่าสุดกลุ่มเล็ก Bubble ที่ซ้ำกับรายสถานที่ รูปแบบภายในวันที่มีวันเดียว และส่วนแบ่งถนนที่ยังไม่ยืนยันครบแขนแยก ข้อมูลและกราฟเก่าคงอยู่ในเวอร์ชันเดิม

## ขอบเขตงานและบทบาท AI

เป็น EDA ด้วย Pandas/NumPy/Matplotlib ไม่เพิ่ม ML; AI ช่วยร่างโค้ด คัดกราฟ เรียบเรียง และตรวจสูตร สมาชิกต้องทวนข้อมูลและเติมการแบ่งหน้าที่ตามจริง ก่อนส่งยังต้องตรวจข้อกำหนดอาจารย์และจัด PDF/ลิงก์ GitHub ที่ใช้จริง
'''
 if len(m)<100:text+='\n**ข้อจำกัดการส่งงาน:** จับคู่ได้น้อยกว่า 100 แถว ต้องทบทวนขอบเขตกับข้อกำหนดรายวิชา ไม่สร้างแถวเพิ่มเทียม\n'
 text+='\n## นิยาม Lockdown และสถานะการอ้างอิง\n\nใช้สอง flag ตามไฟล์โดยผู้ใช้อนุญาต ไม่แก้ 168 แถวโดยอัตโนมัติสำหรับ snapshot (5); จำนวนจริงรอบนี้อยู่ในผลตรวจด้านล่าง ช่วงอ้างอิงรวมวันเริ่มและวันสิ้นสุด 22 มี.ค.–12 เม.ย. 2020 และ 12 ก.ค.–30 ก.ย. 2021; ไม่รวมประกาศสถานการณ์ฉุกเฉินเป็นมาตรการเดียวกันโดยอัตโนมัติ Not Lockdown หมายถึงค่า 0 ตามนิยามนี้ ไม่ใช่ไม่มีมาตรการทุกชนิด\n\n[ไทยโพสต์](https://www.thaipost.net/main/detail/60470) รองรับช่วงปิดสถานที่ปี 2020; [BBC](https://www.bbc.com/thai/thailand-57773493) รองรับวันเริ่มปี 2021 แต่ยังไม่ยืนยันวันสิ้นสุด 30 ก.ย. จากบทความนั้น; [ราชกิจจาฯ ที่ผู้ใช้ให้](https://www.ratchakitcha.soc.go.th/DATA/PDF/2563/E/069/T_0001.PDF) เปิดตรวจไม่ได้ในการตรวจรอบก่อน ช่วง 26 มี.ค.–30 เม.ย. บันทึกเป็นข้อมูลผู้ใช้ ไม่ใช่ข้อเท็จจริงที่ยืนยันจาก PDF แล้ว\n\n'+tab(pd.DataFrame(lock_summary))+'\n\n'+'\n'.join(notes);(out/'README.md').write_text(text,encoding='utf-8')
 (out/'Speaker_Notes.md').write_text('# แนวพูดหน้าชั้นเรียน\n\nเปิดเรื่อง: เราศึกษาปริมาณรถ ณ จุดสำรวจ ไม่ใช่ระดับรถติดทั้งเมือง\n\n'+'\n\n'.join(f"## {c['title']}\n\n{c['speech']}\n\nตัวเลขที่พูด: {c['finding']}\n\nถ้าถูกถาม: {c['limit']}" for c in charts)+'\n\nปิดเรื่อง: ผลช่วยระบุจุดที่ควรตรวจหรือสำรวจซ้ำ ยังไม่แยกสาเหตุของโควิดออกจากปัจจัยอื่น',encoding='utf-8')
 slides=['<section><h1>Bangkok Traffic V4</h1><p>ปริมาณรถและความต่างรายสถานที่</p><p>'+html.escape(statement)+'</p></section>']
 for c in charts:slides.append('<section><h2>'+html.escape(c['title'])+'</h2><img src="figures/'+c['image']+'"><p>'+html.escape(c['finding'])+'</p><small>'+html.escape(c['limit'])+'</small></section>')
 slides.append('<section><h2>ข้อเสนอแนะและข้อจำกัด</h2><p>สำรวจซ้ำสถานที่ เวลา เดือน และประเภทวันให้เทียบเคียงกัน</p><p>ทวนข้อมูลต้นทางและค่าว่าง; เพิ่มความเร็วหรือเวลาเดินทางหากจะตอบเรื่องรถติด</p><p>ยังไม่สรุปผลเชิงสาเหตุจาก COVID</p></section>')
 (out/'Presentation.html').write_text('<!doctype html><html lang="th"><meta charset="utf-8"><title>Bangkok Traffic V4</title><style>body{font:20px Tahoma,sans-serif;background:#eef2f5;color:#163344}section{box-sizing:border-box;background:white;max-width:1200px;margin:24px auto;padding:36px;min-height:650px}img{display:block;max-width:100%;max-height:440px;margin:auto}small{font-size:15px}@media print{@page{size:A4 landscape;margin:12mm}body{background:white}section{break-after:page;margin:0;padding:0;min-height:0}img{max-height:135mm}}</style>'+''.join(slides)+'</html>',encoding='utf-8')
 assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
 assert np.allclose(d.vph*d.period_hours,d.total)
 manifest={'status':'complete','source_sha256':sha,'source_filename':source.name,'raw_rows':len(raw),'eligible_rows':len(d),'matched_rows':len(m),'units':len(w),'charts':charts,'notes':notes,'lockdown_summary':lock_summary,'flag_notes':flag_notes,'bootstrap_replicates':1000,'version':'4.0','run_id':out.name}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output-parent');a=p.parse_args();print(run(a.input,a.output_parent))
