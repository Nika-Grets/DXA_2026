from __future__ import annotations
import json, numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'artifacts/v68_oof/results.json').read_text())
preds=json.loads((ROOT/'artifacts/v68_oof/oof_predictions.json').read_text())
rng=np.random.default_rng(42)
out={}
for crit,z in preds.items():
    studies=np.asarray(z['study']); y=np.asarray(z['y']); p=np.asarray(z['p'],float)
    uniq=np.unique(studies)
    auc=[]; ap=[]
    for _ in range(3000):
        sample=rng.choice(uniq,size=len(uniq),replace=True)
        idx=np.concatenate([np.flatnonzero(studies==u) for u in sample])
        yy=y[idx]; pp=p[idx]
        if len(np.unique(yy))<2: continue
        auc.append(roc_auc_score(yy,pp)); ap.append(average_precision_score(yy,pp))
    def ci(a): return [float(np.percentile(a,2.5)),float(np.percentile(a,97.5))] if a else None
    out[crit]={'n_bootstrap':len(auc),'roc_auc_95ci':ci(auc),'pr_auc_95ci':ci(ap)}
for crit,v in out.items(): data.setdefault(crit,{})['bootstrap_95ci']=v
(ROOT/'artifacts/v68_oof/results_with_ci.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
