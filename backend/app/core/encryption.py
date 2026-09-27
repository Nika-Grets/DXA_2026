import base64
import hmac
import logging
import os
import struct
from hashlib import sha256
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from app.core.exceptions import AppError

MAGIC = b"DEXAENC1"
NONCE_SIZE = 12
log = logging.getLogger(__name__)


class EncryptionService:
    """AES-256-GCM encryption with key rotation and path-bound AAD."""

    def __init__(self, configured_keys: SecretStr | str, key_file: Path | None = None) -> None:
        raw = (
            configured_keys.get_secret_value() if isinstance(configured_keys, SecretStr) else configured_keys
        )
        if not raw and key_file:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            if key_file.is_file():
                raw = key_file.read_text(encoding="ascii").strip()
            else:
                raw = self.generate_key("local")
                fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="ascii") as handle:
                    handle.write(raw)
                log.warning("Generated a local data key at %s; back it up securely", key_file)
        self.keys: dict[str, bytes] = {}
        for item in filter(None, (part.strip() for part in raw.split(","))):
            key_id, separator, encoded = item.partition(":")
            if not separator or not key_id.isascii() or len(key_id) > 64:
                raise ValueError("Encryption keys must use key_id:base64 format")
            try:
                key = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise ValueError("Encryption key is not valid base64") from exc
            if len(key) != 32:
                raise ValueError("AES-256-GCM keys must contain exactly 32 bytes")
            self.keys[key_id] = key
        if not self.keys:
            raise ValueError("DATA_ENCRYPTION_KEYS or a durable key file is required")
        self.active_key_id = next(iter(self.keys))

    @staticmethod
    def generate_key(key_id: str = "v1") -> str:
        return f"{key_id}:{base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()}"

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> bytes:
        key_id = self.active_key_id.encode("ascii")
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = AESGCM(self.keys[self.active_key_id]).encrypt(nonce, plaintext, aad)
        return MAGIC + struct.pack("!H", len(key_id)) + key_id + nonce + ciphertext

    def decrypt(self, payload: bytes, *, aad: bytes) -> bytes:
        if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 2 + NONCE_SIZE + 16:
            raise AppError("STORAGE_INTEGRITY_ERROR", "Encrypted resource is invalid", 500)
        offset = len(MAGIC)
        key_len = struct.unpack("!H", payload[offset : offset + 2])[0]
        offset += 2
        key_id = payload[offset : offset + key_len].decode("ascii", errors="strict")
        offset += key_len
        key = self.keys.get(key_id)
        if key is None:
            raise AppError("ENCRYPTION_KEY_UNAVAILABLE", "Required data key is unavailable", 500)
        nonce = payload[offset : offset + NONCE_SIZE]
        ciphertext = payload[offset + NONCE_SIZE :]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise AppError(
                "STORAGE_INTEGRITY_ERROR", "Encrypted resource failed integrity check", 500
            ) from exc

    @staticmethod
    def aad_for(root: Path, path: Path) -> bytes:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        return b"dexa-file:v1:" + sha256(relative.encode()).digest()

    def derive_key(self, key_id: str, purpose: bytes) -> bytes:
        key = self.keys.get(key_id)
        if key is None:
            raise AppError("ENCRYPTION_KEY_UNAVAILABLE", "Required audit key is unavailable", 500)
        return hmac.new(key, b"dexa-key-derivation-v1:" + purpose, sha256).digest()

    def active_derived_key(self, purpose: bytes) -> tuple[str, bytes]:
        return self.active_key_id, self.derive_key(self.active_key_id, purpose)
