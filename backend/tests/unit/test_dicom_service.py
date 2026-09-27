import numpy as np

from app.services.dicom_service import DicomService
from tests.conftest import make_dicom_bytes


def test_whitelist_excludes_phi_and_applies_rescale():
    service = DicomService()
    parsed = service.parse_bytes(make_dicom_bytes(slope=2, intercept=-10))
    assert "PatientName" not in parsed.metadata
    assert "PatientID" not in parsed.metadata
    assert parsed.pixels[0, 0] == -10
    assert parsed.pixels[0, 1] == -8


def test_monochrome1_preview_matches_ml_orientation():
    service = DicomService()
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    parsed = service.parse_bytes(make_dicom_bytes(monochrome="MONOCHROME1", pixels=pixels))
    preview = service.preview_array(parsed, 0, 100)
    assert preview.dtype == np.uint8
    assert preview.tolist() == [[255, 170], [85, 0]]


def test_parse_normalizes_monochrome1_for_ml_inference():
    service = DicomService()
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    parsed = service.parse_bytes(make_dicom_bytes(monochrome="MONOCHROME1", pixels=pixels))
    assert parsed.pixels.tolist() == [[3.0, 2.0], [1.0, 0.0]]


def test_monochrome1_preview_is_not_double_inverted():
    service = DicomService()
    pixels = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    parsed = service.parse_bytes(make_dicom_bytes(monochrome="MONOCHROME1", pixels=pixels))
    preview = service.preview_array(parsed, 0, 100)
    assert preview.tolist() == [[255, 170], [85, 0]]
