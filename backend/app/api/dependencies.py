from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models import AuthSession, User
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.batch_service import BatchService
from app.services.prediction_service import PredictionService
from app.services.report_service import ReportService
from app.services.storage import StorageService
from app.services.upload_service import UploadService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def get_upload_service(request: Request) -> UploadService:
    return request.app.state.upload_service


def get_prediction_service(request: Request) -> PredictionService:
    return request.app.state.prediction_service


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_audit_service(request: Request) -> AuditService:
    return request.app.state.audit_service


def get_batch_service(request: Request) -> BatchService:
    return request.app.state.batch_service


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.session()


def _apply_request_limits(request: Request, user_id: str) -> None:
    limiter = request.app.state.rate_limiter
    settings = request.app.state.settings
    limiter.check(user_id)
    path = request.url.path.removeprefix(settings.api_v1_prefix)
    method = request.method.upper()
    cooldown: tuple[str, float] | None = None
    if method == "POST" and path == "/upload":
        cooldown = ("study.upload", settings.upload_cooldown_seconds)
    elif method == "DELETE" and path.startswith("/studies/"):
        cooldown = (f"study.delete:{path}", settings.delete_cooldown_seconds)
    elif method == "POST" and path == "/batch":
        cooldown = ("study.batch", settings.batch_cooldown_seconds)
    elif method == "POST" and path.endswith("/predict"):
        cooldown = (f"study.predict:{path}", settings.predict_cooldown_seconds)
    elif method == "POST" and path.endswith("/report"):
        cooldown = (f"study.report:{path}", settings.report_cooldown_seconds)
    if cooldown:
        limiter.check_cooldown(user_id, *cooldown)


def get_current_auth(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> tuple[User, AuthSession]:
    if not token:
        raise AppError("AUTHENTICATION_REQUIRED", "Bearer token is required", 401)
    user, session = service.authenticate(db, token)
    request.state.audit_actor_id = user.id
    _apply_request_limits(request, user.id)
    return user, session


def get_current_user(auth: Annotated[tuple[User, AuthSession], Depends(get_current_auth)]) -> User:
    return auth[0]
