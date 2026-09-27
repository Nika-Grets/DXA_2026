# V6.7 status — production alignment

## Implemented

1. Canonical study manifest with explicit `source_folder_id -> StudyInstanceUID -> SeriesInstanceUID -> SOPInstanceUID` mapping.
2. Canonical split keyed by DICOM `StudyInstanceUID`.
3. Production spine criterion now calls `localize_spine()` and evaluates the mandatory 5° axis criterion in physical coordinates using `PIXEL_X_MM / PIXEL_Y_MM`.
4. Production hip criteria now call `localize_hip()`.
5. `HIP_ROI` is now a real deterministic geometry criterion: lateral margin >= 20 mm and superior/inferior margins >= 30 mm, measured from the localized proximal-femur candidate to the image borders.
6. MONOCHROME1 preview no longer double-inverts pixels after ingestion has normalized them for ML.
7. Added regression tests for physical spine angle handling, anatomy-localizer integration and MONOCHROME1 preview orientation.

## Deliberately unchanged

- Experimental serialized benchmark heads remain disabled by default.
- The rejected scale-invariant and adaptive-Hough experiments are not promoted.
- No new classifier selection was performed on the repeatedly inspected V6.6 validation split.
- Scoliosis and endoprosthesis remain findings rather than automatic quality violations.

## Next gate

Run the complete dependency-backed backend test suite and a single frozen benchmark using
`study_split_canonical.json`. Treat the old V6.6 validation split as development validation,
not as an untouched final test set.
