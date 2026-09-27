import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import router
from app.core.config import Settings, get_settings
from app.core.encryption import EncryptionService
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import Database
from app.ml.dexa_baseline import DexaBaselineAdapter
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.batch_service import BatchService
from app.services.dicom_service import DicomService
from app.services.migration_service import DataMigrationService
from app.services.prediction_service import PredictionService
from app.services.rate_limit_service import AccountRateLimiter
from app.services.report_service import ReportService
from app.services.storage import StorageService
from app.services.upload_service import UploadService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger = configure_logging(settings.log_level)
    database = Database(settings.database_url)
    encryption = EncryptionService(settings.data_encryption_keys, settings.data_encryption_key_file)
    storage = StorageService(settings.data_dir, encryption)
    dicom = DicomService(
        settings.max_decoded_pixels,
        settings.require_burned_in_annotation_no,
    )
    migration = DataMigrationService(storage, dicom)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage.root.mkdir(parents=True, exist_ok=True)
        if settings.auto_create_schema:
            app.state.database.create_schema()
        encrypted, deidentified, quarantined = app.state.migration_service.run()
        logger.info(
            "storage migration completed encrypted=%s deidentified=%s quarantined=%s",
            encrypted,
            deidentified,
            quarantined,
        )
        yield
        app.state.database.engine.dispose()

    app = FastAPI(
        title="Moscow Profiki DICOM Backend",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    app.state.logger = logger
    app.state.database = database
    app.state.encryption = encryption
    app.state.storage = storage
    app.state.auth_service = AuthService(settings)
    app.state.audit_service = AuditService(encryption)
    app.state.rate_limiter = AccountRateLimiter(
        settings.account_rate_limit,
        settings.account_rate_window_seconds,
    )
    app.state.batch_service = BatchService(
        ml_module=settings.ml_study_module,
        timeout_seconds=settings.batch_timeout_seconds,
        max_archive_bytes=settings.max_zip_bytes,
        max_unpacked_bytes=settings.max_unpacked_bytes,
        max_dicom_files=settings.max_dicom_files,
        dicom=dicom,
    )
    app.state.upload_service = UploadService(storage, dicom, settings)
    app.state.prediction_service = PredictionService(storage, dicom, DexaBaselineAdapter())
    app.state.migration_service = migration
    app.state.report_service = ReportService(
        storage, Path(__file__).parent / "templates", settings.report_template
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    if settings.force_https:
        app.add_middleware(HTTPSRedirectMiddleware)
        
    cors_origins = list(dict.fromkeys([
    *settings.cors_origins,
    "http://127.0.0.1:5173",
]))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Authorization"],
)

    @app.middleware("http")
    async def security_operation_and_audit_log(request: Request, call_next):
        started = time.perf_counter()
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if settings.force_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        actor_user_id = getattr(request.state, "audit_actor_id", None)
        if actor_user_id:
            try:
                with app.state.database.session_factory() as audit_db:
                    app.state.audit_service.record_request(
                        audit_db,
                        actor_user_id=actor_user_id,
                        request=request,
                        status_code=response.status_code,
                    )
            except Exception:
                logger.exception(
                    "audit trail write failed request_id=%s path=%s",
                    request.state.request_id,
                    request.url.path,
                )
                response.headers["X-Audit-Trail"] = "failed"
        logger.info(
            "request completed request_id=%s path=%s status=%s duration_ms=%.2f",
            request.state.request_id,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    @app.get("/health", tags=["technical"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router, prefix=settings.api_v1_prefix)
    register_exception_handlers(app)
    return app


app = create_app()
