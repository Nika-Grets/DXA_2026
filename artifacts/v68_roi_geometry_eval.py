import sys,json
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score,confusion_matrix
sys.path.insert(0,str(Path('/mnt/data/v68/dxa_v66_work/v64/backend')));sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study
from app.ml.hip_localizer import localize_hip
from mini_dicom import read_meta,read_pixels
ROOT=Path('/mnt/data/v68/dxa_v66_work/v64');TRAIN=Path('/mnt/data/train_v68');STUDY=next(TRAIN.glob('#U0418*'));M=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text());BY={s['study_uid']:s for s in M['studies']};by={}
for p in STUDY.rglob('*.dcm'):
 try:
  m,_=read_meta(p);u=m.get((0x0020,0x000d));s=m.get((0x0008,0x0018))
  if u in BY:by.setdefault(u,[]).append((s,p,m))
 except:pass
for u in by:by[u].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
rows=[]
for u,s in BY.items():
 ims=[read_pixels(p)[0] for _,p,_ in by[u]]; preds=classify_study(ims)
 for side,pc,rc in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
  if s['labels'].get(rc) is None:continue
  pp=[p for p in preds if p.region=='femur_'+side]
  if not pp:continue
  loc=localize_hip(ims[pp[0].image_index],side); lm,tm,rm,bm=loc.physical_margin_mm; lat=rm if side=='right' else lm
  # positive risk: any mandatory margin is below the threshold. continuous severity is max deficit in mm.
  risk=max(30-tm,30-bm,20-lat)
  rows.append({'study':u,'side':side,'y':int(s['labels'][rc]),'risk':float(risk),'margins':[lm,tm,rm,bm]})
y=np.array([r['y'] for r in rows]); risk=np.array([r['risk'] for r in rows]); pred=risk>0
print('n',len(y),'pos',int(y.sum()),'risk>0',int(pred.sum()),'cm',confusion_matrix(y,pred).tolist())
print('auc',roc_auc_score(y,risk),'ap',average_precision_score(y,risk))
for t in [0,2,5,10,15,20,30,40,50]:
 p=risk>=t; tp=((p)&(y==1)).sum();fn=((~p)&(y==1)).sum();tn=((~p)&(y==0)).sum();fp=((p)&(y==0)).sum();sens=tp/(tp+fn) if tp+fn else 0;spec=tn/(tn+fp) if tn+fp else 0
 print(t,'sens',round(sens,3),'spec',round(spec,3),'tp/fp',tp,fp)
