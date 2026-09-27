import shutil
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.dicom_service import DicomService
from app.services.preview_service import encode_preview
from app.services.storage import StorageService


class UploadService:
    def __init__(self, storage: StorageService, dicom: DicomService, settings: Settings) -> None:
        self.storage = storage
        self.dicom = dicom
        self.settings = settings

    def ingest(self, payload: bytes, filename: str | None) -> dict:
        if not payload:
            raise AppError("BAD_REQUEST", "Uploaded file is empty", 400)
        study_id = uuid4()
        study_path = self.storage.create_study(study_id)
        try:
            uid_map: dict[str, str] = {}
            last_error: AppError | None = None
            candidates = self._candidates(payload, filename)
            images: list[dict] = []
            metadata_by_image: dict[str, dict] = {}
            for data in candidates:
                if len(images) >= self.settings.max_dicom_files:
                    raise AppError("UPLOAD_TOO_LARGE", "DICOM file count limit exceeded", 413)
                try:
                    parsed = self.dicom.parse_bytes(data)
                    data = self.dicom.deidentify(parsed, uid_map)
                except AppError as exc:
                    last_error = exc
                    continue
                image_id = uuid4()
                extension = "jpg" if self.settings.preview_format == "jpeg" else "png"
                dicom_rel = f"original/{image_id}.dcm"
                preview_rel = f"preview/{image_id}.{extension}"
                self.storage.write_bytes_atomic(study_path / dicom_rel, data)
                pixels = self.dicom.preview_array(
                    parsed,
                    self.settings.preview_lower_percentile,
                    self.settings.preview_upper_percentile,
                )
                preview = encode_preview(
                    pixels,
                    image_format=self.settings.preview_format,
                    jpeg_quality=self.settings.jpeg_quality,
                    max_side=self.settings.preview_max_side,
                )
                self.storage.write_bytes_atomic(study_path / preview_rel, preview)
                images.append(
                    {
                        "image_id": str(image_id),
                        "dicom_path": dicom_rel,
                        "preview_path": preview_rel,
                        "frames": parsed.frames,
                    }
                )
                metadata_by_image[str(image_id)] = parsed.metadata
            if not images:
                raise last_error or AppError("DICOM_INVALID", "No valid DICOM files found", 422)
            created_at = datetime.now(UTC).isoformat()
            manifest = {
                "study_id": str(study_id),
                "source_filename": filename or "",
                "status": "parsed",
                "created_at": created_at,
                "deidentified": True,
                "deidentification_method": "metadata allowlist, private-tag removal, UID pseudonymization",
                "images": images,
                "error": None,
            }
            self.storage.write_json_atomic(
                study_path / "metadata.json",
                {"study_id": str(study_id), "images": metadata_by_image},
            )
            self.storage.write_json_atomic(study_path / "manifest.json", manifest)
            return manifest
        except Exception:
            shutil.rmtree(study_path, ignore_errors=True)
            raise

    def _candidates(self, payload: bytes, filename: str | None) -> Iterator[bytes]:
        is_zip = payload.startswith(b"PK\x03\x04") or (filename or "").lower().endswith(".zip")
        if not is_zip:
            if len(payload) > self.settings.max_dicom_bytes:
                raise AppError("UPLOAD_TOO_LARGE", "DICOM size limit exceeded", 413)
            yield payload
            return
        if len(payload) > self.settings.max_zip_bytes:
            raise AppError("UPLOAD_TOO_LARGE", "ZIP size limit exceeded", 413)
        try:
            archive = zipfile.ZipFile(BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise AppError("UNSUPPORTED_MEDIA_TYPE", "Invalid ZIP archive", 415) from exc
        total = 0
        with archive:
            infos = archive.infolist()
            if len(infos) > max(self.settings.max_dicom_files * 10, 1000):
                raise AppError("UPLOAD_TOO_LARGE", "ZIP entry count limit exceeded", 413)
            for info in infos:
                normalized = info.filename.replace("\\", "/")
                path = PurePosixPath(normalized)
                if path.is_absolute() or ".." in path.parts or (path.parts and path.parts[0].endswith(":")):
                    raise AppError("ZIP_PATH_TRAVERSAL", "Unsafe ZIP path", 422)
                if info.is_dir():
                    continue
                total += info.file_size
                if total > self.settings.max_unpacked_bytes:
                    raise AppError("UPLOAD_TOO_LARGE", "ZIP unpacked size limit exceeded", 413)
                if info.file_size > self.settings.max_dicom_bytes:
                    continue
                yield archive.read(info)
