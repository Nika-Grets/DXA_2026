import json, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT=Path('/mnt/data/dxa_work')
D=ROOT/'artifacts/routing_fix_diagnostic.json'
rows=json.load(open(D))
rows=[r for r in rows if r['changed'] and r['label']==1]
# reload images

def read(path):
 b=Path(path).read_bytes(); gl=struct.unpack_from('<I',b,140)[0]; o=144+gl; vals={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=8;v=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]: vals[(g,e)]=v
  o+=l
  if (g,e)==(0x7fe0,0x10): break
 h=struct.unpack('<H',vals[(0x28,0x10)])[0];w=struct.unpack('<H',vals[(0x28,0x11)])[0]
 a=np.frombuffer(vals[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w)
 return a

def prep(a):
 x=a.astype(np.float32); lo,hi=np.percentile(x,[1,99]); x=np.clip((x-lo)/(hi-lo+1e-6),0,1); im=Image.fromarray((x*255).astype(np.uint8)).convert('RGB'); im.thumbnail((320,320)); return im
W=700; H=380*len(rows); out=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(out)
for j,r in enumerate(rows):
 y=j*380
 # locate paths by name
 files=list((ROOT/'.training_dicom').rglob(r['current_path']))
 cur=read(files[0]); files2=list((ROOT/'.training_dicom').rglob(r['corrected_path'])); cor=read(files2[0])
 out.paste(prep(cur),(10,y+35)); out.paste(prep(cor),(360,y+35))
 d.text((10,y+8),f"POS N={r['n']} current idx {r['current_index']} p={r['current_artifact']:.3g}",fill='black')
 d.text((360,y+8),f"corrected idx {r['corrected_index']} p={r['corrected_artifact']:.3g}",fill='black')
out.save(ROOT/'artifacts/routing_positive_comparison.png')
print(ROOT/'artifacts/routing_positive_comparison.png')
