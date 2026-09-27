import json, struct, sys
from pathlib import Path
import numpy as np
ROOT=Path('/mnt/data/dxa_work'); sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study, _criterion_prob, fixed_top_bottom_ratio, side_shift, symmetry, _benchmark_features, _load_quality_models

def read(path):
 b=Path(path).read_bytes(); gl=struct.unpack_from('<I',b,140)[0]; o=144+gl; vals={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=8;v=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]: vals[(g,e)]=v
  o+=l
  if (g,e)==(0x7fe0,0x10): break
 s=vals[(0x20,0xd)].decode().rstrip('\0 '); so=vals[(0x8,0x18)].decode().rstrip('\0 ')
 h=struct.unpack('<H',vals[(0x28,0x10)])[0]; w=struct.unpack('<H',vals[(0x28,0x11)])[0]
 a=np.frombuffer(vals[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w)
 return s,so,a

rows=json.load(open(ROOT/'artifacts/spine_artifact_diagnostic.json'))
labels={r['study']:r['label'] for r in rows}
all_by={}
for p in (ROOT/'.training_dicom').rglob('*.dcm'):
 s,so,a=read(p); all_by.setdefault(s,[]).append((so,p,a))

def corrected(items):
 # all-image independent anatomy candidates, retaining original index
 singles=[]
 for i,(_,_,a) in enumerate(items):
  p=classify_study([a])[0]
  singles.append((i,p))
 spine=[(i,p) for i,p in singles if p.region=='spine']
 if spine:
  # Prefer candidate with shift closest to zero; tie-break by lower top/bottom ratio.
  i,p=min(spine,key=lambda t:(abs(t[1].side_shift), t[1].ratio))
 else:
  i,p=min(singles,key=lambda t:(abs(t[1].side_shift), t[1].ratio))
 return i,p,singles

summary=[]
for s,items in all_by.items():
 items=sorted(items,key=lambda x:x[0]); n=len(items)
 cur=classify_study([x[2] for x in items[:3]])
 cur_sp=[p for p in cur if p.region=='spine']
 cur_i=cur_sp[0].image_index if cur_sp else None
 ci,cp,singles=corrected(items)
 model=_load_quality_models().get('spine_artifact')
 p_art=float(model.predict_proba(_benchmark_features(items[ci][2]))[0,1]) if model is not None else 0.0
 summary.append(dict(study=s,label=labels.get(s),n=n,current_index=cur_i,current_path=(items[cur_i][1].name if cur_i is not None else None),corrected_index=ci,corrected_path=items[ci][1].name,corrected_region=cp.region,current_artifact=(float(model.predict_proba(_benchmark_features(items[cur_i][2]))[0,1]) if (cur_i is not None and model is not None) else None),corrected_artifact=p_art,changed=(cur_i!=ci),single_spines=[i for i,p in singles if p.region=='spine']))

changed=[r for r in summary if r['changed']]
print('studies',len(summary),'changed',len(changed),'with >3',sum(r['n']>3 for r in summary),'changed among >3',sum(r['changed'] and r['n']>3 for r in summary))
for lab,name in [(1,'POS'),(0,'NEG'),(None,'UNK')]:
 ss=[r for r in summary if r['label']==lab]
 print(name,'N',len(ss),'changed',sum(r['changed'] for r in ss),'current selected p>=.5',sum((r['current_artifact'] is not None and r['current_artifact']>=.5) for r in ss),'corrected p>=.5',sum(r['corrected_artifact']>=.5 for r in ss))
print('\nChanged positive:')
for r in changed:
 if r['label']==1:
  print(r['study'], 'N',r['n'],'cur',r['current_index'],r['current_path'],'corr',r['corrected_index'],r['corrected_path'],'p',r['current_artifact'],r['corrected_artifact'],'cands',r['single_spines'])
print('\nChanged all >3:')
for r in changed:
 if r['n']>3:
  print(r['study'],r['label'],'N',r['n'],'cur',r['current_index'],'corr',r['corrected_index'],'p',r['current_artifact'],r['corrected_artifact'],'cands',r['single_spines'])
json.dump(summary,open(ROOT/'artifacts/routing_fix_diagnostic.json','w'),indent=2)
