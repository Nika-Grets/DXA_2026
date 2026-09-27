import time, logging
from uuid import UUID

from pydantic import ValidationError

from app.core.exceptions import AppError
from app.ml.base import MLAdapter
from app.schemas.prediction import Defect, ModelPrediction, PredictionResponse
from app.services.dicom_service import DicomService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class PredictionService:
    def __init__(self, storage: StorageService, dicom: DicomService, adapter: MLAdapter) -> None:
        self.storage = storage
        self.dicom = dicom
        self.adapter = adapter

    def predict(self, study_id: UUID) -> PredictionResponse:
        path = self.storage.require_study(study_id)
        manifest = self.storage.read_json(path / "manifest.json")
        if manifest["status"] not in {"parsed", "predicted", "report_ready"}:
            raise AppError("INVALID_STUDY_STATE", "Study is not ready for prediction", 409)
        previous_status = manifest["status"]
        manifest["status"] = "predicting"
        self.storage.write_json_atomic(path / "manifest.json", manifest)
        try:
            started = time.perf_counter()
            metadata = self.storage.read_json(path / "metadata.json")["images"]
            images = []
            for item in manifest["images"]:
                image_id = UUID(item["image_id"])
                parsed = self.dicom.parse_bytes(self.storage.read_bytes(path / item["dicom_path"]))
                if parsed.frames > 1:
                    raise AppError(
                        "ML_INPUT_UNSUPPORTED",
                        "Multi-frame DICOM is unsupported by the current model",
                        422,
                    )
                images.append((image_id, parsed.pixels, metadata[item["image_id"]]))

            prediction = self.adapter.predict_study(images) if hasattr(self.adapter, "predict_study") else None
            if prediction is None:
                predictions = [
                    self.adapter.predict(image, image_id=image_id, metadata=image_metadata)
                    for image_id, image, image_metadata in images
                ]
                # A legacy adapter returns one ModelPrediction per image. Normalize it
                # into the study-level contract expected by the API.
                first = predictions[0] if predictions else None
                image_results = [r for p in predictions for r in p.results]
                defects = [d for p in predictions for d in p.defects]
                scores = [p.quality_score for p in predictions if p.quality_score is not None]
                from app.schemas.prediction import ModelPrediction
                prediction = ModelPrediction(
                    quality_status=("issue_detected" if any(p.quality_status == "issue_detected" for p in predictions) else "acceptable"),
                    quality_score=min(scores) if scores else None,
                    defects=defects,
                    model=first.model if first else None,
                    results=image_results,
                )

            response = PredictionResponse(
                study_id=study_id,
                quality_status=prediction.quality_status,
                quality_score=prediction.quality_score,
                defects=prediction.defects,
                model=prediction.model,
                results=prediction.results,
                processing_time_seconds=round(time.perf_counter() - started, 6),
            )
            self.storage.write_json_atomic(path / "prediction.json", response.model_dump(mode="json"))
            manifest["status"] = "predicted"
            manifest["error"] = None
            self.storage.write_json_atomic(path / "manifest.json", manifest)
            return response
        except AppError:
            manifest["status"] = previous_status
            self.storage.write_json_atomic(path / "manifest.json", manifest)
            raise
        except (ValueError, ValidationError) as exc:
            logger.exception(
                "ML inference validation/value error for study_id=%s",
                study_id,
            )
            manifest["status"] = previous_status
            self.storage.write_json_atomic(path / "manifest.json", manifest)
            raise AppError("ML_INFERENCE_FAILED", "ML inference failed", 502) from exc

        except Exception as exc:
            logger.exception(
                "ML inference unexpected error for study_id=%s",
                study_id,
            )
            manifest["status"] = previous_status
            self.storage.write_json_atomic(path / "manifest.json", manifest)
            raise AppError("ML_INFERENCE_FAILED", "ML inference failed", 502) from exc
