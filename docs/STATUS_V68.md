# STATUS V6.8 — ML quality/probability phase

Date: 2026-09-20

## Completed

- Kept V6.7.1 canonical StudyInstanceUID grouping and two-image routing fix.
- Added composition guard for two-image `spine + single-hip` studies.
- Refit criterion models using a leakage-safe 5-fold `StratifiedGroupKFold` development protocol grouped by `StudyInstanceUID`.
- Saved OOF predictions and criterion-level metrics under `artifacts/v68_oof/`.
- Added study-level bootstrap 95% CIs for OOF ROC-AUC and PR-AUC.
- Added model provenance with hashes and runtime versions.
- `quality_prob` now represents continuous image-level violation risk rather than an inversion of generic confidence.
- Final deployment models are fit on all available labelled criterion samples only after OOF evaluation; they are not an independent test result.

## Current OOF development results

- Spine position: ROC-AUC 0.826, but only 6 positives and a wide CI.
- Spine axis: ROC-AUC 0.631.
- Spine artifact: ROC-AUC 0.546.
- Right hip position/rotation: ROC-AUC 0.769.
- Right hip ROI: ROC-AUC 0.604, only 3 positives.
- Left hip position/rotation: ROC-AUC 0.489.
- Left hip ROI: ROC-AUC 0.301, only 4 positives.

These are development/CV measurements, not independent final-test performance.

## Not claimed yet

- No calibrated clinical probability.
- No independent final-test metric.
- No replacement of deterministic anatomy/geometry with the ML heads.
- No claim of robust ROI classification with 3–4 positive examples.

## Next V6.8 work

1. Improve hip anatomy coordinates and ROI geometry using the existing localizer output rather than fixed image fractions.
2. Add explicit localization/landmark artifacts for visualization.
3. Evaluate geometry changes with the same study-level OOF protocol.
4. Only after that freeze the API and move to V6.9 packaging/containerization.
