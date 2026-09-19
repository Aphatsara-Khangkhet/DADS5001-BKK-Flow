"""V5: ordered presentation, Matplotlib figures and auditable chart data.

Run --input new.xlsx to audit and recompute. Existing runs are never overwritten.
--audited-run reuses a validated run only when its source SHA256 matches --input.
"""
from pathlib import Path
import argparse, datetime, hashlib, html, json, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
import pipeline as base

P=base.PERIODS; K=base.KEY; V=base.V
PE=['Before','During','After']; COLORS=['#557C9B','#D58A36','#178778']
VE=['Car incl. taxi','Pickup / van','Large bus / coach','Small bus','Truck','Tuk-tuk']
ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 ('ผลสำรวจทางแยก สจส. กทม.','https://traffic.bangkok.go.th/re_intersection/intersection/intersection.html'),
 ('คู่มือ สจส. หมวดรถและงานสำรวจ หน้า 133–137','https://traffic.bangkok.go.th/TechnicalManuals/TTD.pdf#page=139'),
 ('ปิดสถานที่ 22 มี.ค.–12 เม.ย. 2020','https://www.thaipost.net/main/detail/60470'),
 ('เริ่มมาตรการ 12 ก.ค. 2021; ไม่ยืนยันวันสิ้นสุด','https://www.bbc.com/thai/thailand-57773493'),
 ('FHWA: บริบทความต่างตามวันและฤดูกาล','https://www.fhwa.dot.gov/policyinformation/tmguide/tmg_2022/traffic-data-methodologies.cfm')]

def safe(obj):
 if isinstance(obj,dict): return {str(k):safe(v) for k,v in obj.items()}
 if isinstance(obj,(list,tuple)):return [safe(v) for v in obj]
 if isinstance(obj,np.generic):return safe(obj.item())
 if isinstance(obj,float) and not np.isfinite(obj):return None
 return obj

def bar(categories,series,ylabel,horizontal=False):
 return dict(kind='bar',categories=list(categories),series=series,ylabel=ylabel,horizontal=horizontal)
def series(name,values,color):return dict(name=name,values=list(values),color=color)
def heat(rows,cols,values,label,cmap='Blues',vmin=None,vmax=None):
 return dict(kind='heatmap',rows=list(rows),categories=list(cols),values=np.asarray(values).tolist(),ylabel=label,cmap=cmap,vmin=vmin,vmax=vmax)
def scatter(ss,xlabel,ylabel,equality=False):return dict(kind='scatter',series=ss,xlabel=xlabel,ylabel=ylabel,equality=equality)

def render(spec,path):
 panels=spec.get('panels',[spec]);fig,axes=plt.subplots(1,len(panels),figsize=(13,5.3),squeeze=False)
 for ax,s in zip(axes[0],panels):
  if s['kind']=='heatmap':
   a=np.asarray(s['values']);im=ax.imshow(a,aspect='auto',cmap=s.get('cmap','Blues'),vmin=s.get('vmin'),vmax=s.get('vmax'))
   ax.set_xticks(range(len(s['categories'])),s['categories']);ax.set_yticks(range(len(s['rows'])),s['rows'])
   for i,row in enumerate(a):
    for j,z in enumerate(row):ax.text(j,i,f'{z:.0f}' if s.get('integer') else f'{z:.1f}',ha='center',va='center',fontsize=9,color='black',bbox=dict(facecolor='white',alpha=.65,edgecolor='none',pad=.6))
   fig.colorbar(im,ax=ax,label=s['ylabel'])
  elif s['kind']=='bar':
   x=np.arange(len(s['categories']));width=.78/max(len(s['series']),1)
   for j,r in enumerate(s['series']):
    pos=x+(j-(len(s['series'])-1)/2)*width
    if s.get('horizontal'):ax.barh(pos,r['values'],height=width,color=r['color'],label=r['name'])
    else:ax.bar(pos,r['values'],width=width,color=r['color'],label=r['name'])
   if s.get('horizontal'):ax.set_yticks(x,s['categories']);ax.invert_yaxis();ax.set_xlabel(s['ylabel']);ax.axvline(0,color='#BCC7CC',lw=.7)
   else:ax.set_xticks(x,s['categories']);ax.set_ylabel(s['ylabel']);ax.axhline(0,color='#BCC7CC',lw=.7)
   if len(s['series'])>1:ax.legend(frameon=False,ncol=min(3,len(s['series'])))
   if 'baseline' in s:
    (ax.axvline if s.get('horizontal') else ax.axhline)(s['baseline'],ls='--',color='#53616A',lw=1)
  else:
   for r in s['series']:ax.scatter(r['x'],r['values'],s=20 if len(r['x'])>50 else 65,color=r['color'],alpha=.6 if len(r['x'])>50 else .95,label=r['name'])
   if s.get('equality'):
    lim=max(max(r['x']+r['values']) for r in s['series'])*1.05;ax.plot([0,lim],[0,lim],ls='--',color='#7A858A');ax.set_xlim(0,lim);ax.set_ylim(0,lim)
   ax.set_xlabel(s['xlabel']);ax.set_ylabel(s['ylabel']);ax.legend(frameon=False)
   if s.get('year_axis'):ax.ticklabel_format(useOffset=False,style='plain',axis='x')
  if s.get('subtitle'):ax.set_title(s['subtitle'],fontsize=12)
  if s['kind']!='heatmap':ax.spines[['top','right']].set_visible(False)
 fig.suptitle(spec['chart_heading'],fontsize=14,fontweight='bold',y=.99)
 fig.tight_layout(rect=(0,0,1,.94));fig.savefig(path,dpi=180,facecolor='white');plt.close(fig)

def build(source,audited_run=None,output_parent=None):
 source=Path(source).resolve();sha=hashlib.sha256(source.read_bytes()).hexdigest()
 run=Path(audited_run) if audited_run else base.run(source,ROOT/'analysis_runs')
 if not (run/'manifest.json').exists():raise ValueError(f'Analysis gate did not pass. Review {run / "AUDIT.md"} before building slides.')
 meta=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
 assert meta['source_sha256']==sha,'Cached analysis belongs to another raw file'
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
 out=Path(output_parent or ROOT/'runs')/(stamp+'_'+sha[:10]);out.mkdir(parents=True,exist_ok=False)
 for name in ['figures','tables','chart_data']:(out/name).mkdir()
 shutil.copytree(run/'tables',out/'tables',dirs_exist_ok=True)
 shutil.copytree(run/'outputs/current_audit',out/'audit_details')
 shutil.copy2(run/'AUDIT.md',out/'AUDIT.md')
 raw=pd.read_csv(run/'data/interim/traffic_audited.csv',low_memory=False)
 d=pd.read_csv(run/'data/processed/traffic_candidates.csv',low_memory=False)
 d=d[d.survey_date_parsed.notna()&d.survey_year.ge(2017)].copy()
 d['total']=d[[v+'_clean' for v in V]].sum(axis=1);d['vph']=d.total/d.period_hours
 m,w,idx=base.pair(d,K);idx=idx.dropna();w=w.loc[idx.index]
 m=m.merge(idx.reset_index()[K],on=K,how='inner')
 idx.reset_index().to_csv(out/'tables/matched_indices.csv',index=False,encoding='utf-8-sig')
 w.reset_index().to_csv(out/'tables/matched_levels.csv',index=False,encoding='utf-8-sig')
 m[['source_excel_row','survey_date_parsed','covid_period',*K,'period_hours','total','vph']].to_csv(out/'tables/matched_observations.csv',index=False,encoding='utf-8-sig')
 bundled_font=ROOT/'assets/NotoSansThai.ttf'
 if bundled_font.exists():font_manager.fontManager.addfont(str(bundled_font))
 fonts={f.name for f in font_manager.fontManager.ttflist}
 font=next((f for f in ['Tahoma','Noto Sans Thai'] if f in fonts),'DejaVu Sans')
 plt.rcParams.update({'font.family':font,'font.size':11,'axes.unicode_minus':False})
 graphs=[]
 def add(key,title,spec,read,finding,limit,speech,action,table,appendix=False):
  num=len(graphs)+1;spec['chart_heading']=f'{num:02d}. '+title
  item=dict(number=num,key=key,title=title,image=f'{num:02d}_{key}.png',read=read,finding=finding,limit=limit,speech=speech,action=action,table=table,spec=spec,appendix=appendix)
  render(spec,out/'figures'/item['image']);graphs.append(item)
  (out/'chart_data'/f'{num:02d}_{key}.json').write_text(json.dumps(safe(spec),ensure_ascii=False,indent=2),encoding='utf-8')
 def load(name):return pd.read_csv(out/'tables'/name)
 def csv(frame,name):frame.to_csv(out/'tables'/name,index=False,encoding='utf-8-sig')

 cov=load('coverage.csv');s=heat(cov.iloc[:,0].astype(int).astype(str),[str(x) for x in range(1,13)],cov.iloc[:,1:].values,'Rows / report month');s['integer']=True
 add('coverage','ข้อมูลครอบคลุมวันใดบ้าง',s,'สีและตัวเลขคือจำนวนแถวต่อเดือนรายงาน ไม่ใช่ปริมาณรถ',f"วันสำรวจ {d.survey_date_parsed.min()} ถึง {d.survey_date_parsed.max()} | {len(raw):,} แถว → ผ่านเกณฑ์ {len(d):,} แถว",'ข้อมูลเป็นวันสำรวจบางวัน และปีล่าสุดไม่ครบปี; ช่อง 0 คือไม่มีรายการในไฟล์','เรามีข้อมูลหลายปี แต่ไม่ได้มีทุกแยกทุกวัน จึงรวมยอดรายปีมาเทียบตรง ๆ ไม่ได้','เปรียบเทียบหน่วยเดิมและเวลาเดิมก่อนตีความ','coverage.csv')
 ov=load('overview.csv');s=bar(PE,[series('Median index',ov.median_index,COLORS[2])],'Index: Before = 100');s['baseline']=100
 overview=f"Before 100 → During {ov.median_index.iloc[1]:.1f} → After {ov.median_index.iloc[2]:.1f} | n={len(idx)} หน่วย"
 ci=f"ช่วง 95%: During {ov.p025.iloc[1]:.1f}–{ov.p975.iloc[1]:.1f}; After {ov.p025.iloc[2]:.1f}–{ov.p975.iloc[2]:.1f}"
 add('overview','ปริมาณรถในหน่วยที่จับคู่ครบสามช่วง',s,'ใช้มัธยฐานคัน/ชั่วโมงของแต่ละหน่วยในแต่ละช่วง หารฐาน Before ของหน่วยนั้น แล้วหามัธยฐานข้ามหน่วย',overview,'เป็นดัชนีของตัวอย่าง ไม่ใช่ยอดรถรวมทั้งเมือง; ไม่พิสูจน์ผลเชิงสาเหตุ',f'ตั้ง Before ของแต่ละหน่วยเป็น 100 ผลภาพรวมคือ {overview} จึงพบระดับต่ำกว่าฐานทั้งสองช่วง แต่ยังแยกสาเหตุไม่ได้ '+ci,'เริ่มดูการกระจายและสถานที่ เพราะค่ากลางอาจซ่อนความต่าง','overview.csv')
 panels=[]
 for j,p in enumerate(P[1:],1):
  ss=scatter([dict(name=f'{PE[j]} / n={len(w)}',x=w[P[0]].tolist(),values=w[p].tolist(),color=COLORS[j])],'Before: median vehicles/hour',f'{PE[j]}: median vehicles/hour',True);ss['subtitle']=f'Before vs {PE[j]}';panels.append(ss)
 lower=[(w[p]<w[P[0]]).mean()*100 for p in P[1:]]
 add('paired','แต่ละหน่วยอยู่เหนือหรือต่ำกว่าฐาน',dict(panels=panels),'หนึ่งจุดคือทางแยก–ถนน–ช่วงเวลา; จุดใต้เส้นทแยงมีปริมาณต่ำกว่า Before',f'ต่ำกว่าฐาน: During {lower[0]:.1f}% | After {lower[1]:.1f}% ของ {len(w)} หน่วย','จุดสำรวจไม่ได้เป็นตัวอย่างสุ่มทั้งกรุงเทพฯ; จุดบนแกนศูนย์ยังแสดงไว้','เส้นทแยงคือระดับเท่าเดิม เรามีทั้งจุดที่สูงขึ้นและต่ำลง ไม่ใช่ทุกแห่งเปลี่ยนไปในทิศทางเดียวกัน','ไม่ใช้ค่ากลางแทนการตัดสินทุกทางแยก','matched_levels.csv')
 edges=[0,50,80,100,120,150,200,np.inf];labels=['<50','50–<80','80–<100','100–<120','120–<150','150–<200','≥200']
 hist=pd.DataFrame({'index_bin':labels})
 for p,e in zip(P[1:],PE[1:]):hist[e]=np.histogram(idx[p],bins=edges)[0]
 csv(hist,'index_distribution.csv')
 add('distribution','ค่ากลางซ่อนการกระจายมากแค่ไหน',bar(labels,[series(e,hist[e],COLORS[j]) for j,e in enumerate(PE) if j],'Matched units'),'แกนนอนเป็นช่วงดัชนี โดย 100 เท่าฐาน; แกนตั้งคือจำนวนหน่วย ใช้ชุดเดิมครบทั้งสองช่วง',f"After มี {int(idx[P[2]].ge(100).sum())}/{len(idx)} หน่วย ({idx[P[2]].ge(100).mean()*100:.1f}%) ที่ไม่น้อยกว่าฐาน",'ช่วงท้ายรวมดัชนีตั้งแต่ 200 ขึ้นไป; ฐานน้อยทำให้เปอร์เซ็นต์เปลี่ยนสูงได้','ค่า After ใกล้ 90 ไม่ได้แปลว่าทุกแยกลด 10 เปอร์เซ็นต์ กราฟนี้แสดงทั้งกลุ่มต่ำกว่าฐานและกลุ่มที่กลับมาไม่น้อยกว่าฐาน','ใช้ข้อมูลคัน/ชั่วโมงประกอบดัชนีเมื่อเลือกจุดศึกษา','index_distribution.csv')
 a=idx[P[1]].ge(100);b=idx[P[2]].ge(100)
 groups=[(~a&~b),(~a&b),(a&~b),(a&b)];labs=['D<100 / A<100','D<100 / A≥100','D≥100 / A<100','D≥100 / A≥100']
 trans=pd.DataFrame({'pattern':labs,'units':[int(x.sum()) for x in groups]});trans['share_pct']=trans.units/len(idx)*100;csv(trans,'period_patterns.csv')
 add('patterns','การเปลี่ยนแปลงมีสี่รูปแบบ',bar(labs,[series('Matched units',trans.units,COLORS[2])],'Matched units'),'D = During, A = After; แบ่งด้วยดัชนี 100 ของ Before โดยใช้หน่วยเดิมทั้งหมด',f"ต่ำกว่าฐานทั้งสองช่วง {trans.units.iloc[0]} หน่วย; During ต่ำ แต่ After ≥ ฐาน {trans.units.iloc[1]} หน่วย",'เป็นการจำแนกระดับ ไม่ใช่เส้นทางรายปีต่อเนื่อง และไม่ใช่การทดสอบนัยสำคัญ','การบอกเพียงว่าฟื้นหรือไม่ฟื้นยังหยาบเกินไป เราแยกได้สี่แบบ บางแห่งต่ำกว่าฐานทั้งสองช่วง บางแห่งกลับมาไม่น้อยกว่าฐานใน After','ใช้รูปแบบเป็นเกณฑ์เลือกกรณีศึกษาหรือสำรวจซ้ำ','period_patterns.csv')
 time=idx.groupby(level='time_key').median();n=idx.groupby(level='time_key').size();time['units']=n;csv(time.reset_index(),'time_window_indices.csv')
 s=bar([f'{t}\nn={int(n[t])}' for t in time.index],[series(PE[j],time[p],COLORS[j]) for j,p in enumerate(P)],'Median index: Before = 100');s['baseline']=100
 add('time_windows','ช่วงเวลาสำรวจให้ผลเหมือนกันหรือไม่',s,'แต่ละกลุ่มเปรียบเทียบสามช่วงภายในเวลาเดียวกัน; ทุกค่าหารด้วยชั่วโมงสำรวจแล้ว',f'มี {len(time)} ช่วงเวลาที่จับคู่ได้; จำนวนหน่วยต่อเวลา {int(n.min())}–{int(n.max())} หน่วย','กลุ่มเวลาประกอบด้วยสถานที่ต่างกัน จึงไม่ใช้สรุปว่าคนย้ายเวลาเดินทาง','เวลาเย็น 16–19 กับ 17–19 เป็นคนละหน่วย เราไม่รวมเพราะอาจทำให้ความหมายเปลี่ยน กลุ่มเล็กต้องอ่านด้วยความระมัดระวัง','ถ้าจะตอบการย้ายเวลา ต้องจับคู่จุดและวันที่เดียวกันข้ามเวลาด้วย','time_window_indices.csv')
 loc=load('location_lookup.csv');s=heat((loc.intersection_key+' / '+loc.road_key).tolist(),PE,loc[P].values,'Index: Before = 100','RdBu_r',0,200)
 add('locations','สถานที่ที่มีความต่างเด่น',s,'แสดงคู่เช้า 07–09 น. ที่มีอย่างน้อย 2 รายการทุกช่วง เลือก 12 คู่ที่ |After−100| มากที่สุด; สเกลสี 0–200',f'แสดง {len(loc)} คู่; สีแดงมากกว่า Before สีฟ้าต่ำกว่า Before และมีตัวเลขกำกับ','คัดผลต่างสูงเพื่อศึกษา ไม่เป็นตัวแทนทั้งเมือง; สีตัดที่ 200 แต่ตัวเลขไม่ตัด','หลังเห็นภาพรวม เราซูมไปยังจุดที่ต่างเด่น โดยเปิดเผยเกณฑ์เลือกตั้งแต่ต้น แล้วตรวจวันที่และประเภทรถต่อ','ทวนรายงานต้นทางก่อนตั้งสมมติฐานเรื่องบริบทพื้นที่','location_lookup.csv')
 cases=load('case_dates.csv');ca=load('case_audit.csv');panels=[]
 common_case_months='; '.join(f'{r.intersection}: เดือนร่วม {r.common_months}' for r in ca.itertuples())
 for (inter,road),g in cases.groupby(['intersection_key','road_key'],sort=False):
  ss=[]
  for j,p in enumerate(P):
   z=g[g.covid_period.eq(p)];dt=pd.to_datetime(z.survey_date_parsed);x=dt.dt.year+(dt.dt.dayofyear-1)/365.25
   ss.append(dict(name=f'{PE[j]} (n={len(z)})',x=x.tolist(),values=z.vph.tolist(),color=COLORS[j]))
  sp=scatter(ss,'Survey year (point = actual survey date)','Vehicles/hour');sp['subtitle']=inter+' / '+road;sp['year_axis']=True;panels.append(sp)
 add('case_dates','วันที่สำรวจของกรณีศึกษา',dict(panels=panels),'แต่ละจุดคือวันสำรวจจริง ไม่ลากเส้นเชื่อม; วันเต็มและแถว Excel อยู่ในตาราง', '; '.join(f'{r.intersection}: n={r.before_n}/{r.during_n}/{r.after_n}' for r in ca.itertuples()),common_case_months+'; [] = ไม่มีเดือนร่วมครบสามช่วง ยังไม่มีหลักฐานเทศกาลหรือปลายทาง','จำนวนวันและเดือนของกรณีศึกษาอยู่ในตาราง แม้ค่าจะต่างชัด ก็ยังอธิบายไม่ได้ว่าเกิดจากโควิด เทศกาล งานก่อสร้าง หรือความผันผวนของวันสำรวจ','ใช้วันนี้ไปตรวจ PDF และประวัติเหตุการณ์ แยกสิ่งยืนยันแล้วออกจากสมมติฐาน','case_dates.csv')
 cv=load('case_vehicle_three_periods.csv');panels=[]
 for (inter,road),g in cv.groupby(['intersection','road'],sort=False):
  wide=g.pivot(index='vehicle',columns='period',values='mean_vph').reindex(V)
  sp=bar(VE,[series(PE[j],wide[p],COLORS[j]) for j,p in enumerate(P)],'Mean vehicles/hour',True);sp['subtitle']=inter+' / '+road;panels.append(sp)
 add('case_vehicles','ประเภทรถที่ประกอบเป็นความต่างของพื้นที่',dict(panels=panels),'ทุกหมวดมี Before / During / After; ใช้ค่าเฉลี่ยคัน/ชั่วโมงเพื่อแสดงระดับของหมวดรถ', '; '.join(f'{r.intersection}: ดัชนีรถรวม After เทียบ Before {r.change_pct:+.1f}%' for r in ca.itertuples()),'เปอร์เซ็นต์รถรวมในข้อความคำนวณจากมัธยฐาน แต่แท่งหมวดรถเป็นค่าเฉลี่ย; ห้ามบวกมัธยฐานรายหมวดแทนรถรวม','ดูว่าหมวดใดมีระดับมากและหมวดใดเปลี่ยน โดยยังไม่ตีความว่าเป็นการเปลี่ยนพาหนะของคนกลุ่มเดิม','ตรวจหมวดที่เปลี่ยนมากกับตารางนับรถต้นทาง','case_vehicle_three_periods.csv')
 mix=load('mix_change.csv').set_index('vehicle').reindex(V)
 mix_n=int(m[m.total.gt(0)].groupby(K).covid_period.nunique().eq(3).sum())
 add('mix','องค์ประกอบรถครบสามช่วง',bar(VE,[series(PE[j],mix[p],COLORS[j]) for j,p in enumerate(P)],'Mean share (%)',True),'คำนวณสัดส่วนแต่ละรายการ → เฉลี่ยในหน่วย–ช่วง → เฉลี่ยข้ามหน่วยร่วมที่มีรถรวมบวกครบทุกช่วง',f"รถยนต์รวมแท็กซี่: {mix.loc[V[0],P[0]]:.2f}% → {mix.loc[V[0],P[1]]:.2f}% → {mix.loc[V[0],P[2]]:.2f}% | n={mix_n}",f'n={mix_n} หน่วย; สัดส่วนไม่ใช่จำนวน และชุดนี้ไม่มีจักรยานยนต์','รถยนต์เป็นหมวดใหญ่ที่สุดในหกหมวดที่เราเก็บได้ แต่ไม่ใช่ส่วนแบ่งทุกยานพาหนะของกรุงเทพฯ และไม่ใช่รถส่วนตัวทั้งหมด','ใช้ประกอบการวางแผนสำรวจหมวดรถเพิ่มเติม','mix_change.csv')
 delta=pd.DataFrame({'vehicle':V,'During_minus_Before_pp':mix[P[1]].values-mix[P[0]].values,'After_minus_Before_pp':mix[P[2]].values-mix[P[0]].values});csv(delta,'mix_delta.csv')
 add('mix_delta','สัดส่วนหมวดเล็กเปลี่ยนอย่างไร',bar(VE,[series('During − Before',delta.iloc[:,1],COLORS[1]),series('After − Before',delta.iloc[:,2],COLORS[2])],'Change in percentage points',True),'ค่าบวกคือส่วนแบ่งเพิ่ม ค่าลบคือส่วนแบ่งลด หน่วยเป็นจุดเปอร์เซ็นต์ ไม่ใช่เปอร์เซ็นต์การเติบโต',f"รถยนต์: During {delta.iloc[0,1]:+.2f} จุด; After {delta.iloc[0,2]:+.2f} จุด เทียบ Before",'หมวดหนึ่งเพิ่ม ส่วนอื่นต้องลดรวมกันตามนิยามสัดส่วน; ไม่สรุปการย้ายจากรถเมล์ไปใช้รถส่วนตัว','กราฟก่อนเห็นโครงสร้างใหญ่ ส่วนกราฟนี้ขยายการเปลี่ยนของแต่ละหมวดโดยใช้แกนศูนย์ร่วมกัน','ถ้าจะศึกษาการเปลี่ยนวิธีเดินทาง ต้องมีข้อมูลผู้เดินทางหรือผู้โดยสารเพิ่ม','mix_delta.csv')
 ls=load('lockdown_summary.csv');lu=load('Supplied_flags_lockdown_units.csv')
 sp=scatter([dict(name=f'Supplied flags / n={len(lu)}',x=lu['0'].tolist(),values=lu['1'].tolist(),color=COLORS[1])],'Not Lockdown: median vehicles/hour','Lockdown: median vehicles/hour',True)
 lb=bar([f'Supplied\nn={int(ls.units.iloc[0])}',f'Reference\nn={int(ls.units.iloc[1])}',f'Same month\nn={int(ls.units.iloc[2])}'],[series('Lockdown index',ls.median_index,COLORS[1])],'Index: Not Lockdown = 100');lb['baseline']=100
 mismatch=len(load('lockdown_date_review.csv'))
 add('lockdown','Lockdown ภายในช่วง During',dict(panels=[sp,lb]),'จับคู่ทางแยก–ถนน–เวลา ภายใน During เท่านั้น; กราฟขวาเทียบนิยามและเงื่อนไขเดือน',f"ตาม flag ในไฟล์ n={int(ls.units.iloc[0])}: ดัชนี {ls.median_index.iloc[0]:.1f} | เทียบกรอบวันที่ {ls.median_index.iloc[1]:.1f}",f'flag ต่างจากกรอบวันที่อ้างอิง {mismatch} แถว; คุมเดือนเหลือ {int(ls.units.iloc[2])} หน่วย จึงไม่สรุปเชิงสาเหตุ','ผลตาม flag พบระดับต่ำกว่า Not Lockdown แต่วันสำรวจและนิยามยังมีข้อจำกัด เราคง flag ของผู้ใช้และแสดงผลอีกนิยามประกอบ','ยืนยันเกณฑ์วันสิ้นสุดและทวนแถว flag ก่อนอ้างเป็นผลของมาตรการ','lockdown_summary.csv')
 sens=load('sensitivity.csv');s=bar([f'{r.design}\nn={r.units}' for r in sens.itertuples()],[series('During',sens.During,COLORS[1]),series('After',sens.After,COLORS[2])],'Median index: Before = 100');s['baseline']=100
 add('sensitivity','ข้อสรุปเปลี่ยนเมื่อจับคู่ละเอียดขึ้นหรือไม่',s,'เพิ่มเงื่อนไขไตรมาสรายงานหรือเดือนสำรวจ โดยสร้างกลุ่มจับคู่ใหม่ในแต่ละวิธี', '; '.join(f'n={r.units}: During {r.During:.1f}, After {r.After:.1f}' for r in sens.itertuples()),'ขนาดและสมาชิกเปลี่ยน จึงแยกผลของการคุมปฏิทินออกจากการเปลี่ยนตัวอย่างไม่ได้','ทุกวิธีในรอบนี้ต่ำกว่าฐาน Before แต่ After เทียบ During ไม่ได้เรียงเหมือนกันทุกวิธี จึงไม่ควรสรุปเส้นทางการฟื้นจากค่ากลางวิธีเดียว','รายงานผลหลักพร้อมความไว และวางแผนเก็บจุดเดิมเดือนเดิม','sensitivity.csv')
 wd=m.copy();wd['weekday']=pd.to_datetime(wd.survey_date_parsed).dt.dayofweek
 wc=pd.crosstab(wd.weekday,wd.covid_period).reindex(index=range(7),columns=P,fill_value=0).fillna(0);pct=wc.div(wc.sum(),axis=1)*100
 csv(wc.reset_index(),'weekday_counts.csv');csv(pct.reset_index(),'weekday_share.csv')
 add('weekday','วันสำรวจของกลุ่มจับคู่เหมือนกันหรือไม่',bar(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],[series(f'{PE[j]} (rows={int(wc[p].sum())})',pct[p],COLORS[j]) for j,p in enumerate(P)],'Share of matched survey rows (%)'),'สัดส่วนแถวสำรวจตามวันในสัปดาห์ ไม่ใช่สัดส่วนจำนวนรถ; ชุดหลักเดียวกับกราฟภาพรวม',f'ใช้ {len(m):,} แถวที่อยู่ใน {len(idx)} หน่วยจับคู่','หลายแถวอาจเป็นวันเดียวกันหรือแยกเดียวกัน; ไม่ได้ตรวจวันหยุดและเทศกาล','แม้จะจับคู่สถานที่และเวลาแล้ว วันที่เก็บยังต่างกันได้ กราฟนี้ไว้ตอบคำถามเรื่องปฏิทิน ไม่ใช้สรุปว่าวันใดรถมาก','หากเพิ่มข้อมูลวันหยุด ให้จับคู่ประเภทวันเพิ่มและตรวจจำนวนหน่วยที่เหลือ','weekday_counts.csv',True)

 stats=dict(source_filename=source.name,source_sha256=sha,raw_rows=len(raw),eligible_rows=len(d),matched_rows=len(m),units=len(idx),intersections=idx.index.get_level_values(0).nunique(),date_min=d.survey_date_parsed.min(),date_max=d.survey_date_parsed.max(),overview=overview,ci=ci,lockdown_index=ls.median_index.iloc[0],flag_mismatch=mismatch)
 slides=[]
 def text_slide(title,body,notes,kind='text',appendix=False):slides.append(dict(title=title,body=body,notes=notes,kind=kind,appendix=appendix))
 text_slide('Traffic Re:View','ปริมาณรถที่ทางแยกกรุงเทพมหานคร\nBefore · During · After COVID\nDADS5001 | Final presentation V5',f'งาน EDA จากไฟล์ {source.name} ชีต traffic_data ข้อมูลยังเป็นฉบับร่างที่ผู้ใช้กำลังตรวจต้นทาง ไม่ใช่สำมะโนการจราจรทั้งเมือง','cover')
 text_slide('ที่มาและคำถามของโครงการ','ข้อมูลผลสำรวจทางแยกของ สจส. กรุงเทพมหานคร\n1. หน่วยเดิมเปลี่ยนไปอย่างไรในสามช่วง?\n2. สถานที่และประเภทรถเปลี่ยนเหมือนกันหรือไม่?\n3. ผลไวต่อวันสำรวจและนิยาม Lockdown แค่ไหน?', 'เว็บไซต์เผยแพร่รายงานผลสำรวจ คู่มืออธิบายงานเก็บข้อมูลเพื่อสนับสนุนงานจราจร เช่น การจัดการสัญญาณและงานวางแผน แต่ไม่ระบุเหตุผลของทุกจุดในไฟล์ เราจึงใช้ข้อมูลตอบเรื่องปริมาณรถ ไม่ตอบเรื่องความเร็วหรือปลายทางการเดินทาง\n'+str(SOURCES[:2]))
 text_slide('ฐานการเปรียบเทียบที่ใช้ร่วมกัน',f'แบ่งช่วงด้วย covid_period ตามไฟล์\nBefore 2017–2019 | During 2020–2021 | After 2022–{d.survey_date_parsed.max()}\nคัน/ชั่วโมง = รถ 6 หมวด ÷ ชั่วโมงสำรวจ\nจับคู่ ทางแยก + ถนน + เวลา ครบสามช่วง\n{len(raw):,} แถว → {len(d):,} ผ่านเกณฑ์ → {len(m):,} แถว / {len(idx)} หน่วย',f'ไม่รวมปี 2016 ตามคำสั่งผู้ใช้ ไม่เติมวันสำรวจที่ไม่มีเป็นศูนย์ ค่าว่างเฉพาะหมวดรถแทนศูนย์ตามข้อตกลง แถวที่ไม่ผ่านเกณฑ์ {len(raw)-len(d)} แถว; แถวที่มีการแทนศูนย์ในชุดผ่านเกณฑ์ {int(d.has_assumed_zero.sum())} ดูสาเหตุและรายการตัดออกใน AUDIT.md; ปีล่าสุดไม่ใช้เทียบยอดเต็มปี')
 for g in graphs:
  if g['appendix']:continue
  slides.append(dict(kind='chart',title=f"{g['number']:02d}  {g['title']}",graph=g['key'],body=g['finding'],notes='อ่านกราฟ: '+g['read']+'\nแนวพูด: '+g['speech']+'\nข้อจำกัด: '+g['limit']+'\nการนำไปใช้: '+g['action']+'\nตาราง: tables/'+g['table'],appendix=False))
 text_slide('สิ่งที่ข้อมูลตอบได้',f'1. {overview}\n2. แต่ละจุดเปลี่ยนต่างกัน จึงใช้ค่ากลางแทนทุกพื้นที่ไม่ได้\n3. Lockdown ตาม flag มีดัชนี {ls.median_index.iloc[0]:.1f} แต่ยังมีข้อจำกัดปฏิทิน\nพบความสัมพันธ์กับช่วงเวลา ยังยืนยันไม่ได้ว่าโควิดเป็นสาเหตุทั้งหมด','คำตอบต่อคำถามว่าโควิดส่งผลหรือไม่คือ ข้อมูลนี้พบปริมาณต่างกันระหว่างช่วงที่นิยามไว้และสอดคล้องกับสมมติฐานว่าการเดินทางเปลี่ยน แต่ EDA นี้ไม่มีสถานการณ์เปรียบเทียบที่ตัดปัจจัยอื่นออก จึงระบุผลเชิงสาเหตุไม่ได้ การลงทุนหรือมาตรการเฉพาะทางแยกยังต้องตรวจข้อมูลเพิ่ม')
 text_slide('ข้อเสนอแนะจากผลวิเคราะห์','สำรวจซ้ำ: จุดเดิม เวลาเดิม เดือนและประเภทวันใกล้เคียงกัน\nตรวจต้นทาง: จุดที่เปลี่ยนมากและวันที่กรณีศึกษา\nยืนยัน Lockdown: แยกปิดสถานที่ เคอร์ฟิว และภาวะฉุกเฉิน\nถ้าศึกษารถติด: เพิ่มความเร็ว เวลาเดินทาง หรือแถวคอย','ผลนี้ช่วยจัดลำดับประเด็นตรวจเพิ่มได้ แต่ยังไม่ใช้สั่งปรับสัญญาณไฟหรือเพิ่มรถเมล์จากจำนวนรถอย่างเดียว งานยังอยู่ในขอบเขต Pandas/NumPy/Matplotlib และการอธิบาย EDA ไม่จำเป็นต้องเพิ่ม ML')
 text_slide('แหล่งข้อมูลและบทบาท AI','สจส. กทม.: รายงานทางแยกและคู่มือปฏิบัติงาน\nไทยโพสต์ / BBC: บริบทวันเริ่มมาตรการตามแหล่งที่ให้\nFHWA: บริบทการควบคุมเวลาและฤดูกาล\nAI: ช่วยโค้ด ตรวจสูตร และร่างคำอธิบาย\nผู้จัดทำต้องตรวจข้อมูลต้นทางและรับผิดชอบข้อสรุป', '\n'.join(f'{a}: {b}' for a,b in SOURCES)+'\nแหล่งราชกิจจาฯ ที่ผู้ใช้ให้ยังไม่ได้ตรวจ PDF สำเร็จ ไม่ใช้ยืนยันว่าเป็นมาตรการเดียวกัน บทความ BBC ยังไม่ยืนยัน 30 ก.ย. 2021 เป็นวันสิ้นสุด')
 for g in graphs:
  if g['appendix']:slides.append(dict(kind='chart',title=f"ภาคผนวก {g['number']:02d}  {g['title']}",graph=g['key'],body=g['finding'],notes=g['read']+'\n'+g['speech']+'\n'+g['limit'],appendix=True))
 text_slide('ภาคผนวก: นิยามและข้อจำกัดสำคัญ',f'รถยนต์รวมแท็กซี่/แวน; เมล์ใหญ่รวมรถทัวร์/สวัสดิการ\nไม่มีจักรยานยนต์ และไม่มีจำนวนผู้โดยสาร\nNot Lockdown = flag 0 ไม่ใช่ไม่มีมาตรการทุกชนิด\nflag ต่างจากกรอบวันที่อ้างอิง {mismatch} แถว\nวันสิ้นสุด 30 ก.ย. 2021 ยังต้องยืนยันประกาศ','กรอบความไวใช้ 22 มี.ค.–12 เม.ย. 2020 และ 12 ก.ค.–30 ก.ย. 2021 รวมวันต้น/ปลาย ตามนิยามผู้ใช้ ไม่เปลี่ยน flag ในไฟล์; ภาวะฉุกเฉิน 26 มี.ค.–30 เม.ย. เป็นคนละนิยาม ไม่รวมโดยอัตโนมัติ; นิยามรถดูคู่มือ สจส. หน้า 133–137',appendix=True)
 text_slide('ภาคผนวก: คำถามที่คาดว่าจะได้รับ','ทำไมไม่เทียบยอดรวมรายปี? → จุดและจำนวนวันสำรวจไม่เท่ากัน\nทำไมใช้คัน/ชั่วโมง? → ความยาวช่วงสำรวจต่างกัน\nรู้หรือไม่ว่ารถไปไหน? → ไม่มีข้อมูลต้นทาง–ปลายทาง\nเทศกาลอธิบายได้ไหม? → ต้องตรวจวันและหลักฐานเหตุการณ์เพิ่ม\nสรุปว่าโควิดทำให้ลดได้ไหม? → ยังไม่ใช่ผลเชิงสาเหตุ','สำหรับคำถามสถิติ: ช่วงความไม่แน่นอนใช้ cluster bootstrap ตามทางแยก 1,000 รอบ seed 5001 เป็นผลประกอบ ไม่ได้แก้ selection bias และไม่ได้ทดสอบ After เทียบ During โดยตรง สำหรับข้อมูลใหม่ให้รัน audit ก่อนอ่านกราฟ เพราะจำนวนคู่และกรณีศึกษาอาจเปลี่ยน',appendix=True)
 for i,s in enumerate(slides,1):s['number']=i
 package=dict(version='5.0',stats=stats,graphs=graphs,slides=slides,sources=SOURCES)
 (out/'presentation_data.json').write_text(json.dumps(safe(package),ensure_ascii=False,indent=2),encoding='utf-8')
 intro=f'# Traffic Re:View — Final V5\n\n{len(slides)} สไลด์ / {len(graphs)} กราฟ เรียงตามลำดับนำเสนอ ผลจากไฟล์ `{source.name}` ชีต `traffic_data` เท่านั้น\n\nSHA256 `{sha}`\n\nข้อมูลฉบับร่าง: Final หมายถึงรูปแบบนำเสนอ ไม่ใช่การรับรองว่าทุกค่าตรงกับ PDF ต้นทาง\n\n## วิธีใช้\n\nเปิด Presentation.html เพื่อไล่สไลด์ ใช้ลูกศร ← → หรือคลิกปุ่ม; กด P เพื่อพิมพ์ทุกหน้า สไลด์ 1–19 เป็นเรื่องหลัก 20–22 เป็นภาคผนวก ถ้าเวลาน้อยใช้ 1,2,3,5,7,10,11,12,13,15,16,17,18,19 และเปิดที่เหลือตอนถามตอบ เวลาจริงต้องอิงประกาศรายวิชา\n\n## วิธีและผลหลัก\n\n{overview}\n\n{ci} จาก cluster bootstrap 1,000 รอบตามทางแยก ไม่รวมความเอนเอียงจากการเลือกตัวอย่าง ไม่ใช่ผลเชิงสาเหตุ\n\nทุกหน่วยคือ ทางแยก–ถนน–เวลาสำรวจ ไม่เท่ากับจำนวนทางแยก; ใช้ covid_period ตามไฟล์; ข้อมูลล่าสุดถึง {d.survey_date_parsed.max()}\n\n'
 md=intro;notes='# บทพูดเรียงตามสไลด์ Final V5\n\n';sections=[]
 lookup={g['key']:g for g in graphs}
 for s in slides:
  notes+=f"## สไลด์ {s['number']:02d} — {s['title']}\n\n{s['notes']}\n\n"
  if s['kind']=='chart':
   g=lookup[s['graph']];md+=f"## กราฟ {g['number']:02d} — {g['title']}\n\n![{g['title']}](figures/{g['image']})\n\n**คำถามและวิธีอ่าน:** {g['read']}\n\n**หลักฐาน:** {g['finding']}\n\n**แนวพูด:** {g['speech']}\n\n**ข้อจำกัด:** {g['limit']}\n\n**นำไปใช้:** {g['action']}\n\n[ตารางคำนวณ](tables/{g['table']})\n\n"
   content=f'<img src="figures/{g["image"]}" alt="{html.escape(g["title"])}"><p class="finding">{html.escape(g["finding"])}</p><p class="limit">{html.escape(g["limit"])}</p>'
  else:content='<div class="body">'+html.escape(s['body']).replace('\n','<br>')+'</div>'
  sections.append(f'<section class="{s["kind"]}"><header><span>{s["number"]:02d} / {len(slides)}</span><h1>{html.escape(s["title"])}</h1></header>{content}<details><summary>บทพูด / แหล่งอ้างอิง</summary><p>{html.escape(s["notes"]).replace(chr(10),"<br>")}</p></details></section>')
 md+='## แหล่งอ้างอิง\n\n'+'\n'.join(f'- [{a}]({b})' for a,b in SOURCES)+'\n\n## สิ่งที่ไม่ใช้สรุป\n\nไม่สร้างแผนที่ความหนาแน่นทั้งกรุงเทพฯ เมื่อยังไม่มีพิกัดและความครอบคลุมที่ตรวจแล้ว ไม่ใช้กราฟรายปีคนละจุดสรุปการฟื้น ไม่เดาว่ารถไปที่ใดหรือเป็นเทศกาลใด\n\n## เปลี่ยน Raw Data\n\nรัน `python src/final_project.py --input "new.xlsx"` จากโฟลเดอร์ V5 โปรแกรมจะสร้าง run ใหม่ ตรวจ audit และคำนวณใหม่ ไม่ทับผลก่อนหน้า ข้อมูลต้องมีชีต traffic_data และ schema เดิม; ถ้าไม่มี flag / กรณีศึกษาครบเกณฑ์ รุ่น Final นี้จะหยุดแทนการเติมผลเก่า ควรตรวจ audit ใหม่ก่อนใช้ผล\n\nAI ช่วยจัดโค้ด กราฟ และคำอธิบาย ผู้จัดทำต้องตรวจต้นทาง แก้ไขข้อสรุป และเติมสมาชิก/การแบ่งหน้าที่ตามจริงก่อนส่งตามข้อกำหนดอาจารย์\n'
 (out/'Read.md').write_text(md,encoding='utf-8');(out/'Speaker_Notes.md').write_text(notes,encoding='utf-8')
 style='body{margin:0;background:#e8eef1;color:#17323b;font:20px Tahoma,sans-serif}section{background:white;box-sizing:border-box;width:min(1280px,98vw);min-height:720px;margin:20px auto;padding:30px 48px;display:none}section.active{display:block}header{display:flex;gap:22px;align-items:baseline}header span{font-size:15px;color:#607d87}h1{font-size:30px;margin:4px 0 12px}.body{font-size:27px;line-height:1.8;margin-top:60px}.cover{background:#17323b;color:white}.cover h1{font-size:62px;margin-top:80px}.cover .body{font-size:30px}img{width:100%;height:465px;object-fit:contain}.finding{font-size:21px;margin:8px 0}.limit{font-size:16px;color:#586b75}details{font-size:17px;line-height:1.6}nav{position:fixed;bottom:8px;right:15px}button{font-size:18px;padding:8px 18px;margin:4px}@media print{@page{size:landscape;margin:8mm}section,section.active{display:block;break-after:page;width:100%;margin:0;min-height:0;height:180mm;padding:8mm}img{height:115mm}details,nav{display:none}.body{font-size:24px}.cover{print-color-adjust:exact}}'
 script='let i=0;const ss=[...document.querySelectorAll("section")];function show(n){i=Math.max(0,Math.min(ss.length-1,n));ss.forEach((s,j)=>s.classList.toggle("active",i===j));location.hash=i+1;}document.onkeydown=e=>{if(e.key==="ArrowRight")show(i+1);if(e.key==="ArrowLeft")show(i-1);if(e.key.toLowerCase()==="p")print();};show(Number(location.hash.slice(1)||1)-1);'
 (out/'Presentation.html').write_text('<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Traffic Re:View Final V5</title><style>'+style+'</style>'+''.join(sections)+'<nav><button onclick="show(i-1)">←</button><button onclick="show(i+1)">→</button><button onclick="print()">PDF / Print</button></nav><script>'+script+'</script></html>',encoding='utf-8')
 assert sum(trans.units)==len(idx)
 assert all(hist[e].sum()==len(idx) for e in PE[1:])
 assert np.allclose(mix[P].sum(),100)
 assert all(np.allclose(w[p]/w[P[0]]*100,idx[p]) for p in P)
 assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
 (out/'manifest.json').write_text(json.dumps(safe(dict(version='5.0',status='complete',stats=stats,graphs=len(graphs),slides=len(slides),source_analysis_run=run.name)),ensure_ascii=False,indent=2),encoding='utf-8')
 return out

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--audited-run');parser.add_argument('--output-parent');args=parser.parse_args()
 print(build(args.input,args.audited_run,args.output_parent))
