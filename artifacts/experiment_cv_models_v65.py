import sys, json, cv2, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, balanced_accuracy_score, confusion_matrix
sys.path.insert(0, str(Path('/mnt/data/v6_4_work/v64/backend')))
from app.ml.dexa_baseline import classify_study, _normalize
from app.ml.hip_localizer import localize_hip

ROOT=Path('/mnt/data/dicom_original'); CACHE=Path('/mnt/data/dicom_cache')
images=pd.read_csv('/mnt/data/dexa_work/manifest/images.csv')
studies=pd.read_csv('/mnt/data/dexa_work/manifest/studies.csv')
# Fixed study split copied from checkpoint.
split=json.load(open('/mnt/data/v6_4_work/v64/artifacts/study_split.json'))['split']

# image loader by manifest relative path; cache is keyed by pixel hash.
path_by_hash=dict(zip(images.pixel_hash, images.path_to_image))
# Map rel path -> cache hash
hash_by_path=dict(zip(images.path_to_image, images.pixel_hash))

def load_study(uid):
    rows=images[images.study_folder_uid==uid].drop_duplicates('pixel_hash').sort_values('instance_number')
    arr=[]
    for _,r in rows.iterrows():
        arr.append(np.load(CACHE/f"{r.pixel_hash}.npy").astype(np.float32))
    return arr

def hip_features(img, loc, side):
    x=_normalize(img); h,w=x.shape
    bx,by,bw,bh=loc.bone_bbox
    if side=='left':
        x=np.fliplr(x); bx=1-(bx+bw)
    pad_x=.45*bw; pad_y=.55*bh
    x0=max(0,int((bx-pad_x)*w)); x1=min(w,int((bx+bw+pad_x)*w))
    y0=max(0,int((by-pad_y)*h)); y1=min(h,int((by+bh+pad_y)*h))
    crop=x[y0:y1,x0:x1]
    crop=cv2.resize(crop.astype(np.float32),(48,64),interpolation=cv2.INTER_AREA).astype(np.float32)
    gx=cv2.Sobel(crop,cv2.CV_32F,1,0,ksize=3); gy=cv2.Sobel(crop,cv2.CV_32F,0,1,ksize=3)
    mag=cv2.magnitude(gx,gy)
    # HOG-like fixed descriptor via HOG implementation.
    hog=cv2.HOGDescriptor((48,64),(16,16),(8,8),(8,8),9)
    hd=hog.compute((crop*255).astype(np.uint8)).ravel().astype(np.float32)
    geom=np.array([loc.confidence,loc.shaft_score,bx,by,bw,bh,1-(bx+bw),1-(by+bh),
                   loc.physical_margin_mm[0]/100,loc.physical_margin_mm[1]/100,
                   loc.physical_margin_mm[2]/100,loc.physical_margin_mm[3]/100],np.float32)
    return np.concatenate([hd, geom])

rows=[]
for _,s in studies.iterrows():
    uid=str(s.path_to_study)
    if uid not in split: continue
    imgs=load_study(uid)
    preds=classify_study(imgs)
    for side,poscol,roicol in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
        pos=s[poscol]; roi=s[roicol]
        if pd.isna(pos): continue
        target_region='femur_'+side
        pp=[p for p in preds if p.region==target_region]
        if not pp: continue
        p=pp[0]
        loc=localize_hip(imgs[p.image_index],side)
        rows.append(dict(study=uid,side=side,pos=int(pos),roi=(None if pd.isna(roi) else int(roi)),f=hip_features(imgs[p.image_index],loc,side)))


def fit_eval(data,target):
    data=[r for r in data if r[target] is not None]
    tr=[r for r in data if split[r['study']]=='train']; va=[r for r in data if split[r['study']]=='validation']
    Xtr=np.stack([r['f'] for r in tr]); ytr=np.array([r[target] for r in tr]); groups=np.array([r['study'] for r in tr])
    Xv=np.stack([r['f'] for r in va]); yv=np.array([r[target] for r in va])
    print(f'\n{target}: train n={len(ytr)} pos={ytr.sum()} | val n={len(yv)} pos={yv.sum()}')
    if len(np.unique(yv))<2 or ytr.sum()<4 or (ytr==0).sum()<4:
        print('insufficient class support'); return
    # Candidate models; selection only on train using group-aware CV.
    candidates=[]
    for C in [0.03,0.1,0.3,1.0]:
        candidates.append((f'log_C{C}', make_pipeline(StandardScaler(),LogisticRegression(C=C,class_weight='balanced',max_iter=4000))))
    for C in [0.3,1,3,10]:
        for gamma in ['scale',0.001,0.01]:
            candidates.append((f'rbf_C{C}_g{gamma}', make_pipeline(StandardScaler(),SVC(C=C,gamma=gamma,class_weight='balanced',probability=True,random_state=42))))
    gkf=GroupKFold(n_splits=min(5,len(np.unique(groups))))
    scores=[]
    for name,m in candidates:
        aucs=[]
        for ti,vi in gkf.split(Xtr,ytr,groups):
            if len(np.unique(ytr[ti]))<2 or len(np.unique(ytr[vi]))<2: continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); m.fit(Xtr[ti],ytr[ti]); p=m.predict_proba(Xtr[vi])[:,1]
            aucs.append(roc_auc_score(ytr[vi],p))
        scores.append((np.mean(aucs) if aucs else -np.inf,name,m,aucs))
    scores.sort(key=lambda z:z[0],reverse=True)
    for sc,name,_,aucs in scores[:5]: print(' CV',name,'mean_auc',round(sc,3),'folds',[round(x,3) for x in aucs])
    _,name,m,_=scores[0]; m.fit(Xtr,ytr); p=m.predict_proba(Xv)[:,1]
    # report threshold-independent and fixed 0.5 metrics; no threshold tuning on validation.
    pred=p>=.5
    print(' SELECT',name,'VAL auc',round(roc_auc_score(yv,p),3),'AP',round(average_precision_score(yv,p),3),'F1@.5',round(f1_score(yv,pred,zero_division=0),3),'BA@.5',round(balanced_accuracy_score(yv,pred),3),'CM',confusion_matrix(yv,pred).tolist())
    return name,m

for target in ['pos','roi']:
    fit_eval(rows,target)
