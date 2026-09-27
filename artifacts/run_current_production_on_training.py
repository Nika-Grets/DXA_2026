"""Generate a fresh study-aware production CSV from the labelled training DICOM.

This deliberately uses the same project routing/criterion functions as production,
but a tiny local DICOM reader because the current shell does not have pydicom.
The organiser files are Implicit VR Little Endian, 8-bit MONOCHROME2 single-frame
images; the parser validates those assumptions and stops on PixelData.
"""
from __future__ import annotations

import csv
import hashlib
import struct
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / ".training_dicom"
OLD_CSV = ROOT / "data" / "training_batch.csv"
OUT = ROOT / "data" / "training_batch_current.csv"

sys.path.insert(0, str(ROOT / "backend"))
from app.ml.dexa_baseline import classify_study, evaluate_quality, _quality_probabilities
from app.terminology import term_name


def _text(raw: bytes) -> str:
    return raw.rstrip(b" \x00").decode("utf-8", "replace").strip()


def _read_dicom(path: Path) -> tuple[dict[str, object], np.ndarray]:
    b = path.read_bytes()
    if len(b) < 132 or b[128:132] != b"DICM":
        raise ValueError(f"not a DICOM Part-10 file: {path}")
    pos = 132
    # File meta: Explicit VR Little Endian, group 0002.
    while pos + 8 <= len(b):
        g, e = struct.unpack_from("<HH", b, pos)
        if g != 0x0002:
            break
        vr = b[pos + 4:pos + 6]
        if vr in {b"OB", b"OD", b"OF", b"OL", b"OV", b"OW", b"SQ", b"UC", b"UN", b"UR"}:
            length = struct.unpack_from("<I", b, pos + 8)[0]
            header = 12
        else:
            length = struct.unpack_from("<H", b, pos + 6)[0]
            header = 8
        pos += header + length

    values: dict[str, object] = {}
    pixels = None
    while pos + 8 <= len(b):
        g, e = struct.unpack_from("<HH", b, pos)
        length = struct.unpack_from("<I", b, pos + 4)[0]
        value_start = pos + 8
        value_end = value_start + length
        if value_end > len(b):
            raise ValueError(f"invalid element length at {pos} in {path}")
        tag = (g, e)
        if tag == (0x0008, 0x0070):
            values["Manufacturer"] = _text(b[value_start:value_end])
        elif tag == (0x0008, 0x1090):
            values["ManufacturerModelName"] = _text(b[value_start:value_end])
        elif tag == (0x0020, 0x000D):
            values["StudyInstanceUID"] = _text(b[value_start:value_end])
        elif tag == (0x0008, 0x0018):
            values["SOPInstanceUID"] = _text(b[value_start:value_end])
        elif tag == (0x0028, 0x0010):
            values["Rows"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0011):
            values["Columns"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0100):
            values["BitsAllocated"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0101):
            values["BitsStored"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0102):
            values["HighBit"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0103):
            values["PixelRepresentation"] = struct.unpack_from("<H", b, value_start)[0]
        elif tag == (0x0028, 0x0004):
            values["PhotometricInterpretation"] = _text(b[value_start:value_end])
        elif tag == (0x0028, 0x1053):
            try:
                values["RescaleSlope"] = float(_text(b[value_start:value_end]))
            except ValueError:
                pass
        elif tag == (0x0028, 0x1052):
            try:
                values["RescaleIntercept"] = float(_text(b[value_start:value_end]))
            except ValueError:
                pass
        elif tag == (0x7FE0, 0x0010):
            rows = int(values["Rows"]); cols = int(values["Columns"])
            bits = int(values.get("BitsAllocated", 8))
            if bits != 8:
                raise ValueError(f"expected 8-bit pixels, got {bits}: {path}")
            expected = rows * cols
            raw = b[value_start:value_end]
            if len(raw) < expected:
                raise ValueError(f"short PixelData {len(raw)} < {expected}: {path}")
            pixels = np.frombuffer(raw[:expected], dtype=np.uint8).reshape(rows, cols).astype(np.float32)
            if values.get("PhotometricInterpretation") == "MONOCHROME1":
                pixels = 255.0 - pixels
            break
        pos = value_end

    if pixels is None:
        raise ValueError(f"PixelData not found: {path}")
    required = ("StudyInstanceUID", "SOPInstanceUID", "Rows", "Columns")
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ValueError(f"missing {missing}: {path}")
    return values, pixels


def main() -> None:
    old_rows = list(csv.DictReader(OLD_CSV.open(encoding="utf-8-sig", newline="")))
    path_by_image = {r["image_uid"]: r["path_to_study"] for r in old_rows}

    files = sorted(TRAINING.rglob("*.dcm"))
    if len(files) != 499:
        raise RuntimeError(f"expected 499 DICOM files, found {len(files)}")

    studies: dict[str, list[tuple[str, np.ndarray, dict[str, object]]]] = defaultdict(list)
    for path in files:
        meta, pixels = _read_dicom(path)
        study = str(meta["StudyInstanceUID"])
        image = str(meta["SOPInstanceUID"])
        studies[study].append((image, pixels, meta))

    out = []
    route_counts = defaultdict(int)
    for study_uid, images in sorted(studies.items()):
        unique = []
        groups = []
        seen = {}
        for image_uid, pixels, meta in images:
            digest = hashlib.md5(np.ascontiguousarray(pixels).tobytes()).hexdigest()
            idx = seen.get(digest)
            if idx is None:
                idx = len(unique)
                seen[digest] = idx
                unique.append((image_uid, pixels, meta))
            groups.append(idx)

        routed = classify_study([item[1] for item in unique])
        route_by_index = {r.image_index: r for r in routed}
        for original_idx, (image_uid, pixels, meta) in enumerate(images):
            uidx = groups[original_idx]
            route = route_by_index[uidx]
            region = route.region
            if region == "unknown":
                raise RuntimeError(f"unknown route: {study_uid}/{image_uid}")
            status, confidence, violations, findings = evaluate_quality(pixels, region, meta)
            deterministic_risk = float(np.clip(confidence if status == "issue_detected" else 0.0, 0.0, 1.0))
            model_risks = _quality_probabilities(pixels, region)
            quality_prob = float(np.clip(max([deterministic_risk, *model_risks]), 0.0, 1.0))
            route_counts[region] += 1
            out.append({
                "path_to_study": path_by_image.get(image_uid, ""),
                "study_uid": study_uid,
                "image_uid": image_uid,
                "anatomical_region": {"spine": "Поясничный отдел позвоночника", "femur_right": "Проксимальный отдел бедра", "femur_left": "Проксимальный отдел бедра"}[region],
                "quality_class": int(status == "issue_detected"),
                "violation_type": ";".join(term_name(code) for code in violations if code in {"SPINE_POSITION","SPINE_AXIS","SPINE_ARTIFACT","HIP_POSITION_ROTATION","HIP_ROI"}),
                "processing_status": "success",
                "time_of_processing": "",
                "confidence": confidence,
                "quality_prob": quality_prob,
                "findings": ";".join(term_name(code) for code in findings),
            })

    fieldnames = list(out[0].keys())
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(out)
    print(f"wrote {OUT} rows={len(out)} studies={len(studies)}")
    print("routes", dict(route_counts))
    from collections import Counter
    print("violations", Counter(r["violation_type"] for r in out))

if __name__ == "__main__":
    main()
