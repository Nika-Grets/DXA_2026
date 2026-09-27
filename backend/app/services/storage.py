import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.encryption import MAGIC, EncryptionService
from app.core.exceptions import AppError


class StorageService:
    def __init__(self, root: Path, encryption: EncryptionService) -> None:
        self.root = root.resolve()
        self.encryption = encryption
        self.root.mkdir(parents=True, exist_ok=True)

    def study_dir(self, study_id: UUID) -> Path:
        return self.root / str(study_id)

    def create_study(self, study_id: UUID) -> Path:
        path = self.study_dir(study_id)
        for child in ("original", "preview", "report", "masks"):
            (path / child).mkdir(parents=True, exist_ok=False)
        return path

    def require_study(self, study_id: UUID) -> Path:
        path = self.study_dir(study_id)
        if not path.is_dir():
            raise AppError("STUDY_NOT_FOUND", "Study was not found", 404)
        return path

    def encrypt_legacy_tree(self) -> int:
        """Encrypt every pre-existing plaintext file before the API starts."""
        migrated = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            payload = path.read_bytes()
            if not payload.startswith(MAGIC):
                self._write_encrypted_atomic(path, payload)
                migrated += 1
        return migrated

    def delete_study(self, study_id: UUID) -> None:
        shutil.rmtree(self.require_study(study_id))

    def _write_encrypted_atomic(self, path: Path, plaintext: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.encryption.encrypt(plaintext, aad=self.encryption.aad_for(self.root, path))
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_json_atomic(self, path: Path, data: Any) -> None:
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        self._write_encrypted_atomic(path, encoded)

    def write_bytes_atomic(self, path: Path, data: bytes) -> None:
        self._write_encrypted_atomic(path, data)

    def read_bytes(self, path: Path, *, code: str = "RESOURCE_NOT_FOUND") -> bytes:
        if not path.is_file():
            raise AppError(code, "Requested resource was not found", 404)
        try:
            payload = path.read_bytes()
            if not payload.startswith(MAGIC):
                self._write_encrypted_atomic(path, payload)
                return payload
            return self.encryption.decrypt(payload, aad=self.encryption.aad_for(self.root, path))
        except AppError:
            raise
        except OSError as exc:
            raise AppError("STORAGE_ERROR", "Stored data could not be read", 500) from exc

    def read_json(self, path: Path, *, code: str = "RESOURCE_NOT_FOUND") -> Any:
        try:
            return json.loads(self.read_bytes(path, code=code))
        except AppError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AppError("STORAGE_ERROR", "Stored data could not be decoded", 500) from exc
