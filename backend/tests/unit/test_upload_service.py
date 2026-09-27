from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.core.config import Settings
from app.core.encryption import EncryptionService
from app.core.exceptions import AppError
from app.services.dicom_service import DicomService
from app.services.storage import StorageService
from app.services.upload_service import UploadService
from tests.conftest import make_dicom_bytes


def build_zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return output.getvalue()


def service(tmp_path, **overrides) -> UploadService:
    settings = Settings(data_dir=tmp_path, **overrides)
    encryption = EncryptionService("", tmp_path / ".data-key")
    return UploadService(StorageService(tmp_path, encryption), DicomService(), settings)


def test_zip_with_multiple_dicoms_creates_one_study(tmp_path):
    archive = build_zip({"a/one.dcm": make_dicom_bytes(), "b/two.dcm": make_dicom_bytes()})
    manifest = service(tmp_path).ingest(archive, "study.zip")
    assert len(manifest["images"]) == 2


def test_zip_slip_is_rejected(tmp_path):
    archive = build_zip({"../escape.dcm": make_dicom_bytes()})
    with pytest.raises(AppError, match="Unsafe ZIP path"):
        service(tmp_path).ingest(archive, "study.zip")


def test_unpacked_limit_is_rejected(tmp_path):
    archive = build_zip({"one.dcm": make_dicom_bytes()})
    with pytest.raises(AppError) as caught:
        service(tmp_path, max_unpacked_bytes=10).ingest(archive, "study.zip")
    assert caught.value.status_code == 413
