from __future__ import annotations
import sys,json,cv2,warnings
from pathlib import Path
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,average_precision_score
sys.path.insert(0,'/mnt/data/v68_2_work/v64/backend')
sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study,_normalize
from app.ml.hip_localizer import localize_hip,_candidate_mask,_shaft_candidate
from mini_dicom import read_meta,read_pixels
ROOT=Path('/mnt/data/v68_2_work/v64'); TRAIN=Path('/mnt/data/train_v68')
manifest=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text()); BY={s['study_uid']:s for s in manifest['studies']}
files=[]
for p in TRAIN.rglob('*.dcm'):
    try:
        m,_=read_meta(p); uid=m.get((0x0020,0x000d)); sop=m.get((0x0008,0x0018))
        if uid in BY: files.append((uid,sop,p,m))
    except Exception: pass
by={}
for uid,sop,p,m in files: by.setdefault(uid,[]).append((sop,p,m))
for uid in by: by[uid].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
cache={}
def load(uid):
    if uid not in cache: cache[uid]=[(sop,read_pixels(p)[0]) for sop,p,m in by[uid]]
    return cache[uid]

def landmark_features(img,side):
    x=_normalize(img); h,w=x.shape
    loc=localize_hip(x,side); shaft=_shaft_candidate(_candidate_mask(x),x,side)
    if shaft is None:return None
    _,sx,sty,sbw,sbh=shaft
    # canonical mirror: lateral side always +x
    z=x if side=='right' else np.fliplr(x); sx=w-sx if side=='left' else sx
    # proximal search window around shaft top
    x0=max(0,int(sx-.24*w)); x1=min(w,int(sx+.30*w)); y0=max(0,int(sty-.32*h)); y1=min(h,int(sty+.20*h))
    crop=z[y0:y1,x0:x1]
    if crop.size<500:return None
    H,W=crop.shape
    # Bone mask with adaptive threshold + cleanup.
    q=float(np.percentile(crop,78)); m=(crop>=q).astype(np.uint8)
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    # Distance transform gives a candidate for a roughly circular head; restrict above shaft.
    dt=cv2.distanceTransform(m,cv2.DIST_L2,5)
    yy,xx=np.indices(dt.shape)
    valid=(yy < .72*H) & (xx > .10*W) & (xx < .92*W)
    if valid.any():
        d=dt.copy(); d[~valid]=0
        _,r,_,(hx,hy)=cv2.minMaxLoc(d)
    else:r=hx=hy=0
    # Connected component around the distance-transform maximum.
    head_area=0; head_w=head_h=0
    if r>2:
        hh=max(1,int(2.2*r)); xa=max(0,int(hx-hh)); xb=min(W,int(hx+hh)); ya=max(0,int(hy-hh)); yb=min(H,int(hy+hh))
        sub=m[ya:yb,xa:xb]
        n,lab,stats,cents=cv2.connectedComponentsWithStats(sub,8)
        if n>1:
            j=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA])); head_area=float(stats[j,cv2.CC_STAT_AREA]); head_w=float(stats[j,cv2.CC_STAT_WIDTH]); head_h=float(stats[j,cv2.CC_STAT_HEIGHT])
    # Row-wise widths in canonical proximal region. A head should produce a broad
    # expansion followed by a narrower neck toward the shaft.
    widths=[]; centers=[]; ys=[]
    for y in range(int(.12*H),int(.88*H)):
        xs=np.where(m[y]>0)[0]
        if xs.size>=3:
            lo,hi=xs.min(),xs.max(); widths.append((hi-lo+1)/W); centers.append(((lo+hi)/2)/W); ys.append(y/H)
    widths=np.asarray(widths); centers=np.asarray(centers); ys=np.asarray(ys)
    if widths.size:
        imax=int(np.argmax(widths)); maxw=float(widths[imax]); y_max=float(ys[imax]);
        # local minimum after the broadest point (neck waist)
        tail=np.arange(imax+1,len(widths))
        if tail.size:
            j=int(tail[np.argmin(widths[tail])]); neckw=float(widths[j]); y_neck=float(ys[j]); neckc=float(centers[j])
        else:neckw=maxw;y_neck=y_max;neckc=float(centers[imax])
        meanw=float(widths.mean()); p90=float(np.percentile(widths,90)); spread=float(widths.std())
    else:maxw=y_max=neckw=y_neck=neckc=meanw=p90=spread=0.0
    # Lateral protrusion cue (greater trochanter proxy): max right-side extent relative to centerline.
    lat=[]
    for y in range(int(.25*H),int(.82*H)):
        xs=np.where(m[y]>0)[0]
        if xs.size: lat.append((xs.max()/W, xs.min()/W))
    if lat:
        la=np.asarray(lat); maxlat=float(la[:,0].max()); minlat=float(la[:,1].min())
    else:maxlat=minlat=0.0
    # Orientation of candidate proximal mask via PCA.
    pts=np.column_stack(np.nonzero(m))
    if len(pts)>10:
        cov=np.cov(pts[:,[1,0]].T); ev=np.linalg.eigvalsh(cov); anis=float(ev[0]/max(ev[1],1e-6))
    else:anis=0.0
    # geometry relative to shaft and image, all normalized
    f=[r/W, hx/W, hy/H, head_area/(W*H), head_w/W, head_h/H,
       maxw, neckw, maxw/max(neckw,1e-4), y_max, y_neck, y_neck-y_max,
       meanw,p90,spread,maxlat,minlat,anis,
       loc.confidence,loc.shaft_score, sx/w, sty/h, sbw/w, sbh/h,
       (sx/w-loc.bone_center[0]), (sty/h-loc.bone_center[1])]
    return np.asarray(f,dtype=np.float32)

rows=[]; missing=[]
for uid,s in BY.items():
    ims=load(uid); preds=classify_study([a for _,a in ims])
    for side,pc,rc in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
        if s['labels'].get(pc) is None:continue
        pp=[p for p in preds if p.region==f'femur_{side}']
        if not pp:missing.append((uid,side,'route'));continue
        f=landmark_features(ims[pp[0].image_index][1],side)
        if f is None:missing.append((uid,side,'feature'));continue
        rows.append({'study':uid,'side':side,'pos':s['labels'][pc],'roi':s['labels'][rc],'f':f})
out=ROOT/'artifacts'/'v68_landmarks';out.mkdir(exist_ok=True)
results={}
for target in ['pos','roi']:
    data=[r for r in rows if r[target] is not None];X=np.stack([r['f'] for r in data]);y=np.array([r[target] for r in data]);g=np.array([r['study'] for r in data])
    if y.sum()<2 or (y==0).sum()<2:results[target]={'status':'insufficient','n':len(y),'positive':int(y.sum())};continue
    cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42);oof=np.full(len(y),np.nan)
    for tr,va in cv.split(X,y,g):
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=4000,random_state=42))
        with warnings.catch_warnings():warnings.simplefilter('ignore');model.fit(X[tr],y[tr])
        oof[va]=model.predict_proba(X[va])[:,1]
    results[target]={'n':len(y),'positive':int(y.sum()),'roc_auc':float(roc_auc_score(y,oof)),'pr_auc':float(average_precision_score(y,oof))}
    (out/f'oof_{target}.json').write_text(json.dumps({'study':g.tolist(),'side':[r['side'] for r in data],'y':y.tolist(),'p':oof.tolist()},ensure_ascii=False,indent=2))
# feature-by-feature univariate AUC
uni={}
for j in range(rows[0]['f'].size):
    for target in ['pos','roi']:
        data=[r for r in rows if r[target] is not None];y=np.array([r[target] for r in data]);s=np.array([r['f'][j] for r in data])
        if y.sum()>0 and (y==0).sum()>0:
            a=roc_auc_score(y,s);uni.setdefault(str(j),{})[target]=float(max(a,1-a))
(out/'results.json').write_text(json.dumps({'rows':len(rows),'missing':missing,'results':results,'univariate_best':uni},ensure_ascii=False,indent=2))
print(json.dumps({'rows':len(rows),'missing':missing,'results':results,'univariate_best':uni},ensure_ascii=False,indent=2))
