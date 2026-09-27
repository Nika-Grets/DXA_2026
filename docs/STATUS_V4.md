# DXA project status — v4

## What is ready
- terminology abstraction layer;
- study-level routing: spine / right hip / left hip / unknown;
- physical scale constants: X=0.60 mm/px, Y=1.05 mm/px;
- deterministic baseline quality checks;
- separate findings for scoliosis and endoprosthesis;
- duplicate-safe inference: duplicate pixel data reuse computation but every source DICOM receives an output row;
- robust API error handling;
- leakage-safe **stratified** study split;
- label audit that preserves the expert criterion labels exactly.

## What is deliberately not claimed yet
The current deterministic adapter is a baseline, not a clinically validated model. The supplied dataset does not contain the bounding-box annotations required by the older YOLOX/L1-L4 training path, so no fabricated localization labels are created.

## What the user needs to provide
Nothing is blocking the current development. When the official terminology dictionary arrives, provide it and it can replace `config/terminology.yaml` without changing model logic. External datasets are optional and can be added later for anatomy/localization/domain-shift robustness.

## Next ML step
1. Build manifest inside the target container with the project's pinned `pydicom`.
2. Run `audit_labels.py` and `split_studies.py`.
3. Train criterion-level spine heads and hip position/rotation heads using study-level grouping.
4. Keep ROI as a geometry/localization track until enough positive examples exist.
5. Evaluate sensitivity, specificity, balanced accuracy, F1 and ROC/PR AUC per criterion and region.
