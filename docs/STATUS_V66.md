# V6.6 status — independent audit + safety hardening

## Current state

V6.5 was independently audited by a second engineer workflow. The study-level split and GroupKFold discipline were reproduced. The documented hip position/rotation result (ROC-AUC ~0.731) was independently reproduced on the raw DICOM archive.

## Findings carried into V6.6

- Study-level split: retained.
- Experimental benchmark heads: remain disabled by default.
- Confirmed hip localization failure cases: `968726_right` (ilium leakage) and `113784_left/right` (magnification/crop sensitivity) retained as regression cases.
- Pelvis external dataset: not used for supervised pretraining; modality/population mismatch documented in `artifacts/independent_review/ANATOMY_RESEARCH.md`.
- VerSe: not used as a direct CT→DXA model transfer; deferred to the spine track.

## Experiments

A naive shaft-width scale-invariant proximal search was tested and rejected because it degraded both hip criteria on the fixed validation split. An adaptive Hough-head radius experiment produced position/rotation ROC-AUC 0.750 vs 0.731 baseline, but AP decreased and ROI ROC-AUC also decreased; it remains experimental and is not promoted.

## Production change

`DicomService.parse_bytes()` now normalizes MONOCHROME1 images before ML inference. This closes a latent modality-handling gap identified in the independent audit. The project test for this behavior was added but must be executed in the normal dependency-complete environment because this runtime lacks `pydicom`.

## Next work

1. Finish the spine localization track.
2. Build criterion models on top of stable anatomy/geometry.
3. Calibrate thresholds using training-only/OOF procedures.
4. Run the complete TЗ benchmark.
5. Finalize reproducibility paths/configuration and Docker/demo validation.
