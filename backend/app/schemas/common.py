from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudyStatus(StrEnum):
    uploaded = "uploaded"
    parsed = "parsed"
    predicting = "predicting"
    predicted = "predicted"
    report_ready = "report_ready"
    failed = "failed"


class ApiErrorDetails(StrictModel):
    code: str
    message: str
    details: Any = None


class ApiError(StrictModel):
    error: ApiErrorDetails
