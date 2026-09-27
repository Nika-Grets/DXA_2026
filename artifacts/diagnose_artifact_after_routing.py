import json, struct, sys
from pathlib import Path
import numpy as np, joblib
ROOT=Path('/mnt/data/dxa_work');sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study, _benchmark_features
model=joblib.load(ROOT/'artifacts/models/spine_artifact.joblib')
labels={r['study']:r['label'] for r in json.load(open(ROOT/'artifacts/spine_artifact_diagnostic.json'))}

def read(path):
 b=Path(path).read_bytes(); gl=struct.unpack_from('<I',b,140)[0]; o=144+gl; vals={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=l+8;v=b[o-l:o]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]: vals[(g,e)]=v
  if (g,e)==(0x7fe0,0x10): break
 s=vals[(0x20,0xd)].decode().rstrip('\0 '); h=struct.unpack('<H',vals[(0x28,0x10)])[0];w=struct.unpack('<H',vals[(0x28,0x11)])[0]
 a=np.frombuffer(vals[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w); return s,a
all_by={}
for p in (ROOT/'.training_dicom').rglob('*.dcm'):
 s,a=read(p);all_by.setdefault(s,[]).append((p,a))
rows=[]
for s,items in all_by.items():
 items=sorted(items,key=lambda x:x[0].as_posix())
 preds=classify_study([a for _,a in items]); sp=[p for p in preds if p.region=='spine']
 if not sp: rows.append({'study':s,'label':labels.get(s),'n':len(items),'idx':None,'p':None}); continue
 idx=sp[0].image_index; p=float(model.predict_proba(_benchmark_features(items[idx][1]))[0,1])
 rows.append({'study':s,'label':labels.get(s),'n':len(items),'idx':idx,'path':items[idx][0].name,'p':p})
known=[r for r in rows if r['label'] in (0,1)]
for thr in [0.5,0.7,0.9,0.95]:
 tp=sum(r['label']==1 and r['p']>=thr for r in known); fp=sum(r['label']==0 and r['p']>=thr for r in known); fn=sum(r['label']==1 and r['p']<thr for r in known); tn=sum(r['label']==0 and r['p']<thr for r in known)
 f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0
 sens=tp/(tp+fn); spec=tn/(tn+fp)
 print(thr,'TP FP FN TN',tp,fp,fn,tn,'F1',round(f1,4),'sens',round(sens,4),'spec',round(spec,4))
print('missing',sum(r['p'] is None for r in known))
print('positive predictions >=.5:',[(r['study'],r['n'],r['idx'],round(r['p'],3)) for r in known if r['label']==1 and r['p']>=.5])
print('negative false >=.5:',[(r['study'],r['n'],r['idx'],round(r['p'],3)) for r in known if r['label']==0 and r['p']>=.5])
json.dump(rows,open(ROOT/'artifacts/spine_artifact_after_routing_diagnostic.json','w'),indent=2)
