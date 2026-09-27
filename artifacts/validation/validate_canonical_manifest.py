"""Validate canonical manifest invariants without touching DICOM pixels."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    studies = doc["studies"]
    assert doc["group_key"] == "study_uid"
    assert len(studies) == len({x["study_uid"] for x in studies})
    assert len(studies) == len({x["source_folder_id"] for x in studies})
    split_counts = Counter(x["split"] for x in studies)
    for study in studies:
        assert study["source_folder_id"]
        assert study["study_uid"]
        assert study["split"] in {"train", "validation"}
        assert study["labels"] is not None
        assert study["n_series"] == len(study["series"])
        for series in study["series"]:
            assert series["series_uid"]
            for image in series["images"]:
                assert image["sop_uid"]
                assert image["pixel_sha256"]
    print(f"OK: {len(studies)} studies; split={dict(split_counts)}")


if __name__ == "__main__":
    main()
