from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import jwt
import pydicom
from sqlalchemy import select

from app.core.encryption import MAGIC
from app.core.security import decode_access_token
from app.db.models import User
from tests.conftest import make_dicom_bytes


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_token_tamper_expiry_refresh_rotation_and_logout(client):
    with client.app.state.database.session_factory() as db:
        user = db.scalar(select(User).where(User.email == "doctor@example.com"))
        assert user.password_hash.startswith("$argon2")
        assert "correct-horse" not in user.password_hash

    access = client.auth_tokens["access_token"]
    tampered = access[:-1] + ("A" if access[-1] != "A" else "B")
    assert client.get("/api/v1/auth/me", headers=auth_header(tampered)).status_code == 401

    claims = decode_access_token(access, client.app.state.settings)
    now = datetime.now(UTC)
    claims.update(
        {
            "iat": now - timedelta(seconds=2),
            "nbf": now - timedelta(seconds=2),
            "exp": now - timedelta(seconds=1),
        }
    )
    expired = jwt.encode(
        claims, client.app.state.settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )
    assert client.get("/api/v1/auth/me", headers=auth_header(expired)).status_code == 401

    first_refresh = client.auth_tokens["refresh_token"]
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh}).status_code == 401
    new_access = rotated.json()["access_token"]
    assert client.post("/api/v1/auth/logout", headers=auth_header(new_access)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth_header(new_access)).status_code == 401


def test_study_owner_isolation_encryption_and_deidentification(client, dicom_bytes):
    source = pydicom.dcmread(BytesIO(dicom_bytes))
    upload = client.post("/api/v1/upload", files={"file": ("scan.dcm", dicom_bytes)})
    assert upload.status_code == 201, upload.text
    study_id = upload.json()["study_id"]
    study_path = client.app.state.storage.study_dir(UUID(study_id))
    manifest_file = study_path / "manifest.json"
    assert manifest_file.read_bytes().startswith(MAGIC)
    assert b"Patient" not in manifest_file.read_bytes()

    manifest = client.app.state.storage.read_json(manifest_file)
    original_path = study_path / manifest["images"][0]["dicom_path"]
    sanitized = pydicom.dcmread(BytesIO(client.app.state.storage.read_bytes(original_path)))
    assert "PatientName" not in sanitized
    assert "PatientID" not in sanitized
    assert "PatientBirthDate" not in sanitized
    assert "InstitutionName" not in sanitized
    assert "AccessionNumber" not in sanitized
    assert "ReferringPhysicianName" not in sanitized
    assert not any(element.tag.is_private for element in sanitized.iterall())
    assert sanitized.PatientIdentityRemoved == "YES"
    assert sanitized.BurnedInAnnotation == "NO"
    assert sanitized.StudyInstanceUID != source.StudyInstanceUID
    assert sanitized.SeriesInstanceUID != source.SeriesInstanceUID
    assert sanitized.SOPInstanceUID != source.SOPInstanceUID
    assert sanitized.pixel_array.shape == source.pixel_array.shape

    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "other@example.com",
                "full_name": "Other Doctor",
                "password": "another-correct-long-password",
            },
        ).status_code
        == 201
    )
    other = client.post(
        "/api/v1/auth/login",
        json={
            "email": "other@example.com",
            "password": "another-correct-long-password",
        },
    ).json()
    assert (
        client.get(f"/api/v1/studies/{study_id}", headers=auth_header(other["access_token"])).status_code
        == 404
    )

    image_id = upload.json()["images"][0]["image_id"]
    preview_path = study_path / "preview" / f"{image_id}.png"
    damaged = bytearray(preview_path.read_bytes())
    damaged[-1] ^= 1
    preview_path.write_bytes(damaged)
    response = client.get(f"/api/v1/studies/{study_id}/preview/{image_id}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "STORAGE_INTEGRITY_ERROR"


def test_protected_routes_reject_missing_token(client):
    saved = client.headers.pop("Authorization")
    try:
        assert client.get("/api/v1/studies").status_code == 401
    finally:
        client.headers["Authorization"] = saved


def test_dicom_with_burned_in_or_unknown_pixel_annotation_is_rejected(client):
    burned_in = client.post(
        "/api/v1/upload",
        files={"file": ("burned-in.dcm", make_dicom_bytes(burned_in_annotation="YES"))},
    )
    assert burned_in.status_code == 422
    assert burned_in.json()["error"]["code"] == "DICOM_BURNED_IN_ANNOTATION_UNVERIFIED"

    unknown = client.post(
        "/api/v1/upload",
        files={"file": ("unknown.dcm", make_dicom_bytes(burned_in_annotation=None))},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "DICOM_BURNED_IN_ANNOTATION_UNVERIFIED"
