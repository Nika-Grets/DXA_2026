# STATUS V6.8.5 — quality probability calibration

## Implemented

- Added leakage-safe OOF-derived Platt calibration maps for criterion-model probabilities.
- Enabled calibration only for criterion heads with positive monotone calibration slope and OOF ROC-AUC >= 0.60.
- Current enabled heads: `spine_position`, `spine_axis`, `right_posrot`.
- Weak/reversed heads remain uncalibrated rather than being artificially inverted.
- `quality_prob` still aggregates deterministic violation risk and applicable model risk using the maximum.
- Added provenance in `artifacts/models/quality_calibrators.json`.

## Not claimed

- No independent calibration cohort exists.
- `quality_prob` is not a clinically validated probability.
- No production quality-class threshold was changed.
- No routing, ROI threshold, or production criterion decision was changed.

## Decision

Use the calibrated maps only as a probability-scale improvement for the supported heads. Keep weak heads raw and visible in provenance rather than forcing a calibration transform that would reverse their learned ranking.
