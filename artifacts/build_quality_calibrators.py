from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score

ROOT=Path(__file__).resolve().parents[1]
OOF=ROOT/'artifacts/v68_oof/oof_predictions.json'
OUT=ROOT/'artifacts/models/quality_calibrators.json'
D=json.loads(OOF.read_text())
result={}
for name,d in D.items():
    y=np.asarray(d['y'],dtype=int)
    p=np.clip(np.asarray(d['p'],dtype=float),1e-6,1-1e-6)
    x=np.log(p/(1-p)).reshape(-1,1)
    cal=LogisticRegression(C=1.0,solver='lbfgs',max_iter=2000,class_weight=None)
    cal.fit(x,y)
    a=float(cal.coef_[0,0]); b=float(cal.intercept_[0])
    pc=1/(1+np.exp(-(a*x[:,0]+b)))
    result[name]={
        'method':'platt_logit', 'coef':a, 'intercept':b,
        'n':int(len(y)), 'positive':int(y.sum()),
        'oof_raw_brier':float(brier_score_loss(y,p)),
        'oof_calibrated_brier':float(brier_score_loss(y,pc)),
        'oof_raw_auc':float(roc_auc_score(y,p)),
        'oof_calibrated_auc':float(roc_auc_score(y,pc)),
        'oof_raw_ap':float(average_precision_score(y,p)),
        'oof_calibrated_ap':float(average_precision_score(y,pc)),
        'note':'Calibration fit on leakage-safe OOF predictions; metrics are in-sample for the calibration mapping and are diagnostic, not independent validation.'
    }
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(json.dumps(result,indent=2))
