# ML baseline — V6.8 OOF benchmark

This is a **development/CV** evaluation, not an independent final-test result.

Protocol: `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`, grouped by canonical DICOM `StudyInstanceUID`. Criterion-level labels are used as supplied; missing criterion labels are excluded from that criterion. The OOF predictions are generated without using the validation fold for fitting. Final deployment `.joblib` files are then refit on all available labelled samples.

| Criterion | N | Positive | OOF ROC-AUC | 95% CI | OOF PR-AUC | 95% CI | Brier |
|---|---:|---:|---:|---|---:|---|---:|
| spine_position | 99 | 6 | 0.826 | 0.555–0.982 | 0.347 | 0.104–0.772 | 0.051 |
| spine_axis | 99 | 10 | 0.631 | 0.362–0.857 | 0.303 | 0.089–0.593 | 0.089 |
| spine_artifact | 99 | 17 | 0.546 | 0.397–0.689 | 0.196 | 0.118–0.345 | 0.198 |
| right_posrot | 72 | 17 | 0.769 | 0.616–0.904 | 0.495 | 0.315–0.767 | 0.176 |
| right_roi | 72 | 3 | 0.604 | 0.000–0.972 | 0.153 | 0.014–0.613 | 0.062 |
| left_posrot | 78 | 19 | 0.489 | 0.334–0.646 | 0.265 | 0.161–0.459 | 0.307 |
| left_roi | 78 | 4 | 0.301 | 0.065–0.568 | 0.044 | 0.016–0.111 | 0.069 |

## Interpretation

- `right_posrot` has a reproducible learnable signal in this development protocol.
- `spine_position` also shows signal, but only six positives make the confidence interval wide.
- `left_posrot` is near chance and should not be presented as a successful learned detector.
- Both hip ROI criteria are too sparse for a reliable standalone supervised model; their wide confidence intervals reflect this.
- These results do not justify replacing deterministic geometry/routing with the classifiers.

## V6.8 probability semantics

`quality_prob` is the continuous **risk score for an image-level quality violation**, in `[0,1]`. It is computed as the maximum of the deterministic violation risk and available criterion-model probabilities. It is no longer inverted from the generic confidence field. The current value is probability-like/model-risk output, not a clinically calibrated probability. Formal calibration remains a later step requiring a dedicated development calibration protocol.

## Routing

V6.8 keeps the V6.7.1 two-image study logic and adds a composition guard for valid `spine + single-hip` studies where the hip can be mistaken for a second spine by the single-image heuristic. On the supplied 100-study labelled set, all labelled criterion samples are now routable (0 missing routes).
