import json, struct, sys
from pathlib import Path
import numpy as np
ROOT=Path('/mnt/data/dxa_work'); sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study, _normalize, fixed_top_bottom_ratio, side_shift, symmetry
# simple reader

def read(path):
 b=Path(path).read_bytes(); gl=struct.unpack_from('<I',b,140)[0]; o=144+gl; vals={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=8;v=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]:vals[(g,e)]=v
  o+=l
  if (g,e)==(0x7fe0,0x10):break
 s=vals[(0x20,0xd)].decode().rstrip('\0 '); so=vals[(0x8,0x18)].decode().rstrip('\0 ')
 h=struct.unpack('<H',vals[(0x28,0x10)])[0];w=struct.unpack('<H',vals[(0x28,0x11)])[0]
 a=np.frombuffer(vals[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w)
 return s,so,a
rows=json.load(open(ROOT/'artifacts/spine_artifact_diagnostic.json')); pos={r['study'] for r in rows if r['label']==1}
all_by={}
for p in (ROOT/'.training_dicom').rglob('*.dcm'):
 s,so,a=read(p);all_by.setdefault(s,[]).append((so,p,a))
for s in sorted(pos):
 items=sorted(all_by[s],key=lambda x:x[0]); print('\n',s,'N',len(items))
 for i,(so,p,a) in enumerate(items):
  pr=classify_study([a])[0]
  print(i, 'single=',pr.region, 'conf',round(pr.confidence,2),'ratio',round(pr.ratio,3),'shift',round(pr.side_shift,3),'sym',round(pr.symmetry,3),p.name)
