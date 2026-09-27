from typing import Protocol
from uuid import UUID

import numpy as np

from app.schemas.prediction import ModelPrediction


class MLAdapter(Protocol):
    def predict(self, image: np.ndarray, *, image_id: UUID, metadata: dict) -> ModelPrediction: ...

    def predict_study(self, images: list[tuple[UUID, np.ndarray, dict]]) -> ModelPrediction: ...
