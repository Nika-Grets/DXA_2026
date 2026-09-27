# V6.7 verification status

## Static / logic verification completed

- Python `compileall` passed for `backend/app` and `backend/tests` before cache cleanup.
- `canonical_manifest.json` validated: 100 studies, 80 train / 20 validation, unique source-folder and DICOM StudyInstanceUID mappings.
- Canonical split cross-check passed against the manifest.
- Direct execution of the spine localizer synthetic anisotropic-spacing case passed: raw pixel-space angle ~17.10°, physical angle ~9.97° for a 10° target.
- Direct execution of the hip localizer + production quality path passed; the synthetic case did not raise `HIP_ROI` solely from the new ROI criterion.

## Full pytest status

The full backend pytest suite was not executable in the current analysis runtime because `pydicom`
is not installed there. The repository's existing DICOM tests therefore remain to be run in the
normal dependency-complete environment.

This is an environment limitation, not a test failure of the modified code.
