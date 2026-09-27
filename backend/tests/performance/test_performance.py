import os
import time

from app.core.config import Settings
from app.core.encryption import EncryptionService
from app.core.security import create_access_token, decode_access_token
from app.services.dicom_service import DicomService
from tests.conftest import make_dicom_bytes


def test_aes_gcm_throughput(tmp_path):
    encryption = EncryptionService("", tmp_path / ".key")
    payload = os.urandom(8 * 1024 * 1024)
    started = time.perf_counter()
    encrypted = encryption.encrypt(payload, aad=b"benchmark")
    decrypted = encryption.decrypt(encrypted, aad=b"benchmark")
    elapsed = time.perf_counter() - started
    assert decrypted == payload
    assert elapsed < 5.0


def test_jwt_validation_throughput():
    settings = Settings()
    token, _, _ = create_access_token(
        user_id="user", session_id="session", token_version=0, settings=settings
    )
    started = time.perf_counter()
    for _ in range(1000):
        decode_access_token(token, settings)
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0


def test_dicom_deidentification_throughput():
    payload = make_dicom_bytes()
    service = DicomService()
    started = time.perf_counter()
    for _ in range(50):
        parsed = service.parse_bytes(payload)
        sanitized = service.deidentify(parsed, {})
        assert sanitized
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0
