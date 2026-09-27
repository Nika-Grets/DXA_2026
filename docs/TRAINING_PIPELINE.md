# DXA training pipeline

## Ground-truth rules

- Join labels by the source folder identifier used in `разметка.xlsx`, then resolve that identifier to the actual DICOM `StudyInstanceUID` using `artifacts/canonical_manifest.json`.
- Use DICOM `StudyInstanceUID` as the canonical ML grouping and split key; retain `source_folder_id`, `SeriesInstanceUID` and `SOPInstanceUID` for traceability.
- Split by study, never by image.
- Preserve criterion-level labels; do not reconstruct them from aggregate columns.
- Empty cells mean no supplied criterion label and are not converted to zero.
- Pixel-identical duplicates are detected for training hygiene but source paths remain available for audit.

## Current supervised targets

Spine: `spine_position`, `spine_axis`, `spine_artifact`.

Hip: `right_posrot`, `right_roi`, `left_posrot`, `left_roi`.

`SCOLIOSIS` and `ENDOPROSTHESIS` are findings, not automatic quality violations.

## Commands

```bash
python artifacts/tools/build_canonical_manifest.py \
  --root /data/training/Исследования \
  --xlsx /data/training/разметка.xlsx \
  --split artifacts/study_split.json \
  --out artifacts/canonical_manifest.json

python artifacts/validation/validate_canonical_manifest.py \
  artifacts/canonical_manifest.json

```

The last command is deliberately a scaffold: it audits class support before any weights are trained. ROI positives are too sparse for an unqualified standalone supervised model; do not fabricate positives or silently merge criteria.
