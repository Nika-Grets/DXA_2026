# STATUS V6.8.1 — anatomy visualization payload

Date: 2026-09-20

## Added
- `ImagePrediction.anatomy_localization`.
- Spine candidate bbox + centerline + physical axis angle.
- Hip proximal-femur candidate bbox + shaft bbox + side + physical margins.
- Explicit documentation that these are candidate anatomy geometries, not defect masks.

## Validation
- Python compileall: PASS.
- V6.7.1 test ZIP, full study-level inference: 3/3 images routed correctly.
- All 3 test results carry `anatomy_localization`.
- `quality_prob` remains in [0,1].

## Experiments not adopted
- Shaft-anchored anatomy-coordinate feature set: hip position/rotation OOF ROC-AUC 0.541; worse than the existing benchmark head.
- Benchmark + localizer geometry features: position/rotation OOF ROC-AUC 0.606; worse than existing 0.769.
- Physical-margin-only ROI severity: ROC-AUC 0.631 with only 1/7 ROI positives detected at the literal threshold; not sufficient to replace the current ROI logic.
- Sigmoid calibration experiment did not provide a consistent improvement across criteria; calibration remains criterion-specific and is not promoted globally.

The existing benchmark heads therefore remain unchanged.
