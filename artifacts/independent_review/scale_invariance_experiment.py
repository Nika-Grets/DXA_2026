import sys, glob, json, hashlib, os, warnings
from pathlib import Path
import numpy as np, cv2, pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, balanced_accuracy_score
sys.path.insert(0,'/mnt/data')
sys.path.insert(0,'/mnt/data/v65_inspect/v64/backend')
from mini_dcm import read_dcm
from app.ml.dexa_baseline import classify_study,_normalize
from app.ml.hip_localizer import localize_hip,_candidate_mask,_shaft_candidate,HipLocalization

ROOT=Path('/mnt/data/raw_dicom')
SPLIT=json.load(open('/mnt/data/v65_inspect/v64/artifacts/study_split.json'))['split']
MAN=json.load(open('/mnt/data/v65_inspect/v64/artifacts/study_manifest.json'))
labels={r['study_folder']:r['labels'] for r in MAN}

def files_for(uid):
    fs=glob.glob(str(ROOT)+f'/**/*{uid}/**/*.dcm',recursive=True)
    fs.sort(key=lambda x:int(Path(x).stem.replace('CR','')) if Path(x).stem.replace('CR','').isdigit() else 999)
    return fs

def load_unique(uid):
    out=[]; seen=set()
    for f in files_for(uid):
        a,_=read_dcm(f); h=hashlib.sha1(a.tobytes()).hexdigest()
        if h in seen: continue
        seen.add(h); out.append(a)
    return out

def estimate_shaft_width(x,cx):
    h,w=x.shape; widths=[]
    for y in range(int(.62*h), int(.95*h)):
        lo=max(0,int(cx-.18*w)); hi=min(w,int(cx+.18*w)); r=x[y,lo:hi]
        if r.size<8: continue
        thr=np.percentile(r,75); b=(r>=thr).astype(np.uint8); j=int(round(cx))-lo
        if not (0<=j<len(b)): continue
        if not b[j]:
            q=np.where(b[max(0,j-5):min(len(b),j+6)]>0)[0]
            if len(q)==0: continue
            j=max(0,j-5)+int(q[np.argmin(np.abs(q-(j-max(0,j-5))))])
        l=j
        while l>0 and b[l-1]: l-=1
        rr=j
        while rr+1<len(b) and b[rr+1]: rr+=1
        if rr-l+1>=3: widths.append(rr-l+1)
    if not widths: return None
    return float(np.median(widths))

def localize_scale(image,side):
    x=_normalize(image); h,w=x.shape; mask=_candidate_mask(x); shaft=_shaft_candidate(mask,x,side)
    if shaft is None: return localize_hip(image,side)
    score,cx,shaft_top,sbw,sbh=shaft
    sw=estimate_shaft_width(x,cx)
    if sw is None: return localize_hip(image,side)
    # Scale from actual visible shaft width, not full-frame height.
    search_up=float(np.clip(4.5*sw,0.20*h,0.45*h))
    search_down=float(np.clip(3.0*sw,0.10*h,0.22*h))
    local_top=max(0,int(round(shaft_top-search_up)))
    local_bottom=min(h,int(round(shaft_top+search_down)))
    band=max(6,int(0.09*w)); xa=max(0,int(cx-band)); xb=min(w,int(cx+band))
    col=x[:,xa:xb].mean(axis=1)
    ref=x[local_top:local_bottom,xa:xb]
    threshold=float(np.percentile(ref,72.0)) if ref.size else .7
    sig=(col>=threshold).astype(np.uint8)
    sig=cv2.morphologyEx(sig[:,None],cv2.MORPH_CLOSE,np.ones((11,1),np.uint8)).ravel()
    inds=np.where(sig[local_top:shaft_top+1]>0)[0]
    prox_top=local_top+int(inds[0]) if inds.size else max(0,int(round(shaft_top-0.30*search_up)))
    # prevent a single pelvic column from consuming the full search window
    prox_top=max(prox_top,int(round(shaft_top-search_up)))
    half_w=.18*w; bx=max(0.,float(cx-half_w)); bx1=min(float(w),float(cx+half_w))
    y0=max(0.,float(prox_top)-0.02*h); y1=min(float(h),float(shaft_top+search_down))
    if y1<=y0: y1=min(float(h),y0+max(0.15*h,3*sw))
    bw=(bx1-bx)/w; bh=(y1-y0)/h; by=y0/h; bx=bx/w
    left_mm=bx*w*.60; right_mm=(1-(bx+bw))*w*.60; top_mm=by*h*1.05; bottom_mm=(1-(by+bh))*h*1.05
    margin_x=20/.60; margin_y=30/1.05
    x0=max(0,bx*w-(margin_x if side=='left' else 0)); x1=min(w,(bx+bw)*w+(margin_x if side=='right' else 0))
    ry0=max(0,by*h-margin_y); ry1=min(h,(by+bh)*h+margin_y)
    roi=(x0/w,ry0/h,(x1-x0)/w,(ry1-ry0)/h)
    return HipLocalization(side=side,bone_bbox=(bx,by,bw,bh),roi_bbox=roi,bone_center=(bx+bw/2,by+bh/2),roi_margin_px=(left_mm/.6,top_mm/1.05,right_mm/.6,bottom_mm/1.05),confidence=float(np.clip(.35+.65*score,0,1)),physical_margin_mm=(left_mm,top_mm,right_mm,bottom_mm),shaft_bbox=(max(0,(cx-sbw/2)/w),shaft_top/h,sbw/w,sbh/h),shaft_score=float(score))

def feat(img,loc,side):
    x=_normalize(img); h,w=x.shape; bx,by,bw,bh=loc.bone_bbox
    if side=='left': x=np.fliplr(x); bx=1-(bx+bw)
    pad_x=.45*bw; pad_y=.55*bh; x0=max(0,int((bx-pad_x)*w)); x1=min(w,int((bx+bw+pad_x)*w)); y0=max(0,int((by-pad_y)*h)); y1=min(h,int((by+bh+pad_y)*h))
    crop=cv2.resize(x[y0:y1,x0:x1].astype(np.float32),(48,64),interpolation=cv2.INTER_AREA)
    hog=cv2.HOGDescriptor((48,64),(16,16),(8,8),(8,8),9).compute((crop*255).astype(np.uint8)).ravel().astype(np.float32)
    geom=np.array([loc.confidence,loc.shaft_score,bx,by,bw,bh,1-(bx+bw),1-(by+bh),loc.physical_margin_mm[0]/100,loc.physical_margin_mm[1]/100,loc.physical_margin_mm[2]/100,loc.physical_margin_mm[3]/100],np.float32)
    return np.concatenate([hog,geom])

records=[]; failures=[]
for uid in SPLIT:
    imgs=load_unique(uid); preds=classify_study(imgs); lab=labels[uid]
    for side,poscol,roicol in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
        pos=lab.get(poscol); roi=lab.get(roicol)
        if pos is None: continue
        region='femur_'+side; pp=[p for p in preds if p.region==region]
        if not pp: continue
        p=pp[0]; img=imgs[p.image_index]
        b=localize_hip(img,side); s=localize_scale(img,side)
        records.append(dict(study=uid,side=side,pos=int(pos),roi=(None if roi is None else int(roi)),fb=feat(img,b,side),fs=feat(img,s,side)))
        if uid.endswith('113784') or uid.endswith('968726'): failures.append((uid,side,p.image_index,b,s))
print('records',len(records),'failures',failures)

def eval_model(records, target, key):
    data=[r for r in records if r[target] is not None]
    tr=[r for r in data if SPLIT[r['study']]=='train']; va=[r for r in data if SPLIT[r['study']]=='validation']
    Xtr=np.stack([r[key] for r in tr]); ytr=np.array([r[target] for r in tr]); g=np.array([r['study'] for r in tr]); Xv=np.stack([r[key] for r in va]); yv=np.array([r[target] for r in va])
    cand=[]
    for C in [.03,.1,.3,1.]: cand.append((f'log{C}',make_pipeline(StandardScaler(),LogisticRegression(C=C,class_weight='balanced',max_iter=4000))))
    for C in [.3,1,3,10]:
      for gamma in ['scale',.001,.01]: cand.append((f'rbf{C}-{gamma}',make_pipeline(StandardScaler(),SVC(C=C,gamma=gamma,class_weight='balanced',probability=True))))
    gkf=GroupKFold(n_splits=min(5,len(np.unique(g))))
    scored=[]
    for name,m in cand:
      auc=[]
      for ti,vi in gkf.split(Xtr,ytr,g):
       if len(np.unique(ytr[ti]))<2 or len(np.unique(ytr[vi]))<2: continue
       with warnings.catch_warnings(): warnings.simplefilter('ignore'); m.fit(Xtr[ti],ytr[ti]); p=m.predict_proba(Xtr[vi])[:,1]
       auc.append(roc_auc_score(ytr[vi],p))
      scored.append((np.mean(auc),name,m,auc))
    scored.sort(reverse=True,key=lambda z:z[0]); sc,name,m,auc=scored[0]; m.fit(Xtr,ytr); p=m.predict_proba(Xv)[:,1]
    return dict(target=target,variant=key,train_n=len(ytr),train_pos=int(ytr.sum()),val_n=len(yv),val_pos=int(yv.sum()),model=name,cv_auc=float(sc),auc=float(roc_auc_score(yv,p)),ap=float(average_precision_score(yv,p)),f1=float(f1_score(yv,p>=.5,zero_division=0)),ba=float(balanced_accuracy_score(yv,p>=.5)))
for t in ['pos','roi']:
 print('BASE',eval_model(records,t,'fb')); print('SCALE',eval_model(records,t,'fs'))
