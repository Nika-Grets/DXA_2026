import hashlib
import hmac
import json
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import EncryptionService
from app.db.models import AuditEvent
from app.schemas.audit import AuditEventResponse, AuditIntegrityResponse

AUDIT_PURPOSE = b"audit-trail"


def _digest(value: str | None, key: bytes) -> str | None:
    if not value:
        return None
    return hmac.new(key, value.encode("utf-8", errors="replace"), hashlib.sha256).hexdigest()


def _canonical_payload(values: dict) -> bytes:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _utc_iso(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def _action_name(method: str, route: str) -> str:
    suffix = route.removeprefix("/api/v1")
    mapping = {
        ("POST", "/auth/register"): "auth.register",
        ("POST", "/auth/login"): "auth.login",
        ("POST", "/auth/refresh"): "auth.refresh",
        ("POST", "/batch"): "study.batch",
        ("GET", "/auth/me"): "auth.profile.read",
        ("POST", "/auth/logout"): "auth.logout",
        ("POST", "/upload"): "study.upload",
        ("GET", "/studies"): "study.list",
        ("GET", "/studies/{study_id}"): "study.read",
        ("DELETE", "/studies/{study_id}"): "study.delete",
        ("GET", "/studies/{study_id}/preview/{image_id}"): "study.preview.read",
        ("POST", "/studies/{study_id}/predict"): "study.predict",
        ("GET", "/studies/{study_id}/prediction"): "study.prediction.read",
        ("GET", "/studies/{study_id}/status"): "study.status.read",
        ("POST", "/studies/{study_id}/report"): "study.report.generate",
        ("GET", "/studies/{study_id}/report"): "study.report.download",
        ("GET", "/audit-events"): "audit.list",
        ("GET", "/audit-events/integrity"): "audit.integrity.verify",
    }
    return mapping.get((method, suffix), f"http.{method.lower()}:{suffix}")


class AuditService:
    def __init__(self, encryption: EncryptionService) -> None:
        self.encryption = encryption
        self._write_lock = Lock()

    def record_request(
        self,
        db: Session,
        *,
        actor_user_id: str,
        request: Request,
        status_code: int,
    ) -> AuditEvent:
        with self._write_lock:
            return self._record_request(
                db,
                actor_user_id=actor_user_id,
                request=request,
                status_code=status_code,
            )

    def _record_request(
        self,
        db: Session,
        *,
        actor_user_id: str,
        request: Request,
        status_code: int,
    ) -> AuditEvent:
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", request.url.path)
        method = request.method.upper()
        resource_id = request.path_params.get("study_id")
        resource_type = "study" if resource_id else None
        request_id = getattr(request.state, "request_id", str(uuid4()))
        key_id, key = self.encryption.active_derived_key(AUDIT_PURPOSE)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        outcome = "success" if status_code < 400 else ("denied" if status_code < 500 else "failure")
        details = {"method": method, "route": route, "status_code": status_code}
        previous = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
        previous_hash = previous.event_hash if previous else "0" * 64
        occurred_at = datetime.now(UTC)
        canonical_values = {
            "actor_user_id": actor_user_id,
            "occurred_at": _utc_iso(occurred_at),
            "action": _action_name(method, route),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "request_id": request_id,
            "ip_hash": _digest(ip_address, key),
            "user_agent_hash": _digest(user_agent, key),
            "details_json": json.dumps(details, sort_keys=True, separators=(",", ":")),
            "key_id": key_id,
            "previous_hash": previous_hash,
        }
        event_hash = hmac.new(
            key,
            previous_hash.encode() + _canonical_payload(canonical_values),
            hashlib.sha256,
        ).hexdigest()
        event = AuditEvent(
            **{key: value for key, value in canonical_values.items() if key != "occurred_at"},
            occurred_at=occurred_at,
            event_hash=event_hash,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def list_for_user(self, db: Session, user_id: str, limit: int = 200) -> list[AuditEventResponse]:
        events = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.actor_user_id == user_id)
            .order_by(AuditEvent.id.desc())
            .limit(limit)
        )
        return [
            AuditEventResponse(
                id=event.id,
                occurred_at=event.occurred_at,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                outcome=event.outcome,
                request_id=event.request_id,
                details=json.loads(event.details_json),
            )
            for event in events
        ]

    def verify_integrity(self, db: Session) -> AuditIntegrityResponse:
        previous_hash = "0" * 64
        checked = 0
        for event in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
            values = {
                "actor_user_id": event.actor_user_id,
                "occurred_at": _utc_iso(event.occurred_at),
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "outcome": event.outcome,
                "request_id": event.request_id,
                "ip_hash": event.ip_hash,
                "user_agent_hash": event.user_agent_hash,
                "details_json": event.details_json,
                "key_id": event.key_id,
                "previous_hash": event.previous_hash,
            }
            try:
                key = self.encryption.derive_key(event.key_id, AUDIT_PURPOSE)
            except Exception:
                return AuditIntegrityResponse(valid=False, events_checked=checked)
            expected = hmac.new(
                key,
                previous_hash.encode() + _canonical_payload(values),
                hashlib.sha256,
            ).hexdigest()
            if event.previous_hash != previous_hash or not hmac.compare_digest(event.event_hash, expected):
                return AuditIntegrityResponse(valid=False, events_checked=checked)
            previous_hash = event.event_hash
            checked += 1
        return AuditIntegrityResponse(valid=True, events_checked=checked)
