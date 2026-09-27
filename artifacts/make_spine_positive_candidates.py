import struct,json,math,sys
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import numpy as np
ROOT=Path('/mnt/data/dxa_work');sys.path.insert(0,str(ROOT/'backend'))
from app.ml.dexa_baseline import classify_study
# parse
def read(p):
 b=Path(p).read_bytes();gl=struct.unpack_from('<I',b,140)[0];o=144+gl;v={}
 while o+8<=len(b):
  g,e,l=struct.unpack_from('<HHI',b,o);o+=8;x=b[o:o+l]
  if (g,e) in [(0x20,0xd),(0x8,0x18),(0x28,0x10),(0x28,0x11),(0x7fe0,0x10)]:v[(g,e)]=x
  o+=l
  if (g,e)==(0x7fe0,0x10):break
 s=v[(0x20,0xd)].decode().rstrip('\0 ');so=v[(0x8,0x18)].decode().rstrip('\0 ');h=struct.unpack('<H',v[(0x28,0x10)])[0];w=struct.unpack('<H',v[(0x28,0x11)])[0];a=np.frombuffer(v[(0x7fe0,0x10)],dtype=np.uint8,count=h*w).reshape(h,w);return s,so,a
rows=json.load(open(ROOT/'artifacts/spine_artifact_diagnostic.json'));pos=sorted(set(r['study'] for r in rows if r['label']==1));allby={}
for p in (ROOT/'.training_dicom').rglob('*.dcm'):
 s,so,a=read(p);allby.setdefault(s,[]).append((so,p,a))
thumbs=[]
for s in pos:
 items=sorted(allby[s],key=lambda x:x[0]);
 for j,(so,p,a) in enumerate(items):
  pr=classify_study([a])[0]
  if pr.region!='spine': continue
  lo,hi=np.percentile(a,[1,99]);x=np.clip((a-lo)/(hi-lo+1e-9),0,1);im=Image.fromarray((x*255).astype('uint8'));im.thumbnail((210,260));c=Image.new('RGB',(230,310),'white');c.paste(ImageOps.autocontrast(im).convert('RGB'),((230-im.width)//2,25));d=ImageDraw.Draw(c);d.text((4,4),f'p study={pos.index(s)+1} img#{j}',fill='black');d.text((4,285),f'ratio {pr.ratio:.2f} shift {pr.side_shift:.2f}',fill='black');thumbs.append(c)
cols=5;out=Image.new('RGB',(cols*230,math.ceil(len(thumbs)/cols)*310),'#ddd')
for i,t in enumerate(thumbs):out.paste(t,((i%cols)*230,(i//cols)*310))
out.save(ROOT/'artifacts/spine_positive_candidates.png');print(len(thumbs),ROOT/'artifacts/spine_positive_candidates.png')
