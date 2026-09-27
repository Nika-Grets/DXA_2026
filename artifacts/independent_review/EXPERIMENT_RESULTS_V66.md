# Independent follow-up experiments for V6.6

## Scope

These experiments were run independently against the raw organizer DICOM archive using a minimal uncompressed-DICOM reader because the runtime did not have `pydicom` installed. The project code itself declares/uses `pydicom`; the production unit test suite could therefore not be executed in this runtime.

All classifier experiments reused the fixed study-level split from `artifacts/study_split.json`, selected models only on the training studies with GroupKFold, and evaluated once on the fixed validation studies.

## 1. Naive scale-invariant proximal search

Hypothesis: replacing image-height fractions in `_proximal_box` with a multiple of an estimated shaft width will fix magnification views.

Result: **reject this exact variant**.

- Hip position/rotation ROC-AUC: 0.7311 → 0.6477
- Hip position/rotation AP: 0.5843 → 0.4226
- Hip ROI ROC-AUC: 0.8125 → 0.6354

Conclusion: the idea is plausible, but this naive implementation makes the anatomy crop less stable. It must not be promoted.

## 2. Adaptive Hough-head radius

Hypothesis: scale the Hough-circle femoral-head radius range from an estimated visible shaft width instead of full image width.

Result:

- Hip position/rotation ROC-AUC: 0.7311 → 0.7500
- Hip position/rotation AP: 0.5843 → 0.5591
- Hip ROI ROC-AUC: 0.8125 → 0.8021

The aggregate change is not established as an improvement. It remains experimental.

## 3. Head-anchor that can expand/shrink the box

A more aggressive variant was tested to cover both observed failure modes: ilium leakage and magnification views. It substantially altered many crops and degraded validation ROC-AUC, so it is rejected.

## 4. Production safety patch: MONOCHROME1

`PredictionService` passes `ParsedDicom.pixels` directly to ML. `DicomService.preview_array()` already inverted MONOCHROME1 for display, but `parse_bytes()` did not normalize MONOCHROME1 before ML inference.

The V6.6 code now normalizes MONOCHROME1 after modality LUT using the finite min/max intensity range. This is a robustness fix, not a performance claim.

The corresponding unit test was added. It could not be executed in this runtime because `pydicom` is not installed here; run the normal project test suite in the project environment before release.
