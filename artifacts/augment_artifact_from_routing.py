from pathlib import Path
import csv, json, struct

ROOT=Path(__file__).resolve().parents[1]
TRAIN=ROOT/'.training_dicom'
SRC=ROOT/'data/training_batch.csv'
OUT=ROOT/'data/training_batch_routed_artifact.csv'
DIAG=json.load(open(ROOT/'artifacts/routing_fix_diagnostic.json',encoding='utf-8'))

def read_uids(path):
 b=path.read_bytes(); pos=132
 while pos+8<=len(b):
  g,e=struct.unpack_from('<HH',b,pos)
  if g!=2: break
  vr=b[pos+4:pos+6]
  if vr in {b'OB',b'OD',b'OF',b'OL',b'OV',b'OW',b'SQ',b'UC',b'UN',b'UR'}: L=struct.unpack_from('<I',b,pos+8)[0]; h=12
  else: L=struct.unpack_from('<H',b,pos+6)[0]; h=8
  pos += h+L
 vals={}
 while pos+8<=len(b):
  g,e=struct.unpack_from('<HH',b,pos); L=struct.unpack_from('<I',b,pos+4)[0]; a=pos+8; z=a+L
  if z>len(b): break
  if (g,e)==(0x0020,0x000d): vals['study']=b[a:z].rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x0008,0x0018): vals['sop']=b[a:z].rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x7fe0,0x0010): break
  pos=z
 return vals

mapping={}
for p in TRAIN.rglob('*.dcm'):
 v=read_uids(p)
 if v.get('study') and v.get('sop'):
  mapping[(v['study'],p.name)]=v['sop']

rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig',newline='')))
by_target={(d['study'],d['corrected_path']):d for d in DIAG}
changed=[]
for r in rows:
 key=(r['study_uid'], None)
 target=None
 for (study,path),d in by_target.items():
  if study==r['study_uid']:
   target=path; diag=d; break
 if target and r['image_uid']==mapping.get((r['study_uid'],target)) and float(diag['corrected_artifact'])>=0.5:
  old=r['violation_type'] or ''
  parts=[x for x in old.split(';') if x]
  if 'Присутствуют посторонние предметы' not in parts: parts.append('Присутствуют посторонние предметы')
  r['violation_type']=';'.join(parts)
  r['quality_class']='1'
  r['confidence']=max(float(r['confidence'] or 0),float(diag['corrected_artifact']))
  r['quality_prob']=max(float(r['quality_prob'] or 0),float(diag['corrected_artifact']))
  changed.append((r['study_uid'],r['image_uid'],diag['corrected_artifact']))

with OUT.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print('changed',len(changed),'studies',len(set(x[0] for x in changed)))
for x in changed: print(*x)
print('out',OUT)
