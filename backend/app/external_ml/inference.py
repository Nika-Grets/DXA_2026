"""Batch inference entry point used by the API batch service."""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID, uuid5

import numpy as np

from app.ml.dexa_baseline import DexaBaselineAdapter
from app.services.dicom_service import DicomService

NAMESPACE = UUID("b1cbe9de-9b2d-4b68-8b85-8f0f1e7b5f4b")


def _uid_for_path(path: Path) -> UUID:
    return uuid5(NAMESPACE, str(path.resolve()))


def predict_study(dicom_paths: list[str]) -> list[dict]:
    adapter = DexaBaselineAdapter()
    dicom = DicomService(require_burned_in_annotation_no=False)
    unique: list[tuple[UUID, np.ndarray, dict]] = []
    cache: dict[str, dict] = {}
    path_to_digest: list[tuple[str, str, str]] = []

    for raw_path in dicom_paths:
        path = Path(raw_path)
        parsed = dicom.load(path)
        pixels = parsed.pixels[0] if parsed.frames > 1 else parsed.pixels
        if pixels.ndim != 2:
            raise ValueError(f"Unsupported DICOM pixel shape: {pixels.shape}")
        digest = hashlib.sha256(np.ascontiguousarray(pixels).tobytes()).hexdigest()
        image_uid = str(getattr(parsed.dataset, "SOPInstanceUID", "") or "")
        path_to_digest.append((raw_path, digest, image_uid))
        if digest not in cache:
            unique.append((_uid_for_path(path), pixels, parsed.metadata))
            cache[digest] = {}

    prediction = adapter.predict_study(unique)
    # Match unique predictions back to pixel digests through their image UID.
    by_uid = {item.image_uid: item for item in prediction.results if item.image_uid}
    unique_by_digest: dict[str, dict] = {}
    for _, digest, image_uid in path_to_digest:
        if digest in unique_by_digest:
            continue
        result = by_uid.get(image_uid)
        if result is None:
            raise RuntimeError("Inference result missing for unique image")
        unique_by_digest[digest] = result.model_dump(mode="json")

    outputs = []
    for _, digest, image_uid in path_to_digest:
        image_prediction = dict(unique_by_digest[digest])
        # BatchService consumes the legacy/stable StudyPrediction DTO.
        # Keep the richer ModelPrediction/ImagePrediction fields inside the ML
        # layer, but explicitly adapt the boundary here instead of passing
        # image_id/study_uid/quality_score/processing_status/anatomy_localization
        # into StudyPrediction (which uses extra=forbid).
        outputs.append({
            "image_uid": image_uid,
            "anatomical_region": image_prediction["anatomical_region"],
            "quality_class": image_prediction["quality_class"],
            "violation_type": ";".join(image_prediction.get("violation_type", [])),
            "confidence": image_prediction.get("confidence"),
            "quality_prob": image_prediction.get("quality_prob"),
            "findings": ";".join(image_prediction.get("findings", [])),
        })
    return outputs
