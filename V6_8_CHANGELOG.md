# V6.8 changelog — 2026-09-20

## Added
- Leakage-safe 5-fold OOF benchmark grouped by DICOM StudyInstanceUID.
- OOF prediction archive and criterion-level metrics.
- Study-level bootstrap 95% confidence intervals.
- Model provenance and SHA-256 hashes.
- Continuous `quality_prob` risk semantics.
- Two-image spine+single-hip routing guard.

## Changed
- Criterion models are refit on all labelled samples only after OOF diagnostics.
- Production model version: `1.6.0-v68`.
- `quality_prob` is no longer derived by inverting the generic confidence score.

## Explicit limitations
- OOF results are development/CV results, not independent test performance.
- Current quality scores are not clinically calibrated probabilities.
- Hip ROI labels remain too sparse for a reliable standalone supervised detector.

## V6.8.1 — anatomy visualization payload

- Added `anatomy_localization` to image prediction schema.
- Exposed spine candidate corridor/centerline and physical axis angle.
- Exposed hip proximal-femur candidate bbox, shaft bbox, side and physical margins.
- Kept these geometries explicitly separate from defect localization/segmentation.
- Rejected new hip anatomy-feature and ROI-geometry experiments after leakage-safe study-level OOF comparison showed no improvement over the existing benchmark heads.

## V6.8.2 — experimental hip landmarks
- Added `backend/app/ml/hip_landmarks.py` with explainable candidate femoral-head, neck, shaft-axis and greater-trochanter proxy landmarks.
- Added grouped OOF experiment `artifacts/v68_landmark_candidates.py`.
- Candidate landmarks are visualization/research only; they do not change production quality decisions.
- OOF combined feature results: position/rotation ROC-AUC 0.487, ROI ROC-AUC 0.591.
- Added `docs/STATUS_V682.md`.

## V6.8.3 — ROI candidate-score experiment
- Added an interpretable single-feature ROI candidate (`q60_sx`).
- Evaluated with study-level grouping and bootstrap CI.
- Result: ROC-AUC 0.833, PR-AUC 0.516 on 150 observations / 7 positives.
- No production threshold or model changed; experiment remains development-only.
