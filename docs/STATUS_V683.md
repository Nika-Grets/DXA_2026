# STATUS V6.8.3 — ROI candidate score

Date: 2026-09-20

V6.8.3 is an experimental ROI-analysis increment.

## Included

- `artifacts/v68_3_roi_candidate_score.py`
- `artifacts/v68_3_roi/results.json`
- `artifacts/v68_3_roi/records.json`
- `artifacts/v68_3_roi/REPORT.md`

## Result

The interpretable `q60_sx` candidate score reaches ROC-AUC 0.833 and PR-AUC 0.516 on 150 grouped development observations with 7 positive ROI labels. Study-level bootstrap 95% CI for AUC is 0.490–0.991.

The result is exploratory. No production threshold, model, routing rule, or quality probability was changed.
