from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel, StudyStatus

UnitFloat = Annotated[float, Field(ge=0, le=1)]


class BBoxROI(StrictModel):
    type: Literal["bbox"] = "bbox"
    x: UnitFloat
    y: UnitFloat
    width: UnitFloat
    height: UnitFloat

    @model_validator(mode="after")
    def contained(self) -> "BBoxROI":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("bbox must fit inside normalized image bounds")
        return self


class PolygonROI(StrictModel):
    type: Literal["polygon"] = "polygon"
    points: list[tuple[UnitFloat, UnitFloat]] = Field(min_length=3)


class MaskROI(StrictModel):
    type: Literal["mask"] = "mask"
    mask_url: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


ROI = Annotated[BBoxROI | PolygonROI | MaskROI, Field(discriminator="type")]



class AnatomyLocalization(StrictModel):
    """Candidate anatomy geometry for visualization; not a segmentation mask."""
    type: Literal["candidate_anatomy"] = "candidate_anatomy"
    bbox: BBoxROI
    shaft_bbox: BBoxROI | None = None
    centerline: list[tuple[UnitFloat, UnitFloat]] = Field(default_factory=list)
    confidence: UnitFloat
    side: Literal["left", "right"] | None = None
    physical_margin_mm: tuple[float, float, float, float] | None = None
    axis_degrees_physical: float | None = None


class Defect(StrictModel):
    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    confidence: UnitFloat
    image_id: UUID
    roi: ROI


class ModelInfo(StrictModel):
    name: str
    version: str


class ImagePrediction(StrictModel):
    image_id: UUID
    study_uid: str | None = None
    image_uid: str | None = None
    anatomical_region: Literal["Поясничный отдел позвоночника", "Проксимальный отдел бедра"]
    quality_class: Literal[0, 1]
    quality_score: UnitFloat | None = None
    confidence: UnitFloat | None = None
    quality_prob: UnitFloat | None = None
    violation_type: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    processing_status: Literal["success", "error"] = "success"
    anatomy_localization: AnatomyLocalization | None = None


class ModelPrediction(StrictModel):
    quality_status: Literal["acceptable", "issue_detected"]
    quality_score: UnitFloat | None = None
    defects: list[Defect] = Field(default_factory=list)
    model: ModelInfo
    results: list[ImagePrediction] = Field(default_factory=list)


class PredictionResponse(ModelPrediction):
    study_id: UUID
    processing_time_seconds: float | None = Field(default=None, ge=0)
    status: Literal[StudyStatus.predicted] = StudyStatus.predicted
