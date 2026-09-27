import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import (
    get_audit_service,
    get_auth_service,
    get_batch_service,
    get_current_auth,
    get_current_user,
    get_db,
    get_prediction_service,
    get_report_service,
    get_storage,
    get_upload_service,
)
from app.core.exceptions import AppError
from app.db.models import AuthSession, Study, User
from app.schemas.audit import AuditEventResponse, AuditIntegrityResponse
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.common import ApiError
from app.schemas.prediction import PredictionResponse
from app.schemas.report import ReportResponse
from app.schemas.study import ImageSummary, StudySummary, UploadResponse
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.batch_service import BatchService
from app.services.prediction_service import PredictionService
from app.services.report_service import ReportService
from app.services.storage import StorageService
from app.services.upload_service import UploadService

router = APIRouter()
error_responses = {
    401: {"model": ApiError},
    403: {"model": ApiError},
    404: {"model": ApiError},
    409: {"model": ApiError},
    413: {"model": ApiError},
    415: {"model": ApiError},
    422: {"model": ApiError},
    429: {"model": ApiError},
}


def _common_metadata(items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    values = list(items.values())
    keys = set.intersection(*(set(item) for item in values))
    return {key: values[0][key] for key in keys if all(item[key] == values[0][key] for item in values)}


def _summary(storage: StorageService, study_id: UUID) -> StudySummary:
    path = storage.require_study(study_id)
    manifest = storage.read_json(path / "manifest.json")
    metadata = storage.read_json(path / "metadata.json")["images"]
    images = [
        ImageSummary(
            image_id=UUID(item["image_id"]),
            preview_url=f"/api/v1/studies/{study_id}/preview/{item['image_id']}",
            frames=item["frames"],
            metadata=metadata.get(item["image_id"], {}),
        )
        for item in manifest["images"]
    ]
    return StudySummary(
        study_id=study_id,
        status=manifest["status"],
        created_at=datetime.fromisoformat(manifest["created_at"]),
        images_count=len(images),
        images=images,
        metadata=_common_metadata(metadata),
        has_prediction=(path / "prediction.json").is_file(),
        has_report=(path / "report" / "report.pdf").is_file(),
    )


def _owned_study(db: Session, study_id: UUID, user: User) -> Study:
    study = db.get(Study, str(study_id))
    if not study or study.owner_id != user.id:
        raise AppError("STUDY_NOT_FOUND", "Study was not found", 404)
    return study


def _usable_manifest(storage: StorageService, study_id: UUID) -> tuple[Any, dict[str, Any]]:
    path = storage.require_study(study_id)
    manifest = storage.read_json(path / "manifest.json")
    error = manifest.get("error") or {}
    if error.get("code") == "LEGACY_DICOM_QUARANTINED":
        raise AppError(
            "STUDY_QUARANTINED",
            "Study is blocked because mandatory de-identification failed",
            409,
        )
    return path, manifest


@router.post("/auth/register", status_code=201, response_model=UserResponse, responses=error_responses)
def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    result = service.register(db, payload)
    request.state.audit_actor_id = str(result.id)
    return result


@router.post("/auth/login", response_model=TokenResponse, responses=error_responses)
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    result = service.login(db, payload)
    user, _ = service.authenticate(db, result.access_token)
    request.state.audit_actor_id = user.id
    return result


@router.post("/auth/refresh", response_model=TokenResponse, responses=error_responses)
def refresh(
    request: Request,
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    result = service.refresh(db, payload.refresh_token)
    user, _ = service.authenticate(db, result.access_token)
    request.state.audit_actor_id = user.id
    return result


@router.post("/auth/logout", status_code=204, responses=error_responses)
def logout(
    auth: Annotated[tuple[User, AuthSession], Depends(get_current_auth)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.logout(db, auth[1])
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserResponse, responses=error_responses)
def me(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    return service.user_response(user)


@router.get("/audit-events/integrity", response_model=AuditIntegrityResponse, responses=error_responses)
def verify_audit_integrity(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuditService, Depends(get_audit_service)],
) -> AuditIntegrityResponse:
    del user
    return service.verify_integrity(db)


@router.get("/audit-events", response_model=list[AuditEventResponse], responses=error_responses)
def list_audit_events(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuditService, Depends(get_audit_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[AuditEventResponse]:
    return service.list_for_user(db, user.id, limit)


@router.post(
    "/batch",
    responses=error_responses,
)
async def process_batch(
    file: Annotated[UploadFile, File(description="ZIP dataset containing nested DICOM studies")],
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[BatchService, Depends(get_batch_service)],
    include_visualizations: Annotated[bool, Query()] = False,
) -> Response:
    del user
    payload = bytearray()
    while chunk := await file.read(1024 * 1024):
        payload.extend(chunk)
        if len(payload) > service.max_archive_bytes:
            raise AppError(
                "UPLOAD_TOO_LARGE",
                "Batch archive size limit exceeded",
                413,
            )
    artifact = await run_in_threadpool(
        service.process_archive,
        bytes(payload),
        file.filename,
        include_visualizations=include_visualizations,
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Batch-Rows": str(len(artifact.rows)),
        },
    )


@router.post("/upload", status_code=201, response_model=UploadResponse, responses=error_responses)
async def upload(
    file: Annotated[UploadFile, File(description="One DICOM file or ZIP archive")],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[UploadService, Depends(get_upload_service)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> StudySummary:
    payload = bytearray()
    limit: int | None = None
    while chunk := await file.read(1024 * 1024):
        if limit is None:
            is_zip = chunk.startswith(b"PK\x03\x04") or (file.filename or "").lower().endswith(".zip")
            limit = service.settings.max_zip_bytes if is_zip else service.settings.max_dicom_bytes
        payload.extend(chunk)
        if len(payload) > limit:
            raise AppError("UPLOAD_TOO_LARGE", "Upload size limit exceeded", 413)
    manifest = await run_in_threadpool(service.ingest, bytes(payload), file.filename)
    created_at = datetime.fromisoformat(manifest["created_at"])
    db.add(
        Study(
            id=manifest["study_id"],
            owner_id=user.id,
            status=manifest["status"],
            created_at=created_at,
            updated_at=created_at,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_study(UUID(manifest["study_id"]))
        raise
    return _summary(storage, UUID(manifest["study_id"]))


@router.get("/studies", response_model=list[StudySummary], responses=error_responses)
def list_studies(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> list[StudySummary]:
    rows = db.scalars(
        select(Study).where(Study.owner_id == user.id).order_by(Study.created_at.desc()).limit(100)
    )
    return [_summary(storage, UUID(row.id)) for row in rows]


@router.get("/studies/{study_id}", response_model=StudySummary, responses=error_responses)
def get_study(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> StudySummary:
    _owned_study(db, study_id, user)
    return _summary(storage, study_id)


@router.delete("/studies/{study_id}", status_code=204, responses=error_responses)
def delete_study(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> Response:
    study = _owned_study(db, study_id, user)
    storage.delete_study(study_id)
    db.delete(study)
    db.commit()
    return Response(status_code=204)


@router.get("/studies/{study_id}/preview/{image_id}", responses={404: {"model": ApiError}})
def get_preview(
    study_id: UUID,
    image_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> Response:
    _owned_study(db, study_id, user)
    path, manifest = _usable_manifest(storage, study_id)
    match = next((item for item in manifest["images"] if item["image_id"] == str(image_id)), None)
    if not match:
        raise AppError("IMAGE_NOT_FOUND", "Image was not found in this study", 404)
    preview = path / match["preview_path"]
    media_type = "image/jpeg" if preview.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return Response(storage.read_bytes(preview, code="PREVIEW_NOT_FOUND"), media_type=media_type)


@router.post(
    "/studies/{study_id}/predict",
    response_model=PredictionResponse,
    responses={
        404: {"model": ApiError},
        409: {"model": ApiError},
        422: {"model": ApiError},
        502: {"model": ApiError},
    },
)
def predict(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[PredictionService, Depends(get_prediction_service)],
) -> PredictionResponse:
    study = _owned_study(db, study_id, user)
    result = service.predict(study_id)
    study.status, study.updated_at = "predicted", datetime.now(UTC)
    db.commit()
    return result


@router.get("/studies/{study_id}/prediction", response_model=PredictionResponse, responses=error_responses)
def get_prediction(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> PredictionResponse:
    _owned_study(db, study_id, user)
    path = storage.require_study(study_id)
    return PredictionResponse.model_validate(
        storage.read_json(path / "prediction.json", code="PREDICTION_NOT_FOUND")
    )


@router.get("/studies/{study_id}/status", responses=error_responses)
def get_status(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> dict[str, Any]:
    _owned_study(db, study_id, user)
    manifest = storage.read_json(storage.require_study(study_id) / "manifest.json")
    progress = {"parsed": 25, "predicting": 60, "predicted": 90, "report_ready": 100}.get(
        manifest["status"], 0
    )
    return {
        "study_id": str(study_id),
        "status": manifest["status"],
        "progress": progress,
        "error": manifest["error"],
    }


@router.get("/studies/{study_id}/csv", responses={404: {"model": ApiError}, 409: {"model": ApiError}})
def get_study_csv(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> Response:
    _owned_study(db, study_id, user)
    path, manifest = _usable_manifest(storage, study_id)
    prediction_path = path / "prediction.json"
    if not prediction_path.is_file():
        raise AppError("PREDICTION_NOT_FOUND", "Study must be predicted before CSV export", 409)

    prediction = storage.read_json(prediction_path)
    metadata = storage.read_json(path / "metadata.json").get("images", {})
    source_filename = manifest.get("source_filename") or str(study_id)
    elapsed = prediction.get("processing_time_seconds")
    rows = []

    for result in prediction.get("results", []):
        image_id = str(result.get("image_id", ""))
        image_metadata = metadata.get(image_id, {})
        violation_type = result.get("violation_type") or []
        findings = result.get("findings") or []
        rows.append({
            "path_to_study": source_filename,
            "study_uid": result.get("study_uid") or image_metadata.get("StudyInstanceUID", ""),
            "image_uid": result.get("image_uid") or image_metadata.get("SOPInstanceUID", ""),
            "anatomical_region": result.get("anatomical_region", ""),
            "quality_class": result.get("quality_class", ""),
            "violation_type": "; ".join(violation_type) if isinstance(violation_type, list) else str(violation_type),
            "processing_status": "Success" if result.get("processing_status", "success") == "success" else "Failure",
            "time_of_processing": elapsed if elapsed is not None else "",
            "confidence": result.get("confidence"),
            "quality_prob": result.get("quality_prob"),
            "findings": "; ".join(findings) if isinstance(findings, list) else str(findings),
        })

    output = io.StringIO(newline="")
    columns = (
        "path_to_study", "study_uid", "image_uid", "anatomical_region",
        "quality_class", "violation_type", "processing_status",
        "time_of_processing", "confidence", "quality_prob", "findings",
    )
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="study-{study_id}-results.csv"'},
    )


@router.post(
    "/studies/{study_id}/report",
    response_model=ReportResponse,
    responses={404: {"model": ApiError}, 409: {"model": ApiError}},
)
def create_report(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    study = _owned_study(db, study_id, user)
    result = service.generate(study_id)
    study.status, study.updated_at = "report_ready", datetime.now(UTC)
    db.commit()
    return result


@router.get("/studies/{study_id}/report", responses={404: {"model": ApiError}})
def get_report(
    study_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> Response:
    _owned_study(db, study_id, user)
    path, _ = _usable_manifest(storage, study_id)
    report = path / "report" / "report.pdf"
    return Response(
        storage.read_bytes(report, code="REPORT_NOT_FOUND"),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="study-{study_id}-report.pdf"'},
    )
