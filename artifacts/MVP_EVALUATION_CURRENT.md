# V6.9 MVP — current development evaluation

Date: 2026-09-25

## Scope

This is a **development/regression evaluation**, not an independent closed-test result. No model was retrained.

The seven organiser criteria are all evaluated and reported separately:

- spine_position
- spine_axis
- spine_artifact
- right_posrot
- right_roi
- left_posrot
- left_roi

Study-level aggregation is used: a study is positive for a criterion when at least one routed image receives that criterion violation.

## MVP composite used for this audit

The composite CSV `data/training_batch_mvp_composite.csv` starts from the existing production batch and adds two controlled existing-head diagnostics:

1. `spine_artifact` — existing `spine_artifact.joblib` applied to the **corrected spine routing**. The >3-image routing bug was fixed; the final full-data head was not retrained.
2. `right_posrot` — existing `right_posrot.joblib` diagnostic already present in `data/training_batch_right_posrot_experiment.csv`.

The remaining criteria come from the existing production decision output. Therefore this file is a **composite MVP regression artifact**, not a clean single-run production CSV.

## Overall screen

- N = 100 studies
- Expert-positive = 48
- Predicted-positive = 44
- F1 = 0.630 (95% bootstrap CI 0.506–0.736)
- Sensitivity = 0.604 (95% bootstrap CI 0.462–0.741)
- Specificity = 0.712 (95% bootstrap CI 0.583–0.830)

For comparison, the unaugmented existing production CSV was F1 0.301 / sensitivity 0.229 / specificity 0.731 on the same development labels.

## Seven mandatory criteria

| Criterion | N | Positive | Pred+ | TP | FP | FN | F1 | Sensitivity | Specificity | 95% CI / note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| spine_position | 99 | 6 | 0 | 0 | 0 | 6 | 0.000 | 0.000 | 1.000 | very sparse positives |
| spine_axis | 99 | 10 | 8 | 1 | 7 | 9 | 0.111 | 0.100 | 0.921 | F1 CI 0.000–0.333 |
| spine_artifact* | 99 | 17 | 17 | 17 | 0 | 0 | 1.000 | 1.000 | 1.000 | regression-only; trained on same labels |
| right_posrot* | 72 | 17 | 11 | 11 | 0 | 6 | 0.786 | 0.647 | 1.000 | regression-only full-data head |
| right_roi | 72 | 3 | 11 | 1 | 10 | 2 | 0.143 | 0.333 | 0.855 | very sparse positives |
| left_posrot | 78 | 19 | 2 | 0 | 2 | 19 | 0.000 | 0.000 | 0.966 | weak current signal |
| left_roi | 78 | 4 | 7 | 0 | 7 | 4 | 0.000 | 0.000 | 0.905 | very sparse positives |

`*` The two starred rows are controlled regression diagnostics using existing fitted heads. They must not be reported as independent validation performance.

Full bootstrap output is in `artifacts/mvp_eval/production_criterion_metrics.csv`.

## Production decision for the intermediate MVP

- Keep the corrected all-image routing.
- Keep `right_posrot` enabled: its existing leakage-safe OOF evidence is the strongest of the benchmark heads currently available.
- Enable `spine_artifact` for the intermediate MVP because otherwise this mandatory criterion has zero production detections; record it explicitly as **development/regression-only evidence** until corrected-routing leakage-safe OOF is regenerated.
- Keep `left_posrot`, `left_roi`, and `right_roi` on their current deterministic/experimental paths; do not promote new fitted heads solely from the full-data diagnostics.
- `spine_position` and `spine_axis` remain counted as mandatory metrics. Their old OOF evidence should not be silently presented as validation of the corrected routing.

## Important interpretation

The jump in the artifact metric is not a claim of model quality. The forensic result is that the old route frequently fed the wrong image to the artifact head; after routing correction, the existing fitted head produces a strong full-data separation. The next validation step is a fresh study-grouped OOF run using the corrected router.
