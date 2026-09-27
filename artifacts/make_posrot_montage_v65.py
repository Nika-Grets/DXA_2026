exec(open('/mnt/data/v6_4_work/v64/artifacts/experiment_cv_models_v65.py').read().split("for target in ['pos','roi']:")[0])
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
import math
# rebuild rows with image refs
# reuse rows and locate source image by study/side
tr=[r for r in rows if split[r['study']]=='train']; va=[r for r in rows if split[r['study']]=='validation']
Xtr=np.stack([r['f'] for r in tr]); ytr=np.array([r['pos'] for r in tr]); groups=np.array([r['study'] for r in tr])
Xv=np.stack([r['f'] for r in va]); yv=np.array([r['pos'] for r in va])
model=make_pipeline(StandardScaler(),SVC(C=1,gamma='scale',class_weight='balanced',probability=True,random_state=42)); model.fit(Xtr,ytr); p=model.predict_proba(Xv)[:,1]
t=.165; pred=p>=t
items=[]
for r,yy,pp,dd in zip(va,yv,p,pred):
    imgs=load_study(r['study']); ps=[q for q in classify_study(imgs) if q.region=='femur_'+r['side']][0]
    img=imgs[ps.image_index]; loc=localize_hip(img,r['side'])
    items.append((r,yy,pp,dd,img,loc))
# prioritize FN, FP, TP, TN
sel=[]
for typ in ['FN','FP','TP','TN']:
    cand=[]
    for it in items:
        _,yy,pp,dd,*_=it
        kind='TP' if yy and dd else 'TN' if not yy and not dd else 'FP' if not yy and dd else 'FN'
        if kind==typ: cand.append(it)
    cand=sorted(cand,key=lambda z: abs(z[2]-t),reverse=True)
    sel += cand[:3]
import matplotlib.pyplot as plt
fig,axs=plt.subplots(3,4,figsize=(12,9))
for ax in axs.ravel(): ax.axis('off')
for ax,it in zip(axs.ravel(),sel[:12]):
    r,yy,pp,dd,img,loc=it
    x=_normalize(img); ax.imshow(x,cmap='gray')
    bx,by,bw,bh=loc.bone_bbox; h,w=x.shape
    rect=plt.Rectangle((bx*w,by*h),bw*w,bh*h,fill=False,linewidth=2)
    ax.add_patch(rect)
    kind='TP' if yy and dd else 'TN' if not yy and not dd else 'FP' if not yy and dd else 'FN'
    ax.set_title(f"{kind} y={yy} p={pp:.2f} {r['side']}\n{r['study'][-8:]}",fontsize=8)
plt.tight_layout(); out='/mnt/data/v6_4_work/v64/artifacts/posrot_validation_montage_v65.png'; plt.savefig(out,dpi=150); plt.close(); print(out)
