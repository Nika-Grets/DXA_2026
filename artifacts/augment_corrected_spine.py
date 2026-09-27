from pathlib import Path
import csv, json, struct
import numpy as np
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import evaluate_quality, _quality_probabilities
from app.terminology import term_name

SRC=ROOT/'data/training_batch.csv'; OUT=ROOT/'data/training_batch_corrected_spine.csv'
DIAG=json.load(open(ROOT/'artifacts/routing_fix_diagnostic.json',encoding='utf-8'))

def read(path):
 b=path.read_bytes(); pos=132
 while True:
  g,e=struct.unpack_from('<HH',b,pos)
  if g!=2: break
  vr=b[pos+4:pos+6]
  if vr in {b'OB',b'OD',b'OF',b'OL',b'OV',b'OW',b'SQ',b'UC',b'UN',b'UR'}: L=struct.unpack_from('<I',b,pos+8)[0]; h=12
  else: L=struct.unpack_from('<H',b,pos+6)[0]; h=8
  pos+=h+L
 vals={}
 while pos+8<=len(b):
  g,e=struct.unpack_from('<HH',b,pos); L=struct.unpack_from('<I',b,pos+4)[0]; a=pos+8; z=a+L
  if z>len(b): break
  v=b[a:z]
  if (g,e)==(0x20,0xd): vals['study']=v.rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x8,0x18): vals['sop']=v.rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x8,0x70): vals['Manufacturer']=v.rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x8,0x1090): vals['ManufacturerModelName']=v.rstrip(b' \0').decode('utf-8','replace')
  elif (g,e)==(0x28,0x10): vals['rows']=struct.unpack_from('<H',v)[0]
  elif (g,e)==(0x28,0x11): vals['cols']=struct.unpack_from('<H',v)[0]
  elif (g,e)==(0x28,0x100): vals['bits']=struct.unpack_from('<H',v)[0]
  elif (g,e)==(0x28,0x4): vals['photo']=v.rstrip(b' \0').decode('ascii','replace')
  elif (g,e)==(0x7fe0,0x10):
   h,w=vals['rows'],vals['cols']; a=np.frombuffer(v,dtype=np.uint8,count=h*w).reshape(h,w).astype(np.float32)
   if vals.get('photo')=='MONOCHROME1': a=255-a
   return vals,a
  pos=z
 raise RuntimeError(path)

# locate all requested corrected files and calculate their new spine decision
wanted={(d['study'],d['corrected_path']):d for d in DIAG if d['label'] is not None}
results={}
for p in (ROOT / '.training_dicom').rglob('*.dcm'):
 if p.name not in {x['corrected_path'] for x in wanted.values()}: continue
 meta,pix=read(p); key=(meta['study'],p.name)
 if key not in wanted: continue
 status,conf,viol,find=evaluate_quality(pix,'spine',meta)
 model_risks=_quality_probabilities(pix,'spine')
 prob=max([float(conf if status=='issue_detected' else 0.0),*model_risks])
 results[key]={'image_uid':meta['sop'],'violations':viol,'findings':find,'confidence':conf,'quality_prob':prob}

rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig',newline='')))
# clear old spine-only violation types from every image in the study; current routing
# will assign the corrected decision to the one corrected spine image below.
spine_terms={'Некорректная укладка','Не выравнена ось позвоночника','Присутствуют посторонние предметы'}
by_study={d['study']:d for d in DIAG if d['label'] is not None}
for r in rows:
 d=by_study.get(r['study_uid'])
 if not d: continue
 parts=[x for x in (r['violation_type'] or '').split(';') if x and x not in spine_terms]
 r['violation_type']=';'.join(parts)
 if r['image_uid']==results[(d['study'],d['corrected_path'])]['image_uid']:
  z=results[(d['study'],d['corrected_path'])]
  labels=[term_name(x) for x in z['violations'] if x in {'SPINE_POSITION','SPINE_AXIS','SPINE_ARTIFACT'}]
  r['violation_type']=';'.join(labels)
  findings=[term_name(x) for x in z['findings']]
  r['findings']=';'.join(findings)
  r['quality_class']=str(int(bool(labels)))
  r['confidence']=str(z['confidence']); r['quality_prob']=str(z['quality_prob'])
  if z['violations']:
   pass

with OUT.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('computed spine decisions',len(results),'wrote',OUT)
from collections import Counter
print('violations',Counter(r['violation_type'] for r in rows))
