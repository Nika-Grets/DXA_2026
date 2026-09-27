import hmac
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    new_refresh_token,
    normalize_email,
    token_hash,
    verify_password,
)
from app.db.models import AuthSession, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret = settings.jwt_secret_key.get_secret_value()

    @staticmethod
    def user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id, email=user.email, full_name=user.full_name, role=user.role, created_at=user.created_at
        )

    def register(self, db: Session, payload: RegisterRequest) -> UserResponse:
        user = User(
            email=normalize_email(payload.email),
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
            role="doctor",
            created_at=datetime.now(UTC),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppError("EMAIL_ALREADY_REGISTERED", "Email is already registered", 409) from exc
        db.refresh(user)
        return self.user_response(user)

    def login(self, db: Session, payload: LoginRequest) -> TokenResponse:
        now = datetime.now(UTC)
        user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
        valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
        if not user or not valid:
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= self.settings.max_login_attempts:
                    user.locked_until = now + timedelta(minutes=self.settings.login_lock_minutes)
                    user.failed_login_attempts = 0
                db.commit()
            raise AppError("INVALID_CREDENTIALS", "Invalid email or password", 401)
        if user.locked_until and _aware(user.locked_until) > now:
            raise AppError("ACCOUNT_LOCKED", "Account is temporarily locked", 423)
        if not user.is_active:
            raise AppError("ACCOUNT_DISABLED", "Account is disabled", 403)
        user.failed_login_attempts = 0
        user.locked_until = None
        session = AuthSession(
            user_id=user.id,
            access_jti_hash="pending-" + new_refresh_token(),
            refresh_token_hash="pending-" + new_refresh_token(),
            expires_at=now + timedelta(days=self.settings.refresh_token_days),
            created_at=now,
        )
        db.add(session)
        db.flush()
        response = self._rotate(session, user)
        db.commit()
        return response

    def refresh(self, db: Session, raw_refresh_token: str) -> TokenResponse:
        now = datetime.now(UTC)
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == token_hash(raw_refresh_token, self.secret)
            )
        )
        if not session or session.revoked_at or _aware(session.expires_at) <= now:
            raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired", 401)
        if not session.user.is_active:
            raise AppError("ACCOUNT_DISABLED", "Account is disabled", 403)
        response = self._rotate(session, session.user)
        db.commit()
        return response

    def _rotate(self, session: AuthSession, user: User) -> TokenResponse:
        access, jti, _ = create_access_token(
            user_id=user.id, session_id=session.id, token_version=user.token_version, settings=self.settings
        )
        refresh = new_refresh_token()
        session.access_jti_hash = token_hash(jti, self.secret)
        session.refresh_token_hash = token_hash(refresh, self.secret)
        session.expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days)
        return TokenResponse(
            access_token=access, refresh_token=refresh, expires_in=self.settings.access_token_minutes * 60
        )

    def authenticate(self, db: Session, raw_access_token: str) -> tuple[User, AuthSession]:
        claims = decode_access_token(raw_access_token, self.settings)
        if claims.get("typ") != "access":
            raise AppError("INVALID_TOKEN", "Unexpected token type", 401)
        session = db.get(AuthSession, claims["sid"])
        expected = token_hash(claims["jti"], self.secret)
        if (
            not session
            or session.user_id != claims["sub"]
            or session.revoked_at
            or not hmac.compare_digest(session.access_jti_hash, expected)
        ):
            raise AppError("INVALID_TOKEN", "Token session is invalid", 401)
        user = session.user
        if not user.is_active or user.token_version != claims["ver"]:
            raise AppError("INVALID_TOKEN", "Token has been revoked", 401)
        return user, session

    @staticmethod
    def logout(db: Session, session: AuthSession) -> None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
