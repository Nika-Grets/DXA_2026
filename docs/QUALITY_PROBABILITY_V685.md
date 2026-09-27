# `quality_prob` — V6.8.5

`quality_prob` remains an image-level continuous risk score for a quality violation in `[0,1]`.

## Calibration

Criterion-model probabilities are passed through a Platt logit calibration map only when the map was fitted from leakage-safe 5-fold grouped OOF predictions and the development OOF signal supports a monotone calibration (`ROC-AUC >= 0.60`, positive calibration slope).

In the current data this enables calibration for:

- `spine_position`
- `spine_axis`
- `right_posrot`

The remaining criterion heads are left on their raw model probability scale because their OOF evidence is too weak or their fitted calibration slope reverses the ranking. They are not treated as validated probabilities.

The deterministic rule risk remains part of the final `quality_prob` aggregation. The final image-level score is the maximum of the applicable deterministic risk and criterion-model risk values.

## Interpretation

This is a **calibrated probability-like development score**, not a clinically validated probability. Calibration was fitted from OOF predictions, but there is no separate independent calibration cohort. Therefore OOF calibration diagnostics must not be reported as independent test performance.
