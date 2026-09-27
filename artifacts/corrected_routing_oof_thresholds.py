from pathlib import Path
import json, warnings
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score, confusion_matrix
ROOT=Path('/mnt/data/dxa_work'); OUT=ROOT/'artifacts/corrected_routing_oof'
rows=json.loads((OUT/'rows.json').read_text()); z=np.load(OUT/'features.npz')
criteria=['spine_position','spine_axis','spine_artifact']; results={}
for crit in criteria:
 rr=[(i,r) for i,r in enumerate(rows) if r['criterion']==crit]
 X=np.stack([z[f'row_{i}'] for i,r in rr]); y=np.array([r['y'] for i,r in rr]); groups=np.array([r['study'] for i,r in rr])
 cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42); oof=np.full(len(y),np.nan); chosen=[]
 for fold,(tr,va) in enumerate(cv.split(X,y,groups),1):
  model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,class_weight='balanced',max_iter=4000,random_state=42))
  with warnings.catch_warnings(): warnings.simplefilter('ignore'); model.fit(X[tr],y[tr])
  trp=model.predict_proba(X[tr])[:,1]; vp=model.predict_proba(X[va])[:,1]
  grid=np.unique(np.r_[np.linspace(.02,.98,97),np.quantile(trp,np.linspace(.05,.95,19))])
  fs=[f1_score(y[tr],trp>=t,zero_division=0) for t in grid]; best=float(grid[int(np.argmax(fs))]); chosen.append(best); oof[va]=vp>=best
 pred=oof.astype(int); tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
 results[crit]={'thresholds':chosen,'mean_threshold':float(np.mean(chosen)),'TP':int(tp),'TN':int(tn),'FP':int(fp),'FN':int(fn),'F1':float(f1_score(y,pred,zero_division=0)),'Sensitivity':float(tp/(tp+fn)) if tp+fn else None,'Specificity':float(tn/(tn+fp)) if tn+fp else None,'OOF_AUC':float(roc_auc_score(y, np.array([0 if np.isnan(v) else v for v in oof]))) if False else None}
print(json.dumps(results,indent=2))
(OUT/'threshold_diagnostic.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
