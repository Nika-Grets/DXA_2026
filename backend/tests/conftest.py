from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from app.core.config import Settings
from app.main import create_app


def make_dicom_bytes(
    *,
    monochrome: str = "MONOCHROME2",
    patient_name: str = "Private^Patient",
    slope: float = 1.0,
    intercept: float = 0.0,
    pixels: np.ndarray | None = None,
    burned_in_annotation: str | None = "NO",
) -> bytes:
    values = pixels if pixels is not None else np.arange(64, dtype=np.uint16).reshape(8, 8)
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    dataset = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.PatientName = patient_name
    dataset.PatientID = "secret-id"
    dataset.Modality = "DX"
    dataset.Rows, dataset.Columns = values.shape[-2:]
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = monochrome
    dataset.PatientBirthDate = "19700101"
    dataset.InstitutionName = "Private Hospital"
    dataset.AccessionNumber = "private-access"
    dataset.ReferringPhysicianName = "Private^Doctor"
    dataset.add_new((0x0011, 0x1010), "LO", "private-vendor-patient-data")
    if burned_in_annotation is not None:
        dataset.BurnedInAnnotation = burned_in_annotation
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.RescaleSlope = slope
    dataset.RescaleIntercept = intercept
    dataset.PixelData = values.tobytes()
    output = BytesIO()
    dataset.save_as(output, enforce_file_format=True)
    return output.getvalue()


@pytest.fixture
def dicom_bytes() -> bytes:
    return make_dicom_bytes()


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "studies",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_encryption_key_file=tmp_path / ".data-key",
        cors_origins=["http://frontend.test"],
        allowed_hosts=["localhost", "127.0.0.1", "testserver"],
        ml_study_module="tests.fake_study_ml",
        batch_cooldown_seconds=0,
        account_rate_limit=1000,
        upload_cooldown_seconds=0,
        delete_cooldown_seconds=0,
        predict_cooldown_seconds=0,
        report_cooldown_seconds=0,
    )
    app = create_app(settings)
    app.state.report_service.renderer = lambda _html, _base_url: b"%PDF-1.4\n%%EOF\n"
    with TestClient(app) as test_client:
        registered = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": "doctor@example.com",
                "full_name": "Test Doctor",
                "password": "correct-horse-battery-staple",
            },
        )
        assert registered.status_code == 201, registered.text
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "correct-horse-battery-staple"},
        )
        assert login.status_code == 200, login.text
        test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        test_client.auth_tokens = login.json()
        yield test_client
