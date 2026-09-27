# DXA next phase

## Decisions incorporated from the expert Q&A

- Target acquisition device: GE Lunar Prodigy Advance.
- Pixel size: X = 0.60 mm/px; Y = 1.05 mm/px.
- Quality output is mandatory as binary 0/1 (`acceptable` / `issue_detected`).
- Confidence may be emitted as an additional field.
- Output is one row per DICOM image; duplicate pixel data must be deduplicated for inference while preserving the original output rows.
- Missing criterion labels generally mean that the corresponding anatomical examination was not performed.
- Scoliosis is a separate finding and must not automatically be treated as positioning failure.
- Endoprosthesis is a separate finding and must not automatically be treated as a quality violation.
- Border black anonymisation blocks on hip images are acquisition/de-identification artifacts and must not drive the classifier.
- `unknown` is supported for non-DXA / unsupported anatomy.
- Organiser terminology is intentionally isolated behind `app/terminology`.

## Current baseline status

The repository now contains a deterministic, explainable routing/quality baseline and a batch inference entry point. It is **not presented as a clinically validated model**. The next ML step is criterion-level supervised training using study-grouped splits and the supplied expert labels.

## Physical ROI geometry

The known pixel dimensions allow conversion between pixel deltas and physical distances:

- `dx_mm = dx_px * 0.60`
- `dy_mm = dy_px * 1.05`
- `distance_mm = hypot(dx_mm, dy_mm)`

The ROI criterion should only be emitted as a definitive violation after anatomical landmarks/ROI can be detected reliably. The code therefore does not fabricate a 3 cm verdict from arbitrary image borders.

## Training plan

1. Build a study-level manifest and deduplicate pixel-identical DICOMs.
2. Keep all images from one study in exactly one split.
3. Train/evaluate region routing first.
4. Train criterion classifiers separately for spine and hip where labels exist.
5. Keep scoliosis/endoprosthesis as separate findings.
6. Evaluate overall and by anatomical region/criterion with F1, sensitivity, specificity, balanced accuracy and ROC/PR AUC where applicable.
7. Add confidence calibration.
8. Add landmark/ROI localization as an optional bonus layer.
9. Add external public datasets only where they improve a clearly identified weak component.


## Current implementation pass

The backend now invokes the study-aware DXA baseline directly, while keeping the old MockMLAdapter name only as a compatibility alias. A terminology catalog is packaged with the backend. The training pipeline includes leakage-safe study splitting and criterion-support auditing before weight training.

## V6.3 correction: hip ROI semantics

The figure from the methodological guidance clarifies that the 3 cm / 3 cm / 2 cm values are visualization margins around the area of interest, not fixed padding to add to a detected femur bounding box. The lateral 2 cm margin is side-dependent. Therefore a candidate femur bbox is only an anatomical anchor; available image margins are reported separately and are not, by themselves, the final ROI classifier.
