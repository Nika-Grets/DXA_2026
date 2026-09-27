# V6.8.5 — quality probability calibration

Date: 2026-09-20

## Added

- Leakage-safe OOF-derived Platt calibration maps for criterion-model probabilities.
- `artifacts/models/quality_calibrators.json` with calibration provenance and diagnostics.
- Runtime loading of supported calibration maps in `quality_prob` calculation.
- Regression tests for calibration provenance and monotone ranking.

## Enabled calibration heads

- `spine_position`
- `spine_axis`
- `right_posrot`

## Deliberately not calibrated

`spine_artifact`, `right_roi`, `left_posrot`, and `left_roi` are left on their raw model probability scale because their OOF evidence is insufficient or the fitted calibration slope reverses the ranking.

## Unchanged

- Study routing.
- Criterion decision thresholds.
- ROI geometry thresholds.
- `quality_class` production decision path.
- Experimental landmark/ROI branches remain non-production.

## Validation

- Python compile checks: PASS.
- Direct calibration regression tests: PASS.
- Full pytest collection remains blocked by the environment's missing `pydicom` dependency.
- Supplied `Для теста.zip` routing replay remains correct for the 1-spine and 2-hip study composition.
