import sys,json,warnings
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
sys.path.insert(0,str(Path('/mnt/data/v68/dxa_v66_work/v64/backend')));sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study,_benchmark_features
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
 for crit,reg in [('spine_position','spine'),('spine_axis','spine'),('spine_artifact','spine'),('right_posrot','femur_right'),('right_roi','femur_right'),('left_posrot','femur_left'),('left_roi','femur_left')]:
  y=s['labels'].get(crit)
  if y is None:continue
  pp=[p for p in preds if p.region==reg]
  if not pp:continue
  rows.append({'study':u,'criterion':crit,'y':int(y),'x':_benchmark_features(ims[pp[0].image_index]).ravel()})
res={}
for crit in sorted(set(r['criterion'] for r in rows)):
 rr=[r for r in rows if r['criterion']==crit];X=np.stack([r['x'] for r in rr]);y=np.array([r['y'] for r in rr]);g=np.array([r['study'] for r in rr]);
 oof=np.full(len(y),np.nan);cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42)
 for tr,va in cv.split(X,y,g):
  base=make_pipeline(StandardScaler(),LogisticRegression(C=1,class_weight='balanced',max_iter=4000,random_state=42))
  # calibration folds are only within the training partition; for very rare ROI use 3-fold sigmoid.
  inner=3 if y[tr].sum()>=3 and (y[tr]==0).sum()>=3 else 2
  try:
   cal=CalibratedClassifierCV(base,method='sigmoid',cv=inner,n_jobs=1)
   with warnings.catch_warnings():warnings.simplefilter('ignore');cal.fit(X[tr],y[tr])
   oof[va]=cal.predict_proba(X[va])[:,1]
  except Exception:
   with warnings.catch_warnings():warnings.simplefilter('ignore');base.fit(X[tr],y[tr]);oof[va]=base.predict_proba(X[va])[:,1]
 res[crit]={'n':len(y),'positive':int(y.sum()),'auc':float(roc_auc_score(y,oof)),'ap':float(average_precision_score(y,oof)),'brier':float(brier_score_loss(y,oof))}
print(json.dumps(res,indent=2))
(ROOT/'artifacts/v68_oof/calibration_experiment.json').write_text(json.dumps(res,indent=2))
