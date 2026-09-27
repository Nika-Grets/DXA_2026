import sys, json, joblib
from pathlib import Path
import numpy as np
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, f1_score, balanced_accuracy_score
sys.path.insert(0,str(Path('/mnt/data/v6_4_work/v64/artifacts')))
from feature_builder_v65 import rows, split
rows=[r for r in rows if r['pos'] is not None]
tr=[r for r in rows if split[r['study']]=='train']
X=np.stack([r['f'] for r in tr]); y=np.array([r['pos'] for r in tr]); groups=np.array([r['study'] for r in tr])
model=make_pipeline(StandardScaler(),SVC(C=1,gamma='scale',class_weight='balanced',probability=True,random_state=42))
oof=np.full(len(y),np.nan)
for ti,vi in GroupKFold(n_splits=5).split(X,y,groups):
    model.fit(X[ti],y[ti]); oof[vi]=model.predict_proba(X[vi])[:,1]
best=((-1,-1),None)
for t in np.linspace(.05,.95,181):
    pred=oof>=t; f=f1_score(y,pred,zero_division=0); ba=balanced_accuracy_score(y,pred)
    if (f,ba)>best[0]: best=((f,ba),float(t))
threshold=best[1]
model.fit(X,y)
out=Path('/mnt/data/v6_4_work/v64/artifacts/experimental_models'); out.mkdir(exist_ok=True)
joblib.dump(model,out/'hip_posrot_svc_v65.joblib')
meta={'model':'SVC RBF','C':1,'gamma':'scale','class_weight':'balanced','train_n':len(y),'train_positive':int(y.sum()),'study_level_group_cv':5,'oof_threshold':threshold,'oof_f1':best[0][0],'oof_balanced_accuracy':best[0][1],'status':'experimental_not_main_pipeline'}
json.dump(meta,open(out/'hip_posrot_svc_v65.json','w'),indent=2,ensure_ascii=False)
print(json.dumps(meta,indent=2))
