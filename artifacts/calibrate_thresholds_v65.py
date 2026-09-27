exec(open('/mnt/data/v6_4_work/v64/artifacts/experiment_cv_models_v65.py').read().split("for target in ['pos','roi']:")[0])
from sklearn.model_selection import GroupKFold

def threshold_eval(data,target):
    data=[r for r in data if r[target] is not None]
    tr=[r for r in data if split[r['study']]=='train']; va=[r for r in data if split[r['study']]=='validation']
    Xtr=np.stack([r['f'] for r in tr]); ytr=np.array([r[target] for r in tr]); groups=np.array([r['study'] for r in tr])
    Xv=np.stack([r['f'] for r in va]); yv=np.array([r[target] for r in va])
    print(f'\n{target}: train {len(ytr)} pos={ytr.sum()} | val {len(yv)} pos={yv.sum()}')
    model=make_pipeline(StandardScaler(), SVC(C=1,gamma='scale',class_weight='balanced',probability=True,random_state=42)) if target=='pos' else make_pipeline(StandardScaler(),LogisticRegression(C=.03,class_weight='balanced',max_iter=4000))
    gkf=GroupKFold(n_splits=5 if target=='pos' else 3)
    oof=np.full(len(ytr),np.nan)
    for ti,vi in gkf.split(Xtr,ytr,groups):
        if len(np.unique(ytr[ti]))<2: continue
        model.fit(Xtr[ti],ytr[ti]); oof[vi]=model.predict_proba(Xtr[vi])[:,1]
    valid=np.isfinite(oof)
    best=None
    for t in np.linspace(.05,.95,181):
        pred=oof[valid]>=t
        f=f1_score(ytr[valid],pred,zero_division=0); ba=balanced_accuracy_score(ytr[valid],pred)
        key=(f,ba)
        if best is None or key>best[0]: best=(key,t)
    model.fit(Xtr,ytr); pv=model.predict_proba(Xv)[:,1]
    t=best[1]; pred=pv>=t
    print('OOF selected threshold',round(t,3),'OOF F1/BA',tuple(round(x,3) for x in best[0]))
    print('VAL AUC',round(roc_auc_score(yv,pv),3),'AP',round(average_precision_score(yv,pv),3),'F1',round(f1_score(yv,pred,zero_division=0),3),'BA',round(balanced_accuracy_score(yv,pred),3),'CM',confusion_matrix(yv,pred).tolist())
    return t

for target in ['pos','roi']:
    threshold_eval(rows,target)
