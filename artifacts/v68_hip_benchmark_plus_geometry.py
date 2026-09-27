import sys,json,cv2,warnings
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,average_precision_score
sys.path.insert(0,str(Path('/mnt/data/v68/dxa_v66_work/v64/backend')));sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study,_benchmark_features,_normalize
from app.ml.hip_localizer import localize_hip
from mini_dicom import read_meta,read_pixels
ROOT=Path('/mnt/data/v68/dxa_v66_work/v64'); TRAIN=Path('/mnt/data/train_v68'); STUDY_DIR=next(TRAIN.glob('#U0418*'))
M=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text()); BY={s['study_uid']:s for s in M['studies']}; by={}
for p in STUDY_DIR.rglob('*.dcm'):
 try:
  m,_=read_meta(p); uid=m.get((0x0020,0x000d)); sop=m.get((0x0008,0x0018))
  if uid in BY: by.setdefault(uid,[]).append((sop,p,m))
 except: pass
for u in by: by[u].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
cache={}
def load(u):
 if u not in cache: cache[u]=[(s,read_pixels(p)[0]) for s,p,m in by[u]]
 return cache[u]
def geom(img,side):
 loc=localize_hip(img,side); bx,by,bw,bh=loc.bone_bbox
 return np.array([loc.confidence,loc.shaft_score,bx,by,bw,bh,1-(bx+bw),1-(by+bh),*loc.physical_margin_mm],np.float32)
rows=[]
for u,s in BY.items():
 ims=load(u); preds=classify_study([a for _,a in ims])
 for side,pc,rc in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
  if s['labels'].get(pc) is None: continue
  pp=[p for p in preds if p.region=='femur_'+side]
  if not pp: continue
  img=ims[pp[0].image_index][1]
  rows.append({'study':u,'side':side,'pos':s['labels'][pc],'roi':s['labels'][rc], 'base':_benchmark_features(img).ravel(), 'geom':geom(img,side)})
out=ROOT/'artifacts/v68_anatomy';out.mkdir(exist_ok=True)
for target in ['pos','roi']:
 data=[r for r in rows if r[target] is not None]
 res={}
 for name,kind in [('base','base'),('plus','plus')]:
  X=np.stack([r['base'] if kind=='base' else np.r_[r['base'],r['geom']] for r in data]); y=np.array([r[target] for r in data]); g=np.array([r['study'] for r in data]); p=np.full(len(y),np.nan)
  cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42)
  for tr,va in cv.split(X,y,g):
   m=make_pipeline(StandardScaler(),LogisticRegression(C=1,class_weight='balanced',max_iter=4000,random_state=42));
   with warnings.catch_warnings():warnings.simplefilter('ignore');m.fit(X[tr],y[tr])
   p[va]=m.predict_proba(X[va])[:,1]
  res[name]={'roc_auc':float(roc_auc_score(y,p)),'pr_auc':float(average_precision_score(y,p))}
 (out/f'compare_{target}.json').write_text(json.dumps(res,indent=2))
 print(target,res)
