exec(open('/mnt/data/scale_experiment.py').read().split('records=[]')[0])
from app.ml.hip_localizer import localize_hip

def estimate_shaft_width2(x,cx):
    return estimate_shaft_width(x,cx)

def find_head_adaptive(image, shaft):
    if shaft is None: return None
    x=_normalize(image); h,w=x.shape; _,cx,shaft_top,sbw,sbh=shaft
    sw=estimate_shaft_width2(x,cx)
    if sw is None: return None
    y0=max(0,int(shaft_top-0.42*h)); y1=min(h,int(shaft_top+0.10*h)); x0=max(0,int(cx-.22*w)); x1=min(w,int(cx+.22*w))
    win=x[y0:y1,x0:x1]
    if win.size==0:return None
    win8=(np.clip(win,0,1)*255).astype(np.uint8); win8=cv2.GaussianBlur(win8,(5,5),0)
    min_r=max(4,int(.75*sw)); max_r=min(int(.22*w),max(min_r+3,int(3.0*sw)))
    circles=cv2.HoughCircles(win8,cv2.HOUGH_GRADIENT,dp=1.2,minDist=max(8,int(.7*sw)),param1=80,param2=18,minRadius=min_r,maxRadius=max_r)
    if circles is None:return None
    best=None
    for cxx,cyy,r in circles[0]:
      gx,gy=x0+cxx,y0+cyy
      ds=float(np.exp(-(((gx-cx)/(.18*w))**2)))
      hs=float(np.exp(-(((gy-(shaft_top-.10*h))/(.20*h))**2)))
      rs=float(np.exp(-(((r-1.5*sw)/(1.5*sw))**2)));
      sc=ds*hs*rs
      if best is None or sc>best[0]: best=(sc,gx,gy,r)
    return best

def localize_head_anchor(image,side):
    base=localize_hip(image,side); x=_normalize(image); m=_candidate_mask(x); shaft=_shaft_candidate(m,x,side); head=find_head_adaptive(image,shaft)
    info={"head_found":head is not None}
    if shaft is None or head is None:return base,info
    score,hx,hy,r=head; h,w=x.shape; info.update(head_score=score,head_xy=(hx/w,hy/h),head_r=r/w)
    if score<.25:return base,info
    bx,by,bw,bh=base.bone_bbox; bottom=by+bh; head_top=max(0.,(hy-1.6*r)/h); head_center=hy/h
    # Only correct when the baseline has a clear geometric disagreement with
    # the detected head: either the box starts substantially above the head
    # (ilium leak) or the head center lies above the box (zoomed/cropped view).
    if by < head_top-0.10:
        new_by=head_top
    elif head_center < by:
        new_by=head_top
    else:
        info['adjusted']=False; return base,info
    new_bh=bottom-new_by
    if new_bh<.08 or new_bh>.72 or abs(new_by-by)>.36:
        info['adjusted']=False; return base,info
    info['adjusted']=abs(new_by-by)>0.01
    return base.__class__(side=base.side,bone_bbox=(bx,new_by,bw,new_bh),roi_bbox=base.roi_bbox,bone_center=(bx+bw/2,new_by+new_bh/2),roi_margin_px=base.roi_margin_px,confidence=base.confidence,physical_margin_mm=base.physical_margin_mm,shaft_bbox=base.shaft_bbox,shaft_score=base.shaft_score),info

def feat2(img,loc,side): return feat(img,loc,side)

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

records=[]; cases=[]
for uid in SPLIT:
    imgs=load_unique(uid); preds=classify_study(imgs); lab=labels[uid]
    for side,poscol,roicol in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
        pos=lab.get(poscol); roi=lab.get(roicol)
        if pos is None: continue
        pp=[p for p in preds if p.region=='femur_'+side]
        if not pp: continue
        p=pp[0]; img=imgs[p.image_index]; b=localize_hip(img,side); a,info=localize_head_anchor(img,side)
        records.append(dict(study=uid,side=side,pos=int(pos),roi=None if roi is None else int(roi),fb=feat(img,b,side),fa=feat(img,a,side)))
        if uid.endswith('113784') or uid.endswith('968726'): cases.append((uid,side,info,b.bone_bbox,a.bone_bbox))
print('CASES',cases)
for t in ['pos','roi']:
 print('BASE',eval_model(records,t,'fb')); print('ADAPTIVE_HEAD',eval_model(records,t,'fa'))
