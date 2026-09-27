# V6.7.1 status — routing and output-contract fix

## Fixed

1. **Two-image study routing.** A study containing two DICOM images is no longer forced through the legacy multi-image fallback that always selected one image as spine. Each image is classified independently first; bilateral hip pairs and spine+hip pairs are preserved.
2. **Regression coverage.** Added focused routing tests for bilateral two-image hip studies and spine+hip two-image studies.
3. **`quality_prob` contract.** The output remains explicitly defined as the probability-like score of a quality violation in `[0,1]`, consistent with `quality_class=1` meaning `issue_detected`. The current deterministic baseline is **not calibrated** and must not be presented as a calibrated clinical probability.
4. **Batch contract tests.** Updated the expected CSV schema to include `confidence`, `quality_prob` and `findings`, which are already emitted by the current batch service.

## Frozen test-fragment check

The supplied `Для теста.zip` contains one single-image spine study and one two-image bilateral-hip study. With the V6.7.1 routing logic, the two hip images route as:

- `CR000000_ППОБ.dcm` → `femur_right`
- `CR000001_ЛПОБ.dcm` → `femur_left`

The fragment is explicitly described by the TЗ as a format/debugging resource, not as an expert-labelled final test set. Therefore these files are used here only for routing/loader validation, not for sensitivity/specificity claims.

## Known limitations retained from V6.7

- Production-default classifier heads remain conservative and incomplete; no independent performance claim is made from the 100 labelled studies because the serialized production models were refit on labelled data.
- `quality_prob` is not calibrated. Calibration/OOF provenance belongs to V6.8.
- Containerization, pinned dependencies and final README/release packaging remain V6.9 work.
