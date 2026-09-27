# DXA V6.2 status

## Main change
The anatomical routing API now preserves the source image index in `RegionPrediction.image_index`.
The study adapter maps routes by that index instead of assuming that semantic output order equals input DICOM order.
This is important because the three-image router returns semantic regions as spine/left-hip/right-hip, while DICOM image order is not guaranteed to match that order.

## Spine
- Three-image anatomical pattern: 74/74 studies in the audit had the expected left/spine/right side-shift pattern.
- A deterministic spine centerline candidate remains available.
- The centerline is **not** promoted to the final `>5°` clinical/quality decision yet; current localization axis has insufficient criterion-level validation.

## Hip
`backend/app/ml/hip_localizer.py` adds an explainable proximal-femur candidate localizer:
- robust normalization;
- black-edge/anonymization suppression;
- high-density bone candidate mask;
- connected-component selection;
- side-aware femur candidate bbox;
- ROI geometry candidate using the supplied 20 mm side and 30 mm top/bottom physical margins.

Audit on routed hip images:
- 153 hip image candidates;
- localization confidence median ~0.716.
- 151/153 candidate ROI boxes touch an image boundary. This is **not** treated as a violation: the cropped DXA acquisition often does not contain the full physical clearance around the candidate bone, and the external ROI criterion still requires proper anatomical interpretation. Boundary contact is retained only as a diagnostic signal.

## Important limitation
The hip localizer is an anatomical candidate generator, not a validated ROI classifier or segmentation model. External Pelvis FEMUR masks are used as a prior; no direct DXA transfer performance claim is made.

## Environment note
The current analysis container does not have `pydicom`, so the full pytest suite cannot be executed here because `tests/conftest.py` imports pydicom. Pure module compilation and standalone routing/localization checks were run. Docker/CI with project dependencies remains the authoritative integration test.
