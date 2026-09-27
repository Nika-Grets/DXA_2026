from __future__ import annotations
import sys,json,cv2,warnings
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,average_precision_score
sys.path.insert(0,str(Path('/mnt/data/v68/dxa_v66_work/v64/backend'))); sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study,_normalize
from app.ml.hip_localizer import localize_hip,_candidate_mask,_shaft_candidate
from mini_dicom import read_meta,read_pixels
ROOT=Path('/mnt/data/v68/dxa_v66_work/v64'); TRAIN=Path('/mnt/data/train_v68'); STUDY_DIR=next(TRAIN.glob('#U0418*'))
manifest=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text()); BY={s['study_uid']:s for s in manifest['studies']}
files=[]
for p in STUDY_DIR.rglob('*.dcm'):
    try:
        m,_=read_meta(p); uid=m.get((0x0020,0x000d)); sop=m.get((0x0008,0x0018))
        if uid in BY: files.append((uid,sop,p,m))
    except: pass
by={}
for uid,sop,p,m in files: by.setdefault(uid,[]).append((sop,p,m))
for uid in by: by[uid].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
cache={}
def load(uid):
    if uid not in cache: cache[uid]=[(sop,read_pixels(p)[0]) for sop,p,m in by[uid]]
    return cache[uid]

def anatomy_features(img,side):
    x=_normalize(img); h,w=x.shape; loc=localize_hip(x,side); bx,by,bw,bh=loc.bone_bbox
    mask=_candidate_mask(x); shaft=_shaft_candidate(mask,x,side)
    if shaft is None: return None
    score,cx,sty,sbw,sbh=shaft
    # canonical proximal coordinate frame: x relative to shaft center; y=0 at shaft top.
    # mirror left so lateral direction is consistently +x.
    xx=(x if side=='right' else np.fliplr(x)).astype(np.float32); cx=w-cx if side=='left' else cx
    gx=cv2.Sobel(xx,cv2.CV_32F,1,0,ksize=3); gy=cv2.Sobel(xx,cv2.CV_32F,0,1,ksize=3)
    mag=cv2.magnitude(gx,gy)
    # sample anatomy in a shaft-anchored window: 0.55w x 0.42h around proximal end.
    x0=max(0,int(cx-0.28*w)); x1=min(w,int(cx+0.28*w)); y0=max(0,int(sty-0.34*h)); y1=min(h,int(sty+0.22*h))
    crop=xx[y0:y1,x0:x1]; gm=mag[y0:y1,x0:x1]
    if crop.size<100: return None
    crop=cv2.resize(crop,(40,48),interpolation=cv2.INTER_AREA); gm=cv2.resize(gm,(40,48),interpolation=cv2.INTER_AREA)
    # anatomical coordinate summaries, not fixed image fractions.
    feats=[]
    q=np.percentile(crop,[60,70,80,90])
    for t in q:
        m=crop>=t; yy,xx2=np.nonzero(m)
        if len(xx2)>5:
            feats += [xx2.mean()/40, yy.mean()/48, xx2.std()/40, yy.std()/48, len(xx2)/m.size]
        else: feats += [0]*5
    # horizontal profiles capture neck/head expansion and shaft continuity.
    m=crop>=np.percentile(crop,78)
    for a,b in [(0,.20),(.20,.40),(.40,.60),(.60,.80),(.80,1.0)]:
        ya=int(a*48); yb=max(ya+1,int(b*48)); sub=m[ya:yb]; ys,xs=np.nonzero(sub)
        if len(xs): feats += [xs.mean()/40,xs.std()/40,len(xs)/(sub.size)]
        else: feats += [0,0,0]
    # orientation and gradient asymmetry in canonical frame.
    cov=np.cov(np.stack(np.nonzero(m))) if m.sum()>10 else np.eye(2)
    vals=np.linalg.eigvalsh(cov); vals=np.sort(vals)
    feats += [float(vals[0]/max(vals[1],1e-6)), float(np.mean(gm)), float(np.std(gm))]
    geom=[loc.confidence,loc.shaft_score,bx,by,bw,bh,1-(bx+bw),1-(by+bh),cx/w,sty/h,sbw/w,sbh/h]
    return np.asarray(feats+geom,dtype=np.float32)

rows=[]; missing=[]
for uid,s in BY.items():
    ims=load(uid); preds=classify_study([a for _,a in ims])
    for side,pc,rc in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
        if s['labels'].get(pc) is None: continue
        pp=[p for p in preds if p.region=='femur_'+side]
        if not pp: missing.append((uid,side,'route')); continue
        feat=anatomy_features(ims[pp[0].image_index][1],side)
        if feat is None: missing.append((uid,side,'feature')); continue
        rows.append({'study':uid,'side':side,'pos':s['labels'][pc],'roi':s['labels'][rc],'f':feat})

out=ROOT/'artifacts'/'v68_anatomy'; out.mkdir(exist_ok=True)
results={}
for target in ['pos','roi']:
    data=[r for r in rows if r[target] is not None]; X=np.stack([r['f'] for r in data]); y=np.array([r[target] for r in data]); g=np.array([r['study'] for r in data])
    oof=np.full(len(y),np.nan); folds=[]
    if len(np.unique(y))<2 or y.sum()<2 or (y==0).sum()<2:
        results[target]={'n':len(y),'positive':int(y.sum()),'status':'insufficient'}; continue
    cv=StratifiedGroupKFold(n_splits=min(5,len(np.unique(g))),shuffle=True,random_state=42)
    for fold,(tr,va) in enumerate(cv.split(X,y,g),1):
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=4000,random_state=42))
        with warnings.catch_warnings(): warnings.simplefilter('ignore'); model.fit(X[tr],y[tr])
        oof[va]=model.predict_proba(X[va])[:,1]
        folds.append({'fold':fold,'train_n':len(tr),'valid_n':len(va),'valid_pos':int(y[va].sum())})
    results[target]={'n':len(y),'positive':int(y.sum()),'roc_auc':float(roc_auc_score(y,oof)),'pr_auc':float(average_precision_score(y,oof)),'folds':folds}
    (out/f'oof_{target}.json').write_text(json.dumps({'study':g.tolist(),'y':y.tolist(),'p':oof.tolist()},ensure_ascii=False,indent=2))
(out/'results.json').write_text(json.dumps({'rows':len(rows),'missing':missing,'results':results},ensure_ascii=False,indent=2))
print(json.dumps({'rows':len(rows),'missing':missing,'results':results},ensure_ascii=False,indent=2))
