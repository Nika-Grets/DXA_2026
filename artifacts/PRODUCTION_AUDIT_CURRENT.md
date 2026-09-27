# Production audit — V6.9 current run

Date: 2026-09-25

This is an audit of the existing `data/training_batch.csv` against `artifacts/canonical_manifest.json`. No retraining was performed. The left/right hip side was reconstructed with the same `classify_study()` routing logic used by the production adapter because `anatomical_region` in the output intentionally does not encode side.

## Overall quality screen

Study-level definition: expert-positive if any available one of the seven canonical criteria is positive; predicted-positive if any output row for that study has `quality_class=1`.

- N = **100** studies
- Expert-positive = **48**
- Predicted-positive = **25**
- F1 = **0.301** (95% bootstrap CI 0.164–0.434)
- Sensitivity = **0.229** (95% bootstrap CI 0.119–0.356)
- Specificity = **0.731** (95% bootstrap CI 0.603–0.848)

This is a development-set diagnostic, not closed-test performance.

## Criterion-level study metrics

| Criterion | N | Positive | Pred+ | TP | FP | FN | F1 | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spine_position | 99 | 6 | 0 | 0 | 0 | 6 | 0.000 | 0.000 | 1.000 |
| spine_axis | 99 | 10 | 8 | 1 | 7 | 9 | 0.111 | 0.100 | 0.921 |
| spine_artifact | 99 | 17 | 0 | 0 | 0 | 17 | 0.000 | 0.000 | 1.000 |
| right_posrot | 72 | 17 | 0 | 0 | 0 | 17 | 0.000 | 0.000 | 1.000 |
| right_roi | 72 | 3 | 11 | 1 | 10 | 2 | 0.143 | 0.333 | 0.855 |
| left_posrot | 78 | 19 | 2 | 0 | 2 | 19 | 0.000 | 0.000 | 0.966 |
| left_roi | 78 | 4 | 7 | 0 | 7 | 4 | 0.000 | 0.000 | 0.905 |

The full bootstrap intervals are in `production_criterion_metrics.csv`.

## Area-level screening

| Area | N | Positive | Pred+ | F1 | Sensitivity | Specificity |
|---|---:|---:|---:|---:|---:|---:|
| SPINE | 99 | 31 | 8 | 0.154 | 0.097 | 0.926 |
| HIP_RIGHT | 72 | 19 | 11 | 0.267 | 0.211 | 0.868 |
| HIP_LEFT | 78 | 22 | 9 | 0.000 | 0.000 | 0.839 |
| HIP | 78 | 28 | 19 | 0.255 | 0.214 | 0.740 |
| OVERALL | 100 | 48 | 25 | 0.301 | 0.229 | 0.731 |

## What the current output actually detects

Current `training_batch.csv` contains only three violation strings:

- `Некорректная область интереса`: 38 image rows
- `Не выравнена ось позвоночника`: 22 image rows
- `Некорректная укладка`: 5 image rows

There are **0** `Присутствуют посторонние предметы` detections and **0** right-hip rotation detections.

## Block B — root causes

### 1. SPINE_ARTIFACT = 0 detections

This is directly explained by the frozen production gate:

`ENABLE_EXPERIMENTAL_BENCHMARK_HEADS=false`

With that flag off, `_criterion_prob()` returns `None` for the stored benchmark heads, so the `SPINE_ARTIFACT` branch in `evaluate_quality()` cannot append the violation at all.

The stored calibrator is also disabled for `spine_artifact`. The OOF benchmark head itself is weak: AUC ≈ 0.546, and at a 0.50 threshold it had 0 true positives on the OOF development predictions. Therefore **simply enabling it is not justified**.

### 2. HIP_POSITION_ROTATION = almost entirely absent

The default production path does not contain a dedicated anatomical rotation measurement. With benchmark heads disabled, hip rotation can fire only from coarse fallback gates:

- localizer confidence < 0.20
- bbox width < 0.25
- bbox height < 0.65
- bbox center offset > 0.28
- `abs(side_shift) < 0.015`

On the current 333 routed hip images, the observed ranges were:

- minimum localizer confidence: **0.715**
- minimum absolute `side_shift`: **0.126**
- `side_shift < 0.015`: **0 images**
- localizer confidence < 0.20: **0 images**
- bbox/center fallback failures: **5 images**

Those five image-level fallback detections all occurred on the **left hip**; none corresponded to a dedicated rotation-specific signal. This is why the current CSV contains no right-hip rotation detections and only two left-hip studies with the generic `Некорректная укладка` result.

The stored OOF benchmark evidence is materially different: `right_posrot` has documented OOF AUC ≈ 0.769, while `left_posrot` is near chance at ≈ 0.489. That means the existing right-hip head is worth a separate controlled production experiment; the left head is not.

## Decision after this audit

Do **not** retrain anything yet.

The next model-side task should be a small controlled experiment around the **existing `right_posrot` head only**, using the current production decision path and the leakage-safe OOF evidence already in the repository. Keep `spine_artifact` and `left_posrot` out of production decisions for now.
