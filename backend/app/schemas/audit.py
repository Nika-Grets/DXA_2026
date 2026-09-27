from datetime import datetime

from app.schemas.common import StrictModel


class AuditEventResponse(StrictModel):
    id: int
    occurred_at: datetime
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    request_id: str
    details: dict


class AuditIntegrityResponse(StrictModel):
    valid: bool
    events_checked: int
