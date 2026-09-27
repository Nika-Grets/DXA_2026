from pathlib import Path
import zipfile, struct, sys, json
import numpy as np, pandas as pd, joblib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
from app.ml import dexa_baseline as db

# Force-load ONLY the existing right_posrot head. No retraining.
model=joblib.load(ROOT/'artifacts/models/right_posrot.joblib')
def only_right(): return {'right_posrot': model}
db._load_benchmark_models=only_right

def expl(data,off):
    vr=data[off+4:off+6].decode('ascii','replace')
    if vr in ('OB','OD','OF','OL','OV','OW','SQ','UC','UN','UR'):
        return struct.unpack_from('<I',data,off+8)[0],off+12
    return struct.unpack_from('<H',data,off+6)[0],off+8

def read(data):
    off=132
    while True:
        g,e=struct.unpack_from('<HH',data,off)
        if g!=2: break
        l,vo=expl(data,off); off=vo+l
    out={}
    while off+8<=len(data):
        tag=struct.unpack_from('<HH',data,off)
        # Explicit VR body is not used in this public dataset; match existing debug reader.
        l=struct.unpack_from('<I',data,off+4)[0]; vo=off+8
        if tag in [(0x0008,0x0018),(0x0020,0x000d),(0x0028,0x0010),(0x0028,0x0011),(0x7fe0,0x0010)]: out[tag]=data[vo:vo+l]
        off=vo+l
        if tag==(0x7fe0,0x0010): break
    rows=struct.unpack_from('<H',out[(0x0028,0x0010)])[0]
    cols=struct.unpack_from('<H',out[(0x0028,0x0011)])[0]
    pix=np.frombuffer(out[(0x7fe0,0x0010)],dtype=np.uint8).reshape(rows,cols).astype(np.float32)
    sop=out[(0x0008,0x0018)].rstrip(b'\0').decode()
    study=out[(0x0020,0x000d)].rstrip(b'\0').decode()
    return pix,sop,study

pred=pd.read_csv(ROOT/'data/training_batch.csv').fillna({'violation_type':'','findings':''})
route=pd.read_csv(ROOT/'artifacts/current_routing_repro.csv')
route_map=route.drop_duplicates('image_uid').set_index('image_uid')['route'].to_dict()
zip_path=ROOT/'data/#U041d#U0414_#U0434#U043b#U044f_#U043e#U0431#U0443#U0447#U0435#U043d#U0438#U044f.zip'
rows=[]
with zipfile.ZipFile(zip_path) as z:
    for name in sorted(n for n in z.namelist() if n.lower().endswith('.dcm')):
        data=z.read(name); pix,sop,study=read(data)
        if route_map.get(sop)!='femur_right': continue
        q,c,v,f=db.evaluate_quality(pix,'femur_right',None)
        p=float(model.predict_proba(db._benchmark_features(pix))[0,1])
        rows.append({'study_uid':study,'image_uid':sop,'p_right_posrot':p,'quality_class_alt':1 if q=='issue_detected' else 0,'violation_alt':';'.join(v),'findings_alt':';'.join(f)})
alt=pd.DataFrame(rows)
alt.to_csv(ROOT/'artifacts/right_posrot_experiment.csv',index=False)

# Overlay alternative result onto baseline CSV.
merged=pred.merge(alt,on=['study_uid','image_uid'],how='left')
mask=merged['p_right_posrot'].notna()
changed=mask & ((merged['quality_class'].astype(int)!=merged['quality_class_alt'].fillna(merged['quality_class']).astype(int)) | (merged['violation_type'].fillna('')!=merged['violation_alt'].fillna('')))
# only right-hip rows are touched; all other rows stay byte-semantically equivalent.
merged.loc[mask,'quality_class']=merged.loc[mask,'quality_class_alt'].astype(int)
merged.loc[mask,'violation_type']=merged.loc[mask,'violation_alt']
merged.loc[mask,'findings']=merged.loc[mask,'findings_alt']
# confidence/quality_prob intentionally not rewritten here; this is a decision-path experiment only.
outcols=list(pred.columns)
merged[outcols].to_csv(ROOT/'data/training_batch_right_posrot_experiment.csv',index=False)

print('right routed images:',len(alt))
print('p>=0.5:',int((alt.p_right_posrot>=0.5).sum()))
print('baseline violation rows:',int(pred.loc[mask,'violation_type'].fillna('').astype(str).str.contains('Некорректная укладка',regex=False).sum()))
print('alt violation rows:',int(alt.violation_alt.str.contains('Некорректная укладка',regex=False).sum()))
print('changed rows:',int(changed.sum()))
print('new right rotation studies:',alt.loc[alt.violation_alt.str.contains('Некорректная укладка',regex=False),'study_uid'].nunique())
print(alt.sort_values('p_right_posrot',ascending=False).head(15).to_string(index=False))
