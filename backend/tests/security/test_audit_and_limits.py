from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import AuditEvent
from app.services.rate_limit_service import AccountRateLimiter


def test_account_rate_limit_and_retry_after():
    limiter = AccountRateLimiter(limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("doctor-1")

    with pytest.raises(AppError) as caught:
        limiter.check("doctor-1")

    assert caught.value.status_code == 429
    assert caught.value.code == "RATE_LIMIT_EXCEEDED"
    assert caught.value.headers["Retry-After"] == "60"


def test_action_cooldown_is_scoped_by_account_and_action():
    limiter = AccountRateLimiter(limit=100, window_seconds=1)
    limiter.check_cooldown("doctor-1", "study.predict:one", 10)
    limiter.check_cooldown("doctor-2", "study.predict:one", 10)
    limiter.check_cooldown("doctor-1", "study.predict:two", 10)

    with pytest.raises(AppError) as caught:
        limiter.check_cooldown("doctor-1", "study.predict:one", 10)

    assert caught.value.status_code == 429
    assert caught.value.code == "COOLDOWN_ACTIVE"
    assert caught.value.headers["Retry-After"] == "10"


def test_predict_route_cooldown(client, dicom_bytes):
    uploaded = client.post("/api/v1/upload", files={"file": ("image.dcm", dicom_bytes)})
    study_id = UUID(uploaded.json()["study_id"])
    client.app.state.settings.predict_cooldown_seconds = 10

    assert client.post(f"/api/v1/studies/{study_id}/predict").status_code == 200
    repeated = client.post(f"/api/v1/studies/{study_id}/predict")

    assert repeated.status_code == 429
    assert repeated.json()["error"]["code"] == "COOLDOWN_ACTIVE"
    assert repeated.headers["Retry-After"] == "10"


def test_audit_trail_records_requests_and_detects_tampering(client):
    profile = client.get("/api/v1/auth/me")
    assert profile.status_code == 200
    UUID(profile.headers["X-Request-ID"])

    listed = client.get("/api/v1/audit-events")
    assert listed.status_code == 200
    actions = {event["action"] for event in listed.json()}
    assert {"auth.register", "auth.login", "auth.profile.read"} <= actions

    integrity = client.get("/api/v1/audit-events/integrity")
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True
    assert integrity.json()["events_checked"] >= 4

    with client.app.state.database.session_factory() as db:
        event = db.scalar(select(AuditEvent).order_by(AuditEvent.id).limit(1))
        assert event is not None
        assert event.ip_hash
        assert event.user_agent_hash
        event.details_json = '{"tampered":true}'
        db.commit()

    tampered = client.get("/api/v1/audit-events/integrity")
    assert tampered.status_code == 200
    assert tampered.json()["valid"] is False
