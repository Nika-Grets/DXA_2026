exec(open('/mnt/data/v6_4_work/v64/artifacts/experiment_cv_models_v65.py').read().split("rows=[]")[0])
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, balanced_accuracy_score

def geom_extra(img,loc):
    x=_normalize(img); h,w=x.shape
    bx,by,bw,bh=loc.bone_bbox
    x0=max(0,int(bx*w)); x1=min(w,int((bx+bw)*w)); y0=max(0,int(by*h)); y1=min(h,int((by+bh)*h))
    crop=x[y0:y1,x0:x1]
    if crop.size==0: return np.zeros(20,np.float32)
    mask=crop>np.percentile(crop,78)
    yy,xx=np.nonzero(mask)
    feats=[]
    if len(xx)>5:
        cov=np.cov(np.stack([xx,yy])); vals,vecs=np.linalg.eigh(cov); v=vecs[:,np.argmax(vals)]
        angle=np.degrees(np.arctan2(v[1],v[0])); angle=min(abs(angle),180-abs(angle))
        feats += [np.sin(np.radians(angle)), np.cos(np.radians(angle))]
        feats += [xx.mean()/crop.shape[1], yy.mean()/crop.shape[0], xx.std()/crop.shape[1], yy.std()/crop.shape[0]]
    else: feats += [0]*6
    # row-wise width/centroid profile, compact summary of neck/shaft shape
    for frac0,frac1 in [(0,.25),(.25,.5),(.5,.75),(.75,1.0)]:
        a=int(frac0*crop.shape[0]); b=max(a+1,int(frac1*crop.shape[0])); m=mask[a:b]
        ys,xs=np.nonzero(m)
        if len(xs): feats += [xs.mean()/crop.shape[1], xs.std()/crop.shape[1], len(xs)/(m.size)]
        else: feats += [0,0,0]
    return np.array(feats,dtype=np.float32)

def build_rows():
    out=[]
    for _,s in studies.iterrows():
        uid=str(s.path_to_study)
        if uid not in split: continue
        imgs=load_study(uid); preds=classify_study(imgs)
        for side,poscol,roicol in [('right','right_posrot','right_roi'),('left','left_posrot','left_roi')]:
            if pd.isna(s[poscol]): continue
            pp=[p for p in preds if p.region=='femur_'+side]
            if not pp: continue
            p=pp[0]; loc=localize_hip(imgs[p.image_index],side)
            base=hip_features(imgs[p.image_index],loc,side)
            extra=geom_extra(imgs[p.image_index],loc)
            out.append(dict(study=uid,side=side,pos=int(s[poscol]),roi=None if pd.isna(s[roicol]) else int(s[roicol]),f=np.concatenate([base,extra])))
    return out
rows=build_rows()
for target in ['pos','roi']:
    data=[r for r in rows if r[target] is not None]; tr=[r for r in data if split[r['study']]=='train']; va=[r for r in data if split[r['study']]=='validation']
    Xtr=np.stack([r['f'] for r in tr]); ytr=np.array([r[target] for r in tr]); g=np.array([r['study'] for r in tr]); Xv=np.stack([r['f'] for r in va]); yv=np.array([r[target] for r in va])
    print('\n',target,len(ytr),ytr.sum(),len(yv),yv.sum())
    if ytr.sum()<4: continue
    model=make_pipeline(StandardScaler(),SVC(C=1,gamma='scale',class_weight='balanced',probability=True,random_state=42))
    auc=[]
    for ti,vi in GroupKFold(n_splits=5 if target=='pos' else 3).split(Xtr,ytr,g):
        if len(np.unique(ytr[ti]))<2 or len(np.unique(ytr[vi]))<2: continue
        model.fit(Xtr[ti],ytr[ti]); auc.append(roc_auc_score(ytr[vi],model.predict_proba(Xtr[vi])[:,1]))
    model.fit(Xtr,ytr); p=model.predict_proba(Xv)[:,1]
    print('CV AUC',round(np.mean(auc),3),'VAL AUC',round(roc_auc_score(yv,p),3),'AP',round(average_precision_score(yv,p),3),'F1@.5',round(f1_score(yv,p>=.5,zero_division=0),3))
