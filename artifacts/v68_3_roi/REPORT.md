# V6.8.3 — ROI candidate-score experiment

## Scope

This experiment investigates the very rare hip ROI criterion. It is **development-only** and does not change production routing, classification, `quality_prob`, or serialized production models.

## Dataset

- 150 hip-side observations with criterion-level ROI labels.
- 7 positive ROI labels.
- Grouping key: actual DICOM `StudyInstanceUID`.
- Source labels are taken from `разметка.xlsx` and mapped through the canonical manifest.

## Candidate feature

`q60_sx` is the normalized horizontal standard deviation of pixels above the 60th percentile inside the existing shaft-anchored proximal-femur crop. The crop is mirrored for the left side, so the feature is defined in a common anatomical coordinate frame.

This is intentionally a single, interpretable feature. No threshold is promoted to production.

## Results

Grouped development analysis:

- ROC-AUC: **0.833**
- PR-AUC: **0.516**
- Study-level bootstrap 95% CI for AUC: **0.490–0.991**
- Right: AUC **0.676** (3 positives / 72)
- Left: AUC **0.959** (4 positives / 78)

The wide confidence interval is expected because there are only 7 positive labels.

## Threshold diagnostics

These are descriptive only and were not selected as a production operating point:

| threshold | TP | FP | FN | TN | sensitivity | specificity |
|---:|---:|---:|---:|---:|---:|---:|
| 0.230 | 6 | 23 | 1 | 120 | 0.857 | 0.839 |
| 0.235 | 6 | 13 | 1 | 130 | 0.857 | 0.909 |
| 0.240 | 5 | 8 | 2 | 135 | 0.714 | 0.944 |
| 0.250 | 3 | 4 | 4 | 139 | 0.429 | 0.972 |
| 0.270 | 2 | 0 | 5 | 143 | 0.286 | 1.000 |

## Interpretation

The candidate is materially more informative than the current all-feature anatomy experiment (ROI ROC-AUC ~0.591), but this is **not yet evidence for a production ROI detector**. The signal is concentrated in a very small positive set and is substantially stronger on the left side.

The next experiment should test the feature with a strictly predefined rule or a tiny side-aware model under grouped OOF, with the operating point fixed before evaluation. It should also inspect the seven positive studies individually because one positive case is associated with the comment `перелом`, which may represent a different visual mechanism from pure ROI placement.

No production artifact was changed by this experiment.
