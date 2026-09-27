# V6.7 canonical study manifest

## Purpose

The label workbook identifies studies by the source folder name, while the DICOM
objects contain the actual `StudyInstanceUID`. These identifiers are not the same
in the supplied training archive.

`artifacts/canonical_manifest.json` therefore retains both identifiers and nests:

```text
source_folder_id
  -> study_uid (DICOM StudyInstanceUID)
      -> series_uid
          -> sop_uid
```

The canonical ML grouping key is **`study_uid`**. `pixel_sha256` is retained only
for duplicate hygiene and audit; it must not be used as a study grouping key.

`artifacts/study_split_canonical.json` contains the existing V6.6 train/validation
assignment rewritten from source-folder IDs to the corresponding DICOM
`StudyInstanceUID` values.

## Rebuild

```bash
python artifacts/tools/build_canonical_manifest.py \
  --root /data/training/Исследования \
  --xlsx /data/training/разметка.xlsx \
  --split artifacts/study_split.json \
  --out artifacts/canonical_manifest.json

python artifacts/validation/validate_canonical_manifest.py \
  artifacts/canonical_manifest.json
```

The builder fails closed if one source folder maps to multiple StudyInstanceUIDs,
if one StudyInstanceUID maps to multiple source folders, or if a study has no
split/criterion labels.

## Dataset audit at V6.7

The supplied archive produced 100 studies, 101 series and 499 DICOM instances.
The canonical manifest records 80 train and 20 validation studies. All 100 source
folder IDs differ from their DICOM `StudyInstanceUID`; this is why the explicit
mapping is required.
