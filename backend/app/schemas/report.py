from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import StrictModel, StudyStatus


class ReportResponse(StrictModel):
    study_id: UUID
    status: Literal[StudyStatus.report_ready] = StudyStatus.report_ready
    report_url: str
    generated_at: datetime
