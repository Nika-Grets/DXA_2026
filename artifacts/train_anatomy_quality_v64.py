import sys,json,cv2
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score,f1_score,balanced_accuracy_score,confusion_matrix
from openpyxl import load_workbook
sys.path.insert(0,'/mnt/data/v64/backend')
from app.ml.dexa_baseline import classify_study,_normalize
from app.ml.hip_localizer import localize_hip
ROOT=[p for p in Path('/mnt/data/dexa_raw').iterdir() if p.is_dir()][0];CACHE=Path('/mnt/data/work_spine/dcm_cache');mp=json.load(open('/mnt/data/work_spine/dcm_path_hash.json'));split=json.load(open('/mnt/data/v63/artifacts/study_split.json'))['split'];ws=load_workbook(next(Path('/mnt/data/dexa_raw').glob('*.xlsx')),data_only=True).active

def features(a,loc,side):
 x=_normalize(a);h,w=x.shape;bx,by,bw,bh=loc.bone_bbox
 # canonicalize left to right: mirror x for left side.
 if side=='left': x=np.fliplr(x); bx=1-(bx+bw)
 # crop around proximal candidate with context, pad with zeros.
 pad_x=.45*bw;pad_y=.55*bh
 x0=max(0,int((bx-pad_x)*w));x1=min(w,int((bx+bw+pad_x)*w));y0=max(0,int((by-pad_y)*h));y1=min(h,int((by+bh+pad_y)*h))
 crop=x[y0:y1,x0:x1]
 crop=cv2.resize(crop,(32,48),interpolation=cv2.INTER_AREA)
 # low-dimensional geometry; use available physical margins as descriptive features only.
 g=np.array([loc.confidence,loc.shaft_score,bx,by,bw,bh,1-(bx+bw),1-(by+bh)],dtype=np.float32)
 return np.concatenate([crop.ravel().astype(np.float32),g])
rows=[]
for r in ws.iter_rows(min_row=3,values_only=True):
 if not r[1] or str(r[1]) not in split:continue
 ims=[];seen=set()
 for fp in sorted((ROOT/str(r[1])).rglob('*.dcm')):
  k=mp.get(str(fp));
  if k and k not in seen:seen.add(k);ims.append(np.load(CACHE/f'{k}.npy').astype(np.float32))
 for side,poscol,roicol in [('right',5,6),('left',7,8)]:
  if r[poscol] is None:continue
  for pr in classify_study(ims):
   if pr.region==f'femur_{side}':
    loc=localize_hip(ims[pr.image_index],side); f=features(ims[pr.image_index],loc,side)
    rows.append({'study':str(r[1]),'side':side,'pos':int(r[poscol]),'roi':None if r[roicol] is None else int(r[roicol]),'f':f});break
for target in ['pos','roi']:
 data=[z for z in rows if z[target] is not None]; tr=[z for z in data if split[z['study']]=='train'];va=[z for z in data if split[z['study']]=='validation']
 Xtr=np.stack([z['f'] for z in tr]);ytr=np.array([z[target] for z in tr]);Xv=np.stack([z['f'] for z in va]);yv=np.array([z[target] for z in va])
 print('\n',target,'train',len(ytr),'pos',ytr.sum(),'val',len(yv),'pos',yv.sum())
 if ytr.sum()<2 or (ytr==0).sum()<2:continue
 model=make_pipeline(StandardScaler(),LogisticRegression(C=.03,class_weight='balanced',max_iter=3000));model.fit(Xtr,ytr);p=model.predict_proba(Xv)[:,1];pred=p>=.5
 print('auc',round(roc_auc_score(yv,p),3) if len(np.unique(yv))>1 else 'NA','f1',round(f1_score(yv,pred,zero_division=0),3),'bal',round(balanced_accuracy_score(yv,pred),3),'cm',confusion_matrix(yv,pred).tolist())
 np.savez('/mnt/data/v64/artifacts/anatomy_quality_'+target+'.npz',coef=model[-1].coef_,intercept=model[-1].intercept_,mean=model[0].mean_,scale=model[0].scale_)
