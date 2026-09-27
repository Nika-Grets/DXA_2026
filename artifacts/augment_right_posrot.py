from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'data/training_batch_routed_artifact.csv'
exp=ROOT/'data/training_batch_right_posrot_experiment.csv'
out=ROOT/'data/training_batch_mvp_composite.csv'
A=pd.read_csv(base).fillna(''); E=pd.read_csv(exp).fillna('')
# Add only the existing right_posrot benchmark head's explicit rotation decision.
# Do not overwrite ROI or other criteria from the baseline CSV.
mask=E.violation_type.astype(str).str.contains('HIP_POSITION_ROTATION', regex=False)
keys=set(zip(E.loc[mask,'study_uid'],E.loc[mask,'image_uid']))
changed=0
for i,r in A.iterrows():
 if (r.study_uid,r.image_uid) in keys:
  parts=[x for x in str(r.violation_type).split(';') if x]
  if 'Некорректная укладка' not in parts:
   parts.append('Некорректная укладка')
   changed+=1
  A.at[i,'violation_type']=';'.join(parts)
  A.at[i,'quality_class']=1
  p=float(E.loc[(E.study_uid==r.study_uid)&(E.image_uid==r.image_uid),'quality_prob'].iloc[0])
  A.at[i,'quality_prob']=max(float(r.quality_prob or 0),p)
  A.at[i,'confidence']=max(float(r.confidence or 0),p)
A.to_csv(out,index=False)
print('right_posrot image rows added',changed,'studies',len(set(s for s,i in keys)))
print(out)
