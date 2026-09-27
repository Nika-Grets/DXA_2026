from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel, StudyStatus


class ImageSummary(StrictModel):
    image_id: UUID
    preview_url: str
    frames: int = Field(gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudySummary(StrictModel):
    study_id: UUID
    status: StudyStatus
    created_at: datetime
    images_count: int = Field(ge=0)
    images: list[ImageSummary]
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_prediction: bool = False
    has_report: bool = False


class UploadResponse(StudySummary):
    pass
