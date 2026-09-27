"""V6.8 leakage-safe OOF benchmark and model provenance builder."""
from __future__ import annotations
import sys, json, hashlib, warnings
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, balanced_accuracy_score, brier_score_loss
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend')); sys.path.insert(0,'/mnt/data')
from app.ml.dexa_baseline import classify_study, _benchmark_features
from mini_dicom import read_pixels, read_meta
TRAIN=Path('/mnt/data/train_v68'); STUDY_DIR=next(TRAIN.glob('#U0418*'))
MANIFEST=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text())
BY_UID={s['study_uid']:s for s in MANIFEST['studies']}
files=[]
for p in STUDY_DIR.rglob('*.dcm'):
    try:
        m,_=read_meta(p); uid=m.get((0x0020,0x000d)); sop=m.get((0x0008,0x0018))
        if uid in BY_UID: files.append((uid,sop,p,m))
    except Exception: pass
by_study={}
for uid,sop,p,m in files: by_study.setdefault(uid,[]).append((sop,p,m))
for uid in by_study: by_study[uid].sort(key=lambda z:(int(z[2].get((0x0020,0x0013),0) or 0),z[0] or ''))
cache={}
def load(uid):
    if uid not in cache: cache[uid]=[(sop,p,read_pixels(p)[0]) for sop,p,m in by_study[uid]]
    return cache[uid]
criterion_to_region={'spine_position':'spine','spine_axis':'spine','spine_artifact':'spine','right_posrot':'femur_right','right_roi':'femur_right','left_posrot':'femur_left','left_roi':'femur_left'}
rows=[]; missing=[]
for uid,s in BY_UID.items():
    ims=load(uid); preds=classify_study([a for _,_,a in ims])
    for crit,region in criterion_to_region.items():
        y=s['labels'].get(crit)
        if y is None: continue
        pp=[p for p in preds if p.region==region]
        if not pp: missing.append((uid,crit,[p.region for p in preds])); continue
        p=pp[0]; feat=_benchmark_features(ims[p.image_index][2]).ravel().astype(np.float32)
        rows.append({'study':uid,'criterion':crit,'y':int(y),'feature':feat,'image_uid':ims[p.image_index][0]})
out=ROOT/'artifacts'/'v68_oof'; out.mkdir(parents=True,exist_ok=True)
meta_rows=[{k:v for k,v in r.items() if k!='feature'} for r in rows]
(out/'rows.json').write_text(json.dumps(meta_rows,ensure_ascii=False,indent=2))
results={}; oof_all={}
for crit in criterion_to_region:
    rr=[r for r in rows if r['criterion']==crit]
    X=np.stack([r['feature'] for r in rr]); y=np.array([r['y'] for r in rr]); groups=np.array([r['study'] for r in rr])
    oof=np.full(len(y),np.nan); n_splits=min(5,len(np.unique(groups)))
    if len(np.unique(y))<2 or y.sum()<2 or (y==0).sum()<2 or n_splits<2:
        results[crit]={'n':int(len(y)),'positive':int(y.sum()),'status':'insufficient_class_support'}; continue
    cv=StratifiedGroupKFold(n_splits=n_splits,shuffle=True,random_state=42); fold_info=[]
    for fold,(tr,va) in enumerate(cv.split(X,y,groups),1):
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,class_weight='balanced',max_iter=4000,random_state=42))
        with warnings.catch_warnings(): warnings.simplefilter('ignore'); model.fit(X[tr],y[tr])
        oof[va]=model.predict_proba(X[va])[:,1]
        fold_info.append({'fold':fold,'train_n':int(len(tr)),'valid_n':int(len(va)),'train_pos':int(y[tr].sum()),'valid_pos':int(y[va].sum())})
    p=oof; pred=p>=.5
    results[crit]={'n':int(len(y)),'positive':int(y.sum()),'prevalence':float(y.mean()),'roc_auc_oof':float(roc_auc_score(y,p)),'pr_auc_oof':float(average_precision_score(y,p)),'f1_at_0_5':float(f1_score(y,pred,zero_division=0)),'balanced_accuracy_at_0_5':float(balanced_accuracy_score(y,pred)),'brier_oof':float(brier_score_loss(y,p)),'folds':fold_info,'status':'ok'}
    oof_all[crit]={'study':groups.tolist(),'y':y.tolist(),'p':p.tolist()}
    final=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,class_weight='balanced',max_iter=4000,random_state=42)); final.fit(X,y)
    import joblib; joblib.dump(final,ROOT/'artifacts/models'/f'{crit}.joblib')
for p in [ROOT/'artifacts/canonical_manifest.json',ROOT/'docs/ML_BASELINE_RESULTS.md']:
    if p.exists(): results.setdefault('provenance',{})[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'oof_predictions.json').write_text(json.dumps(oof_all,ensure_ascii=False,indent=2)); (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)); (out/'missing_routes.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2))
print(json.dumps({'files':len(files),'studies_indexed':len(by_study),'rows':len(rows),'missing_routes':len(missing),'results':results},ensure_ascii=False,indent=2))
