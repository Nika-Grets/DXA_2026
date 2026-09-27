"""Leakage-safe OOF benchmark using the corrected current routing.

Diagnostic only: does not overwrite production .joblib heads.
Runs grouped OOF for the three spine criteria most affected by routing:
spine_position, spine_axis, spine_artifact.
"""
from __future__ import annotations
import json, hashlib, struct, warnings
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, balanced_accuracy_score, brier_score_loss, confusion_matrix
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study, _benchmark_features

DICOM_ROOT=ROOT/'.training_dicom'
MANIFEST=json.loads((ROOT/'artifacts/canonical_manifest.json').read_text(encoding='utf-8'))
BY_UID={s['study_uid']:s for s in MANIFEST['studies']}


def read_tag(data, off, endian='<'):
    return struct.unpack_from(endian+'HH', data, off)

def parse_meta(data):
    if data[128:132] != b'DICM': raise ValueError('missing DICM')
    off=132; out={}
    while off+8<=len(data):
        g,e=read_tag(data,off,'<')
        if g != 0x0002: break
        vr=data[off+4:off+6].decode('ascii','replace')
        if vr in ('OB','OD','OF','OL','OV','OW','SQ','UC','UN','UR'):
            l=struct.unpack_from('<I',data,off+8)[0]; vo=off+12
        else:
            l=struct.unpack_from('<H',data,off+6)[0]; vo=off+8
        out[(g,e)]=data[vo:vo+l]
        off=vo+l
    return off,out

def parse_body(data, off, endian='<', explicit=False):
    out={}; n=len(data)
    while off+8<=n:
        g,e=read_tag(data,off,endian); tag=(g,e)
        if explicit:
            vr=data[off+4:off+6].decode('ascii','replace')
            if vr in ('OB','OD','OF','OL','OV','OW','SQ','UC','UN','UR'):
                l=struct.unpack_from(endian+'I',data,off+8)[0]; vo=off+12
            else:
                l=struct.unpack_from(endian+'H',data,off+6)[0]; vo=off+8
        else:
            l=struct.unpack_from(endian+'I',data,off+4)[0]; vo=off+8
        if l==0xffffffff or vo+l>n: raise ValueError(f'unsupported/invalid element {tag} l={l}')
        out[tag]=data[vo:vo+l]
        off=vo+l
        if tag==(0x7fe0,0x0010): break
    return out

def text(v):
    return v.rstrip(b'\\ \x00').decode('ascii','replace') if v is not None else ''

def u16(v, endian='<'):
    return struct.unpack(endian+'H',v[:2])[0]

def pixels_from_bytes(path):
    data=path.read_bytes(); mo,meta=parse_meta(data)
    ts=text(meta.get((0x0002,0x0010)))
    if ts not in ('1.2.840.10008.1.2', ''):
        raise ValueError(f'unsupported transfer syntax {ts}')
    body=parse_body(data,mo,'<',False)
    rows=u16(body[(0x0028,0x0010)]); cols=u16(body[(0x0028,0x0011)])
    bits=u16(body[(0x0028,0x0100)]); spp=u16(body.get((0x0028,0x0002),b'\x01\x00'))
    photo=text(body.get((0x0028,0x0004)))
    raw=body[(0x7fe0,0x0010)]
    if bits==8: arr=np.frombuffer(raw,dtype=np.uint8)
    elif bits==16: arr=np.frombuffer(raw,dtype='<u2')
    else: raise ValueError(f'unsupported bits {bits}')
    expected=rows*cols*spp
    if arr.size < expected: raise ValueError(f'pixel payload short {arr.size}<{expected}')
    arr=arr[:expected]
    if spp != 1: arr=arr.reshape(rows,cols,spp)[...,0]
    else: arr=arr.reshape(rows,cols)
    return arr.astype(np.float32,copy=False), body


def load_studies():
    by={uid:[] for uid in BY_UID}
    for p in DICOM_ROOT.rglob('*.dcm'):
        try:
            data=p.read_bytes(); mo,meta=parse_meta(data)
            body=parse_body(data,mo,'<',False)
            uid=text(body.get((0x0020,0x000d)))
            sop=text(body.get((0x0008,0x0018)))
            if uid in BY_UID and sop:
                inst=text(body.get((0x0020,0x0013)))
                by[uid].append((inst,sop,p))
        except Exception as e:
            print('SKIP',p,e)
    for uid in by:
        by[uid].sort(key=lambda z:(int(z[0]) if z[0].isdigit() else 10**9,z[1]))
    return by


def bootstrap_metric_ci(y,p,B=4000,seed=42):
    rng=np.random.default_rng(seed); y=np.asarray(y); p=np.asarray(p)
    vals={'f1':[],'sens':[],'spec':[]}
    n=len(y)
    for _ in range(B):
        idx=rng.integers(0,n,n); yy=y[idx]; pp=p[idx]
        tn,fp,fn,tp=confusion_matrix(yy,pp,labels=[0,1]).ravel()
        vals['f1'].append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
        if tp+fn: vals['sens'].append(tp/(tp+fn))
        if tn+fp: vals['spec'].append(tn/(tn+fp))
    return {k:[float(np.quantile(v,.025)),float(np.quantile(v,.975))] for k,v in vals.items()}


def main():
    out=ROOT/'artifacts'/'corrected_routing_oof'; out.mkdir(exist_ok=True)
    by=load_studies(); rows=[]; routing=[]
    criteria=('spine_position','spine_axis','spine_artifact')
    for uid,s in BY_UID.items():
        items=by.get(uid,[])
        ims=[]
        for inst,sop,p in items:
            px,_=pixels_from_bytes(p); ims.append((sop,p,px))
        if not ims: continue
        preds=classify_study([x[2] for x in ims])
        for pr in preds:
            routing.append({'study_uid':uid,'image_uid':ims[pr.image_index][0],'route':pr.region,'image_index':pr.image_index,'side_shift':pr.side_shift,'ratio':pr.ratio})
        for crit in criteria:
            pp=[p for p in preds if p.region=='spine']
            y=BY_UID[uid]['labels'].get(crit)
            if y is None: continue
            if not pp:
                print('MISSING ROUTE',uid,crit); continue
            p=pp[0]; feat=_benchmark_features(ims[p.image_index][2]).ravel().astype(np.float32)
            rows.append({'study':uid,'criterion':crit,'y':int(y),'feature':feat,'image_uid':ims[p.image_index][0],'image_index':p.image_index})
    metadata=[{k:v for k,v in r.items() if k!='feature'} for r in rows]
    (out/'rows.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    np.savez_compressed(out/'features.npz', **{f'row_{i}': r['feature'] for i,r in enumerate(rows)})
    (out/'routing.csv').write_text(__import__('pandas').DataFrame(routing).to_csv(index=False),encoding='utf-8')
    results={}; oof_all={}
    for crit in criteria:
        rr=[r for r in rows if r['criterion']==crit]
        X=np.stack([r['feature'] for r in rr]); y=np.array([r['y'] for r in rr]); groups=np.array([r['study'] for r in rr])
        n_groups=len(np.unique(groups)); n_splits=min(5,n_groups)
        cv=StratifiedGroupKFold(n_splits=n_splits,shuffle=True,random_state=42)
        oof=np.full(len(y),np.nan); folds=[]
        for fold,(tr,va) in enumerate(cv.split(X,y,groups),1):
            model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,class_weight='balanced',max_iter=4000,random_state=42))
            with warnings.catch_warnings(): warnings.simplefilter('ignore'); model.fit(X[tr],y[tr])
            oof[va]=model.predict_proba(X[va])[:,1]
            folds.append({'fold':fold,'train_n':int(len(tr)),'valid_n':int(len(va)),'train_pos':int(y[tr].sum()),'valid_pos':int(y[va].sum()),'valid_studies':int(len(np.unique(groups[va])))})
        pred=oof>=.5
        tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
        ci=bootstrap_metric_ci(y,pred)
        results[crit]={
            'n':int(len(y)),'positive':int(y.sum()),'prevalence':float(y.mean()),
            'TP':int(tp),'TN':int(tn),'FP':int(fp),'FN':int(fn),
            'f1_oof':float(f1_score(y,pred,zero_division=0)),
            'sensitivity_oof':float(tp/(tp+fn)) if tp+fn else None,
            'specificity_oof':float(tn/(tn+fp)) if tn+fp else None,
            'roc_auc_oof':float(roc_auc_score(y,oof)),
            'pr_auc_oof':float(average_precision_score(y,oof)),
            'balanced_accuracy_oof':float(balanced_accuracy_score(y,pred)),
            'brier_oof':float(brier_score_loss(y,oof)),
            'ci_95_bootstrap':ci,'folds':folds,
            'routing_version':'corrected_all_images', 'status':'ok'
        }
        oof_all[crit]={'study':groups.tolist(),'y':y.tolist(),'p':oof.tolist(),'image_uid':[r['image_uid'] for r in rr],'image_index':[r['image_index'] for r in rr]}
    payload={'results':results,'n_studies':len(BY_UID),'routing_version':'corrected_all_images','seed':42,'bootstrap':4000}
    (out/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'oof_predictions.json').write_text(json.dumps(oof_all,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
