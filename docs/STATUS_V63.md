# DXA V6.3 — status

## What changed

### Hip localization
The previous V6.2 localizer selected a generic bright connected component and then expanded it by fixed 20/30 mm margins. This mixed up two different concepts:

1. finding the proximal femur;
2. checking whether sufficient image is visualized around the area of interest.

V6.3 changes the anatomical candidate to a **femoral-shaft-first** method. A long, side-consistent shaft candidate anchors the proximal-femur box. This explicitly reduces confusion with superior/medial pelvic structures and visible spinal fragments.

The ROI/visualization criterion is now represented by **available physical margins** `(left, top, right, bottom)` in mm. The TЗ requirement is 30 mm above, 30 mm below and 20 mm toward the lateral edge; the 20 mm requirement is side-dependent rather than a 20 mm expansion on both sides.

Important: these physical margins are an explainable feature, **not yet the final ROI classifier**. The dataset contains only 7 positive hip-ROI criterion labels among 150 labeled hip images, and a simple margin proxy has poor agreement with those labels. Therefore we do not claim that the geometric proxy solves the ROI criterion.

## Current measurements

- 153 hip image routes in the 100-study set.
- Median shaft-localization confidence: ~0.803.
- Median shaft score: ~0.697.
- Hip ROI criterion labels available: 150; positives: 7.
- Simple margin-proxy flags: 18/150; exploratory F1 against the expert ROI labels: 0.08. This is **not** used as the final model.

## Current project status

Approximate completion: **~62–66% overall**.

- DICOM/data audit: 100%
- terminology/Q&A: 100%
- study-level split: 100%
- baseline criterion models: 100% baseline, not final
- region routing: ~90%
- spine localization: ~70%
- hip anatomical localization: ~60%
- anatomy + geometry criterion models: ~20%
- threshold calibration: ~0%
- final benchmark: ~20%
- final Docker/demo verification: ~60–70%

These percentages are engineering progress estimates, not evaluation scores.

## Next steps

1. Validate/strengthen the shaft-first hip candidate on all hip images and add abstention for low-confidence cases.
2. Build explicit femoral-neck/trochanter geometry features for positioning/rotation.
3. Keep the physical 3/3/2 mm rule as an interpretable feature, but combine it with image/model evidence rather than using it as a standalone classifier.
4. Rebuild criterion-level models from anatomy + geometry + image evidence.
5. Calibrate thresholds using the existing study-level split without leakage.
6. Run the full benchmark required by the TЗ, then freeze a final Docker checkpoint.
