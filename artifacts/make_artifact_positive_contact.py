import json, struct, math
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import numpy as np
# load rows and reconstruct all dcm paths grouped by study from diagnostic
rows=json.load(open('/mnt/data/dxa_work/artifacts/spine_artifact_diagnostic.json'))
pos_studies=sorted(set(r['study'] for r in rows if r['label']==1))
by={}
for r in rows: by.setdefault(r['study'],{})['selected_spine']=r['sop']
# parse all dcm by study from simple parser imported
import sys; sys.path.insert(0,'/mnt/data/dxa_work/artifacts')
# reuse parser by exec file? avoid running diagnostics; define tiny

def read(path):
 b=Path(path).read_bytes(); gl=struct.unpack_from('<I',b,140)[0]; o=144+gl; vals={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o); o+=8; v=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]: vals[(g,e)]=v
  o+=l
  if (g,e)==(0x7fe0,0x10): break
 study=vals[(0x20,0xd)].decode().rstrip('\0 '); sop=vals[(0x8,0x18)].decode().rstrip('\0 ')
 h=struct.unpack('<H',vals[(0x28,0x10)])[0]; w=struct.unpack('<H',vals[(0x28,0x11)])[0]
 arr=np.frombuffer(vals[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w)
 return study,sop,arr
all_by={}
for p in Path('/mnt/data/dxa_work/.training_dicom').rglob('*.dcm'):
 s,so,a=read(p); all_by.setdefault(s,[]).append((so,p,a))

for si,s in enumerate(pos_studies):
 items=sorted(all_by[s],key=lambda x:x[0]); thumbs=[]
 for j,(sop,p,arr) in enumerate(items):
  lo,hi=np.percentile(arr,[1,99]); x=np.clip((arr-lo)/(hi-lo+1e-9),0,1); im=Image.fromarray((x*255).astype('uint8')); im.thumbnail((260,300))
  c=Image.new('RGB',(290,350),'white'); c.paste(ImageOps.autocontrast(im).convert('RGB'),((290-im.width)//2,25))
  d=ImageDraw.Draw(c); sel=(sop==by[s]['selected_spine']); d.text((5,5),f"{'SELECTED SPINE' if sel else 'other'} #{j} {im.width}x{im.height}",fill='red' if sel else 'black'); d.text((5,325),p.parent.parent.name[:34],fill='black'); thumbs.append(c)
 cols=min(6,len(thumbs)); out=Image.new('RGB',(cols*290,math.ceil(len(thumbs)/cols)*350),'#ddd')
 for j,t in enumerate(thumbs): out.paste(t,((j%cols)*290,(j//cols)*350))
 out.save(f'/mnt/data/dxa_work/artifacts/artifact_pos_{si+1:02d}.png')
 print(si+1,s,len(items),f'/mnt/data/dxa_work/artifacts/artifact_pos_{si+1:02d}.png')
