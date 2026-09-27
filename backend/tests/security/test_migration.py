import json
from io import BytesIO
from uuid import uuid4

import pydicom

from app.core.encryption import MAGIC, EncryptionService
from app.services.dicom_service import DicomService
from app.services.migration_service import DataMigrationService
from app.services.storage import StorageService
from tests.conftest import make_dicom_bytes


def make_legacy_study(tmp_path, dicom_bytes):
    storage = StorageService(tmp_path / "studies", EncryptionService("", tmp_path / ".key"))
    study_id = uuid4()
    study_path = storage.create_study(study_id)
    image_id = uuid4()
    dicom_path = study_path / "original" / f"{image_id}.dcm"
    dicom_path.write_bytes(dicom_bytes)
    manifest = {
        "study_id": str(study_id),
        "status": "parsed",
        "created_at": "2026-01-01T00:00:00+00:00",
        "images": [
            {
                "image_id": str(image_id),
                "dicom_path": f"original/{image_id}.dcm",
                "preview_path": f"preview/{image_id}.png",
                "frames": 1,
            }
        ],
        "error": None,
    }
    (study_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (study_path / "metadata.json").write_text(
        json.dumps({"study_id": str(study_id), "images": {str(image_id): {"PatientName": "PHI"}}}),
        encoding="utf-8",
    )
    return storage, study_path, dicom_path


def test_startup_migration_encrypts_and_deidentifies_legacy_study(tmp_path):
    storage, study_path, dicom_path = make_legacy_study(tmp_path, make_dicom_bytes())
    encrypted, deidentified, quarantined = DataMigrationService(storage, DicomService()).run()

    assert encrypted == 3
    assert deidentified == 1
    assert quarantined == 0
    assert all(path.read_bytes().startswith(MAGIC) for path in study_path.rglob("*") if path.is_file())

    manifest = storage.read_json(study_path / "manifest.json")
    assert manifest["deidentified"] is True
    sanitized = pydicom.dcmread(BytesIO(storage.read_bytes(dicom_path)))
    assert "PatientName" not in sanitized
    assert not any(element.tag.is_private for element in sanitized.iterall())


def test_startup_migration_quarantines_unverified_legacy_pixels(tmp_path):
    storage, study_path, _ = make_legacy_study(
        tmp_path,
        make_dicom_bytes(burned_in_annotation=None),
    )
    _, deidentified, quarantined = DataMigrationService(storage, DicomService()).run()

    assert deidentified == 0
    assert quarantined == 1
    manifest = storage.read_json(study_path / "manifest.json")
    assert manifest["status"] == "failed"
    assert manifest["deidentified"] is False
    assert manifest["error"]["code"] == "LEGACY_DICOM_QUARANTINED"
    assert storage.read_json(study_path / "metadata.json")["images"] == {}
