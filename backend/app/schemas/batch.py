from typing import Literal, TypeAlias

from pydantic import Field

from app.schemas.common import StrictModel


class StudyPrediction(StrictModel):
    image_uid: str | None = None
    anatomical_region: str = Field(min_length=1)
    quality_class: int | str
    violation_type: str = ""
    confidence: float | None = None
    quality_prob: float | None = None
    findings: str = ""


StudyResult: TypeAlias = list[StudyPrediction]


class BatchReportRow(StrictModel):
    path_to_study: str
    study_uid: str
    image_uid: str
    anatomical_region: str
    quality_class: int | str
    violation_type: str
    processing_status: Literal["Success", "Failure"]
    time_of_processing: float
    confidence: float | None = None
    quality_prob: float | None = None
    findings: str = ""
