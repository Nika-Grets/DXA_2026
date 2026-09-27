# Production evaluation — current frozen output

This report evaluates the already-produced production CSV against the canonical study labels. It does not retrain models.

## Overall quality screen

**N=100 studies**; expert-positive=48; predicted-positive=44.

- F1: **0.630** (95% bootstrap CI 0.506–0.736)
- Sensitivity: **0.604** (95% bootstrap CI 0.462–0.741)
- Specificity: **0.712** (95% bootstrap CI 0.583–0.830)

## Criterion-level

| Criterion | N | Pos | Pred+ | TP | FP | FN | F1 | Sensitivity | Specificity | Note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| left_posrot | 78 | 19 | 2 | 0 | 2 | 19 | 0.000 | 0.000 | 0.966 |  |
| left_roi | 78 | 4 | 7 | 0 | 7 | 4 | 0.000 | 0.000 | 0.905 | few positives |
| right_posrot | 72 | 17 | 11 | 11 | 0 | 6 | 0.786 | 0.647 | 1.000 |  |
| right_roi | 72 | 3 | 11 | 1 | 10 | 2 | 0.143 | 0.333 | 0.855 | few positives |
| spine_artifact | 99 | 17 | 17 | 17 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| spine_axis | 99 | 10 | 8 | 1 | 7 | 9 | 0.111 | 0.100 | 0.921 |  |
| spine_position | 99 | 6 | 0 | 0 | 0 | 6 | 0.000 | 0.000 | 1.000 | few positives |

95% bootstrap CIs are stored in `production_criterion_metrics.csv`. For rare criteria with very few positives, intervals are expected to be wide and should not be over-interpreted.

## Area-level screening

| Area | N | Pos | Pred+ | F1 | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|
| SPINE | 99 | 31 | 23 | 0.667 | 0.581 | 0.926 |
| HIP_RIGHT | 72 | 19 | 20 | 0.667 | 0.684 | 0.868 |
| HIP_LEFT | 78 | 22 | 9 | 0.000 | 0.000 | 0.839 |
| HIP | 78 | 28 | 27 | 0.509 | 0.500 | 0.740 |

## Routing sanity check

- femur_left: 169 images
- spine: 166 images
- femur_right: 164 images
- Total routed images: 499 across 100 studies

## Interpretation notes

- This is a study-level aggregation of the image-level production CSV: a study is predicted positive when any relevant image is predicted positive.
- Left/right hip criteria are evaluated after reconstructing the same current `classify_study()` route from the DICOM images, because the CSV's `anatomical_region` field intentionally does not encode side.
- These are development-set measurements; they are not independent closed-test performance.
