# V6.5 status — anatomy-aware criterion experiment

## What changed
- Added a study-level cross-validation experiment for hip positioning/rotation using the existing proximal-femur crop, HOG image descriptor and localizer geometry.
- Added OOF-only threshold calibration experiment; the threshold did not generalize stably to the fixed validation split, so it is **not promoted to the main pipeline**.
- Added `ENABLE_EXPERIMENTAL_BENCHMARK_HEADS` / `enable_experimental_benchmark_heads` gate. Serialized V6.x benchmark heads are now disabled by default in the main inference path until their training provenance is audited and their metrics are re-established with the fixed leakage-safe split.

## Evidence from fixed validation split
- Hip positioning/rotation: RBF SVC selected by study-level GroupKFold on the training studies reached validation ROC-AUC ~0.73 and AP ~0.58 in the fixed run; F1 at 0.5 was 0 because the default threshold is unsuitable for this imbalanced task.
- OOF threshold calibration did not yield a stable validation F1 improvement across reruns; therefore no validation-tuned threshold is used in production.
- Hip ROI remains too sparse for a trustworthy supervised classifier: 4 positive training labels and 3 validation positives in the current split.

## Interpretation
The anatomy-aware feature layer has signal for hip positioning/rotation, but the current 100-study dataset is still too small for claiming a final quality model. The experimental model remains outside the main inference path.
