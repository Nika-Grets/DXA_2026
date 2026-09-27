import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.exceptions import AppError

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("constant-time-dummy-password")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def token_hash(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(*, user_id: str, session_id: str, token_version: int, settings: Settings):
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": jti,
        "ver": token_version,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
    }
    encoded = jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
    return encoded, jti, expires_at


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "nbf", "jti", "sub", "sid", "typ", "ver"]},
        )
    except InvalidTokenError as exc:
        raise AppError("INVALID_TOKEN", "Token is invalid or expired", 401) from exc
