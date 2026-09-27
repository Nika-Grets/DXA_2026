"""Build the canonical study/image manifest for the DXA dataset.

The label workbook uses the source folder identifier, while DICOM contains the
actual StudyInstanceUID. Both identifiers are retained explicitly; ML grouping
and splitting use the DICOM StudyInstanceUID after this mapping is established.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import openpyxl
import pydicom

LABEL_COLUMNS = {
    "spine_position": 3,
    "spine_axis": 4,
    "spine_artifact": 5,
    "right_posrot": 6,
    "right_roi": 7,
    "left_posrot": 8,
    "left_roi": 9,
}


def _label(value):
    if value in (0, 1):
        return int(value)
    if isinstance(value, float) and value in (0.0, 1.0):
        return int(value)
    return None


def _read_labels(path: Path) -> dict[str, dict[str, int | None]]:
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True).active
    out = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        folder_id = row[1]
        if not folder_id:
            continue
        out[str(folder_id)] = {
            name: _label(row[idx - 1]) for name, idx in LABEL_COLUMNS.items()
        }
    return out


def _sha256_pixels(ds) -> str:
    return hashlib.sha256(bytes(ds.PixelData)).hexdigest()


def build(root: Path, labels_path: Path, split_path: Path) -> dict:
    labels = _read_labels(labels_path)
    split_doc = json.loads(split_path.read_text(encoding="utf-8"))
    split_by_folder = split_doc.get("split", split_doc)

    by_study: dict[str, dict] = {}
    folder_seen: dict[str, str] = {}
    files = sorted(root.rglob("*.dcm"))
    for path in files:
        # The first directory below root is the source folder ID. This is kept
        # even when it differs from the DICOM StudyInstanceUID.
        rel = path.relative_to(root)
        source_folder_id = rel.parts[0]
        ds = pydicom.dcmread(path, stop_before_pixels=False, force=False)
        study_uid = str(ds.StudyInstanceUID)
        series_uid = str(ds.SeriesInstanceUID)
        sop_uid = str(ds.SOPInstanceUID)
        previous = folder_seen.setdefault(source_folder_id, study_uid)
        if previous != study_uid:
            raise ValueError(
                f"Source folder {source_folder_id} contains multiple StudyInstanceUID values: "
                f"{previous} and {study_uid}"
            )
        record = by_study.setdefault(study_uid, {
            "source_folder_id": source_folder_id,
            "study_uid": study_uid,
            "split": split_by_folder.get(source_folder_id),
            "labels": labels.get(source_folder_id),
            "series": {},
        })
        if record["source_folder_id"] != source_folder_id:
            raise ValueError(f"StudyInstanceUID {study_uid} maps to multiple source folders")
        series = record["series"].setdefault(series_uid, {
            "series_uid": series_uid,
            "images": [],
        })
        series["images"].append({
            "sop_uid": sop_uid,
            "relative_path": str(rel).replace("\\", "/"),
            "rows": int(ds.Rows),
            "columns": int(ds.Columns),
            "photometric_interpretation": str(getattr(ds, "PhotometricInterpretation", "")),
            "pixel_spacing": [float(v) for v in ds.PixelSpacing] if hasattr(ds, "PixelSpacing") else None,
            "pixel_sha256": _sha256_pixels(ds),
        })

    studies = []
    for study_uid in sorted(by_study):
        record = by_study[study_uid]
        record["series"] = [record["series"][uid] for uid in sorted(record["series"])]
        record["n_series"] = len(record["series"])
        record["n_images"] = sum(len(s["images"]) for s in record["series"])
        record["n_unique_pixel_arrays"] = len({
            image["pixel_sha256"]
            for series in record["series"]
            for image in series["images"]
        })
        studies.append(record)

    missing_split = [x["source_folder_id"] for x in studies if x["split"] not in {"train", "validation"}]
    missing_labels = [x["source_folder_id"] for x in studies if x["labels"] is None]
    if missing_split:
        raise ValueError(f"No split for {len(missing_split)} source folders")
    if missing_labels:
        raise ValueError(f"No labels for {len(missing_labels)} source folders")

    return {
        "schema_version": "canonical_dxa_manifest_v1",
        "group_key": "study_uid",
        "source_label_key": "source_folder_id",
        "notes": [
            "source_folder_id is the identifier used by the label workbook",
            "study_uid is the DICOM StudyInstanceUID and is the canonical ML grouping key",
            "series_uid and sop_uid are retained for traceability",
            "pixel_sha256 is used for duplicate hygiene; it is not a study grouping key",
        ],
        "studies": studies,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--xlsx", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = build(args.root, args.xlsx, args.split)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest['studies'])} studies to {args.out}")


if __name__ == "__main__":
    main()
