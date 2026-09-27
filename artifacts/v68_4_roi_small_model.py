from __future__ import annotations
import json,sys,warnings,cv2
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,average_precision_score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'));sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study,_normalize
from app.ml.hip_localizer import localize_hip,_candidate_mask,_shaft_candidate
from mini_dicom import read_meta,read_pixels
ROOT=Path(__file__).resolve().parents[1]; TRAIN=Path('/mnt/data/train_v68'); STUDY_DIR=next(TRAIN.glob('#U0418*'))
M=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text()); BY={s['study_uid']:s for s in M['studies']}
by={}
for p in STUDY_DIR.rglob('*.dcm'):
    try:
        m,_=read_meta(p); uid=m.get((0x0020,0x000d)); sop=m.get((0x0008,0x0018))
        if uid in BY: by.setdefault(uid,[]).append((sop,p,m))
    except: pass
for uid in by: by[uid].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
cache={}
def load(uid):
    if uid not in cache: cache[uid]=[(sop,read_pixels(p)[0]) for sop,p,m in by[uid]]
    return cache[uid]

def features(img,side):
    x=_normalize(img); h,w=x.shape; loc=localize_hip(x,side); mask=_candidate_mask(x); shaft=_shaft_candidate(mask,x,side)
    if shaft is None:return None
    _,cx,sty,sbw,sbh=shaft
    xx=x if side=='right' else np.fliplr(x); cx=w-cx if side=='left' else cx
    x0=max(0,int(cx-.28*w)); x1=min(w,int(cx+.28*w)); y0=max(0,int(sty-.34*h)); y1=min(h,int(sty+.22*h))
    crop=xx[y0:y1,x0:x1]
    if crop.size<100:return None
    crop=cv2.resize(crop,(40,48),interpolation=cv2.INTER_AREA)
    out=[]
    for q in (60,70,80):
        m=crop>=np.percentile(crop,q); yy,xx2=np.nonzero(m)
        if len(xx2)>5: out += [xx2.std()/40, len(xx2)/m.size]
        else: out += [0.,0.]
    # q60 spread, q70 spread, q80 spread + occupied fraction
    # add normalized crop width/height from localizer as one anatomy-scale feature
    bx,by,bw,bh=loc.bone_bbox
    out += [bw, bh, loc.confidence, loc.shaft_score]
    return np.asarray(out,dtype=np.float32)

rows=[]
for uid,s in BY.items():
    ims=load(uid); preds=classify_study([a for _,a in ims])
    for side in ('right','left'):
        y=s['labels'].get(f'{side}_roi')
        if y is None:continue
        pp=[p for p in preds if p.region==f'femur_{side}']
        if not pp:continue
        f=features(ims[pp[0].image_index][1],side)
        if f is not None:rows.append({'study':uid,'side':side,'y':int(y),'f':f.tolist()})
X=np.array([r['f'] for r in rows]); y=np.array([r['y'] for r in rows]); g=np.array([r['study'] for r in rows])
cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42); oof=np.full(len(y),np.nan); folds=[]
for fold,(tr,va) in enumerate(cv.split(X,y,g),1):
    model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=4000,random_state=42))
    with warnings.catch_warnings():warnings.simplefilter('ignore');model.fit(X[tr],y[tr])
    oof[va]=model.predict_proba(X[va])[:,1]
    folds.append({'fold':fold,'train_n':len(tr),'valid_n':len(va),'valid_pos':int(y[va].sum()),'train_pos':int(y[tr].sum())})
r={'n':len(y),'positive':int(y.sum()),'features':['q60_sx','q60_occ','q70_sx','q70_occ','q80_sx','q80_occ','bbox_width','bbox_height','localizer_conf','shaft_score'],'roc_auc':float(roc_auc_score(y,oof)),'pr_auc':float(average_precision_score(y,oof)),'folds':folds}
# Bootstrap grouped CI
rng=np.random.default_rng(42); studies=np.unique(g); vals=[]
for _ in range(3000):
 ss=rng.choice(studies,len(studies),replace=True); idx=np.concatenate([np.where(g==s)[0] for s in ss])
 if len(np.unique(y[idx]))==2: vals.append(roc_auc_score(y[idx],oof[idx]))
r['bootstrap_95ci']=[float(x) for x in np.percentile(vals,[2.5,97.5])]
# Compare single q60_sx and best 2-feature candidates under same OOF protocol.
comparisons={}
for inds,name in [([0],'q60_sx'),([0,2],'q60_q70_sx'),([0,1],'q60_spread_occ'),([0,2,4],'q60_q70_q80_sx')]:
 oo=np.full(len(y),np.nan)
 for tr,va in cv.split(X,y,g):
  m=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=4000,random_state=42));m.fit(X[tr][:,inds],y[tr]);oo[va]=m.predict_proba(X[va][:,inds])[:,1]
 comparisons[name]={'roc_auc':float(roc_auc_score(y,oo)),'pr_auc':float(average_precision_score(y,oo))}
r['comparisons']=comparisons
out=ROOT/'artifacts/v68_4_roi';out.mkdir(exist_ok=True)
(out/'results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));(out/'records.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));(out/'oof.json').write_text(json.dumps({'study':g.tolist(),'side':[r['side'] for r in rows],'y':y.tolist(),'p':oof.tolist()},ensure_ascii=False,indent=2))
print(json.dumps(r,ensure_ascii=False,indent=2))
