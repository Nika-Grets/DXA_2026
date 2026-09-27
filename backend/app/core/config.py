from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    data_dir: Path = Path("./data/studies")
    database_url: str = "sqlite:///./data/app.db"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://localhost:5173"]
    allowed_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    force_https: bool = False
    enable_docs: bool = True
    auto_create_schema: bool = True
    jwt_secret_key: SecretStr = SecretStr("development-only-change-me-32-bytes")
    jwt_issuer: str = "dexa-backend"
    jwt_audience: str = "dexa-frontend"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    data_encryption_keys: SecretStr = SecretStr("")
    data_encryption_key_file: Path = Path("./data/.encryption-key")
    max_login_attempts: int = 5
    login_lock_minutes: int = 15
    account_rate_limit: int = 10
    account_rate_window_seconds: float = 1.0
    upload_cooldown_seconds: float = 3.0
    delete_cooldown_seconds: float = 3.0
    predict_cooldown_seconds: float = 10.0
    report_cooldown_seconds: float = 10.0
    batch_cooldown_seconds: float = 30.0
    batch_timeout_seconds: float = 180.0
    ml_study_module: str = "app.external_ml.inference"
    enable_experimental_benchmark_heads: bool = False
    max_dicom_bytes: int = 104_857_600
    max_zip_bytes: int = 524_288_000
    max_dicom_files: int = 500
    max_unpacked_bytes: int = 1_073_741_824
    max_decoded_pixels: int = 50_000_000
    require_burned_in_annotation_no: bool = True
    preview_format: str = "png"
    jpeg_quality: int = 90
    preview_lower_percentile: float = 1.0
    preview_upper_percentile: float = 99.0
    preview_max_side: int | None = None
    log_level: str = "INFO"
    report_template: str = "report.html"

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("preview_format")
    @classmethod
    def validate_preview_format(cls, value: str) -> str:
        value = value.lower()
        if value not in {"png", "jpeg"}:
            raise ValueError("PREVIEW_FORMAT must be png or jpeg")
        return value

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if self.access_token_minutes <= 0 or self.refresh_token_days <= 0:
            raise ValueError("Token lifetimes must be positive")
        cooldowns = (
            self.upload_cooldown_seconds,
            self.delete_cooldown_seconds,
            self.predict_cooldown_seconds,
            self.report_cooldown_seconds,
            self.batch_cooldown_seconds,
        )
        if (
            self.account_rate_limit <= 0
            or self.account_rate_window_seconds <= 0
            or any(v < 0 for v in cooldowns)
        ):
            raise ValueError("Rate limits and cooldowns must be positive")
        if self.batch_timeout_seconds <= 0 or not self.ml_study_module.strip():
            raise ValueError("Batch timeout and ML study module must be configured")
        if self.app_env.lower() == "production":
            jwt_secret = self.jwt_secret_key.get_secret_value()
            if len(jwt_secret) < 32 or jwt_secret == "development-only-change-me-32-bytes":
                raise ValueError("JWT_SECRET_KEY must be a unique secret containing at least 32 characters")
            if not self.data_encryption_keys.get_secret_value():
                raise ValueError("DATA_ENCRYPTION_KEYS is required in production")
            if not self.force_https:
                raise ValueError("FORCE_HTTPS must be enabled in production")
            if self.enable_docs:
                raise ValueError("ENABLE_DOCS must be disabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
