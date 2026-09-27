# V6.9 — right_posrot production decision

Date: 2026-09-25

## Decision

Promote **only `right_posrot`** into the default MVP production decision path.

Keep `spine_artifact`, `left_posrot`, `right_roi`, `left_roi`, `spine_position`, and `spine_axis` benchmark heads out of the default decision path for now. They remain available for controlled experiments through `ENABLE_EXPERIMENTAL_BENCHMARK_HEADS=true`.

No retraining was performed.

## Evidence used for the decision

The leakage-safe OOF benchmark was generated with study-level grouping (`StudyInstanceUID`). For `right_posrot`:

- N = 72
- positives = 17
- OOF ROC-AUC = 0.769
- 95% CI = 0.616–0.904
- OOF PR-AUC = 0.495

At the existing production threshold `p >= 0.50` on the OOF predictions:

- TP = 7
- FP = 6
- FN = 10
- TN = 49
- sensitivity = 0.412
- specificity = 0.891
- F1 = 0.467

This is development/validation evidence, not closed-test performance.

## Controlled full-data diagnostic

Using the existing final `right_posrot.joblib` (already fitted on all labelled data), the current 100-study labelled set was run through the exact production feature/decision function with only the right-posrot head injected.

This diagnostic produced 12 right-hip positive studies, of which 11 matched expert-positive studies and 0 matched expert-negative studies. Because the final model was fitted on these same labelled studies, this result is **not** an independent validation metric and must not be reported as such.

At the overall study screen, the diagnostic changed:

- F1: 0.301 → 0.463
- sensitivity: 0.229 → 0.396
- specificity: 0.731 → 0.712

These values are useful only as a regression/sanity check for the code path.

## Why the other heads stay out

- `spine_artifact`: OOF AUC ≈ 0.546; current production had zero detections because benchmark heads were disabled. Enabling it blindly is not justified.
- `left_posrot`: OOF AUC ≈ 0.489; near chance.
- `right_roi`: OOF AUC ≈ 0.604 with only 3 positives; too sparse for a reliable standalone decision head.
- `left_roi`: OOF AUC ≈ 0.301; weak and only 4 positives.
- `spine_position`: OOF AUC ≈ 0.826, but only 6 positives; the confidence interval is wide (0.555–0.982). Keep deterministic geometry as the production decision and do not silently replace it with the classifier.
- `spine_axis`: OOF AUC ≈ 0.631; keep deterministic geometry as the production decision.

## Code change

`backend/app/ml/dexa_baseline.py` now has an explicit production allowlist:

```python
PRODUCTION_BENCHMARK_HEADS = ("right_posrot",)
```

When `ENABLE_EXPERIMENTAL_BENCHMARK_HEADS=false`, only this head is loaded for the production decision path. When the flag is true, all benchmark heads can still be loaded for experiments.

The change was syntax-checked and the default loader was verified to load exactly `['right_posrot']`.

## Next action

Freeze this model decision for the MVP and move to the frontend/integration work. Do not spend the remaining time retraining classifiers. Keep the known limitations in the README and MVP documentation, and report OOF metrics rather than the full-data diagnostic as validation performance.
