# Corrected-routing OOF decision — V6.9 MVP

Date: 2026-09-25

## Scope

A leakage-safe grouped 5-fold OOF benchmark was rerun for the three spine criteria after the routing fix for studies with more than three images.

- Grouping: `StudyInstanceUID`
- Folds: `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`
- N: 99 labelled studies
- Bootstrap: 4000 replicates, seed 42
- Routing: current corrected `classify_study()` (`corrected_all_images`)
- No production `.joblib` files were overwritten by this diagnostic run.

## Results at the existing 0.50 decision threshold

| Criterion | Positives | F1 | Sensitivity | Specificity | ROC-AUC | PR-AUC | 95% CI F1 |
|---|---:|---:|---:|---:|---:|---:|---|
| spine_position | 6 | 0.000 | 0.000 | 1.000 | 0.821 | 0.345 | 0.000–0.000 |
| spine_axis | 10 | 0.000 | 0.000 | 0.966 | 0.596 | 0.167 | 0.000–0.000 |
| spine_artifact | 17 | 0.083 | 0.059 | 0.927 | 0.557 | 0.212 | 0.000–0.261 |

## Interpretation

The routing fix was necessary: it corrected cases where a hip image was selected instead of a later spine image. However, the corrected-routing OOF run does **not** support promotion of any of the three spine benchmark heads as a validated production model at the current 0.50 threshold.

The full-data result that previously looked like `spine_artifact` F1=1.0 was therefore correctly treated as a regression/forensic signal, not validation. It is explained by the fact that the final head was fit on the same labelled studies.

For the intermediate MVP, `spine_artifact` remains enabled in the current production path because the task requires the criterion to be represented and the head provides non-zero behaviour. It must be labelled as development/MVP evidence, not independent validation, and should not be used as a claim of validated clinical performance.

## Threshold diagnostic

A separate fold-local threshold diagnostic shows that the heads contain some probability-ranking signal, especially `spine_position` (OOF ROC-AUC 0.821), but lowering thresholds substantially increases false positives. These thresholds were not promoted to production because they require a separate threshold-selection protocol and do not constitute independent validation.

## Files

- `artifacts/corrected_routing_oof/results.json`
- `artifacts/corrected_routing_oof/oof_predictions.json`
- `artifacts/corrected_routing_oof/rows.json`
- `artifacts/corrected_routing_oof/routing.csv`
- `artifacts/corrected_routing_oof/threshold_diagnostic.json`
