import json,struct,sys
from pathlib import Path
import numpy as np,joblib
ROOT=Path('/mnt/data/dxa_work');sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study,_benchmark_features
# parser
def read(p):
 b=Path(p).read_bytes();gl=struct.unpack_from('<I',b,140)[0];o=144+gl;v={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=8;x=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]:v[(g,e)]=x
  o+=l
  if (g,e)==(0x7fe0,0x10):break
 s=v[(0x20,0xd)].decode().rstrip('\0 ');so=v[(0x8,0x18)].decode().rstrip('\0 ');h=struct.unpack('<H',v[(0x28,0x10)])[0];w=struct.unpack('<H',v[(0x28,0x11)])[0];a=np.frombuffer(v[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w);return s,so,a
labels={r['study']:r['label'] for r in json.load(open(ROOT/'artifacts/spine_artifact_diagnostic.json'))}
allby={}
for p in (ROOT/'.training_dicom').rglob('*.dcm'):
 s,so,a=read(p);allby.setdefault(s,[]).append((so,p,a))
model=joblib.load(ROOT/'artifacts/models/spine_artifact.joblib')
study=[]
for s,items in allby.items():
 cand=[]
 for so,p,a in items:
  pr=classify_study([a])[0]
  if pr.region=='spine': cand.append((float(model.predict_proba(_benchmark_features(a))[0,1]),so))
 if cand and s in labels: study.append((s,labels[s],max(x[0] for x in cand),len(cand)))
for lab in [0,1]:
 z=[x[2] for x in study if x[1]==lab];print('label',lab,'n',len(z),'median',np.median(z),'p90',np.quantile(z,.9),'max',max(z))
for x in sorted(study,key=lambda q:q[2],reverse=True)[:30]: print(x[1],round(x[2],3),x[3],x[0])
