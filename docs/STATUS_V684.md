# STATUS V6.8.4 — small side-aware ROI model

Date: 2026-09-20

## Goal

Test whether a small interpretable ROI model (2–4 anatomical features) improves the single `q60_sx` candidate under the same grouped 5-fold OOF protocol.

## Dataset/protocol

- 150 hip-side observations
- 100 unique studies as grouping unit
- 7 positive ROI labels
- `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`
- LogisticRegression with StandardScaler, `C=0.1`, `class_weight=balanced`
- OOF probabilities only; no production threshold selected

## Result

Using the same implementation/protocol, the single `q60_sx` feature reached:

- ROC-AUC 0.822
- PR-AUC 0.367

Small feature combinations did not improve it:

- q60_sx + q70_sx: ROC-AUC 0.791, PR-AUC 0.332
- q60_sx + q60 occupancy: ROC-AUC 0.822, PR-AUC 0.367
- q60/q70/q80 spread: ROC-AUC 0.732, PR-AUC 0.272
- 10-feature small model: ROC-AUC 0.721, PR-AUC 0.139

Grouped bootstrap 95% CI for the 10-feature model: 0.389–0.921.

## Decision

Do NOT replace the `q60_sx` candidate with a multifeature ROI model. Keep `q60_sx` as an experimental candidate only.

No production routing, ROI threshold, `quality_prob`, or serialized production model was changed.

The previous V6.8.3 exploratory result reported q60_sx AUC 0.833. Re-running the same feature with the V6.8.4 implementation/protocol gives 0.822; the difference is attributable to implementation/protocol consistency and reinforces that the result is exploratory rather than a stable benchmark.
