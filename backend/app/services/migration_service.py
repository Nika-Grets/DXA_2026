import logging

from app.core.exceptions import AppError
from app.services.dicom_service import DicomService
from app.services.storage import StorageService

log = logging.getLogger(__name__)


class DataMigrationService:
    def __init__(self, storage: StorageService, dicom: DicomService) -> None:
        self.storage = storage
        self.dicom = dicom

    def run(self) -> tuple[int, int, int]:
        encrypted = self.storage.encrypt_legacy_tree()
        deidentified = 0
        quarantined = 0
        for study_path in self.storage.root.iterdir():
            manifest_path = study_path / "manifest.json"
            if not study_path.is_dir() or not manifest_path.is_file():
                continue
            try:
                manifest = self.storage.read_json(manifest_path)
            except AppError:
                log.exception("Cannot read legacy manifest path=%s", manifest_path)
                quarantined += 1
                continue
            if manifest.get("deidentified") is True:
                continue
            try:
                self._deidentify_study(study_path, manifest)
                deidentified += 1
            except AppError as exc:
                self._quarantine(study_path, manifest, exc)
                quarantined += 1
        return encrypted, deidentified, quarantined

    def _deidentify_study(self, study_path, manifest: dict) -> None:
        uid_map: dict[str, str] = {}
        metadata: dict[str, dict] = {}
        for image in manifest.get("images", []):
            image_id = image["image_id"]
            original = study_path / image["dicom_path"]
            parsed = self.dicom.parse_bytes(self.storage.read_bytes(original))
            sanitized = self.dicom.deidentify(parsed, uid_map)
            self.storage.write_bytes_atomic(original, sanitized)
            metadata[image_id] = parsed.metadata
        manifest["deidentified"] = True
        manifest["deidentification_method"] = "metadata allowlist, private-tag removal, UID pseudonymization"
        manifest["error"] = None
        self.storage.write_json_atomic(
            study_path / "metadata.json",
            {"study_id": manifest["study_id"], "images": metadata},
        )
        self.storage.write_json_atomic(study_path / "manifest.json", manifest)

    def _quarantine(self, study_path, manifest: dict, exc: AppError) -> None:
        manifest["status"] = "failed"
        manifest["deidentified"] = False
        manifest["error"] = {
            "code": "LEGACY_DICOM_QUARANTINED",
            "message": "Legacy study failed mandatory de-identification",
            "cause": exc.code,
        }
        self.storage.write_json_atomic(
            study_path / "metadata.json",
            {"study_id": manifest.get("study_id"), "images": {}},
        )
        self.storage.write_json_atomic(study_path / "manifest.json", manifest)
        log.warning("Quarantined legacy DICOM study path=%s cause=%s", study_path, exc.code)
