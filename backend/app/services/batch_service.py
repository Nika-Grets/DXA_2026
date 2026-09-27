import csv
import hashlib
import importlib
import io
import multiprocessing
import queue
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import pydicom
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.batch import BatchReportRow, StudyPrediction
from app.services.dicom_service import DicomService
from app.services.preview_service import encode_preview


@dataclass(slots=True)
class BatchArtifact:
    content: bytes
    filename: str
    media_type: str
    rows: list[BatchReportRow]


@dataclass(slots=True)
class _Image:
    path: Path
    relative_path: str
    path_to_study: str
    study_uid: str
    image_uid: str


def _plain_prediction(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return dict(item.model_dump())
    if isinstance(item, dict):
        return dict(item)
    return {
        key: getattr(item, key)
        for key in ("image_uid", "anatomical_region", "quality_class", "violation_type")
        if hasattr(item, key)
    }


def _predict_worker(module_name: str, dicom_paths: list[str], result_queue) -> None:
    try:
        module = importlib.import_module(module_name)
        function = module.predict_study
        result = function(dicom_paths)
        if not isinstance(result, list):
            raise TypeError("predict_study must return a list")
        result_queue.put(("ok", [_plain_prediction(item) for item in result]))
    except BaseException as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {str(exc)[:500]}"))


class BatchService:
    columns = (
        "path_to_study",
        "study_uid",
        "image_uid",
        "anatomical_region",
        "quality_class",
        "violation_type",
        "processing_status",
        "time_of_processing",
        "confidence",
        "quality_prob",
        "findings",
    )

    def __init__(
        self,
        *,
        ml_module: str,
        timeout_seconds: float,
        max_archive_bytes: int,
        max_unpacked_bytes: int,
        max_dicom_files: int,
        dicom: DicomService,
    ) -> None:
        self.ml_module = ml_module
        self.timeout_seconds = timeout_seconds
        self.max_archive_bytes = max_archive_bytes
        self.max_unpacked_bytes = max_unpacked_bytes
        self.max_dicom_files = max_dicom_files
        self.dicom = dicom

    def process_archive(
        self,
        payload: bytes,
        filename: str | None,
        *,
        include_visualizations: bool = False,
    ) -> BatchArtifact:
        if not payload:
            raise AppError("BAD_REQUEST", "Batch archive is empty", 400)
        if len(payload) > self.max_archive_bytes:
            raise AppError("UPLOAD_TOO_LARGE", "Batch archive size limit exceeded", 413)
        if not (payload.startswith(b"PK\x03\x04") or (filename or "").lower().endswith(".zip")):
            raise AppError("UNSUPPORTED_MEDIA_TYPE", "Batch endpoint accepts a ZIP archive", 415)
        with tempfile.TemporaryDirectory(prefix="dexa-batch-") as temporary:
            root = Path(temporary)
            self._extract(payload, root)
            return self.process_directory(root, include_visualizations=include_visualizations)

    def process_path(
        self,
        source: Path,
        *,
        include_visualizations: bool = False,
    ) -> BatchArtifact:
        source = source.resolve()
        if source.is_dir():
            return self.process_directory(source, include_visualizations=include_visualizations)
        if source.is_file() and source.suffix.lower() == ".zip":
            return self.process_archive(
                source.read_bytes(),
                source.name,
                include_visualizations=include_visualizations,
            )
        raise AppError("BATCH_SOURCE_INVALID", "Source must be a directory or ZIP archive", 422)

    def process_directory(
        self,
        root: Path,
        *,
        include_visualizations: bool = False,
    ) -> BatchArtifact:
        files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".dcm")
        if not files:
            raise AppError("DICOM_INVALID", "No .dcm files found in batch source", 422)
        if len(files) > self.max_dicom_files:
            raise AppError("UPLOAD_TOO_LARGE", "Batch DICOM file count limit exceeded", 413)

        groups: dict[str, dict[str, _Image]] = {}
        rows: list[BatchReportRow] = []
        failed_keys: set[tuple[str, str]] = set()
        for path in files:
            try:
                image = self._inspect(root, path)
                groups.setdefault(image.study_uid, {}).setdefault(image.image_uid, image)
            except Exception as exc:
                failed = self._failure_for_unreadable(root, path, exc)
                key = (failed.study_uid, failed.image_uid)
                if key not in failed_keys:
                    rows.append(failed)
                    failed_keys.add(key)

        visualizations: dict[str, bytes] = {}
        for images_by_uid in groups.values():
            images = list(images_by_uid.values())
            started = time.perf_counter()
            try:
                predictions = self._predict_with_timeout([str(image.path) for image in images])
                elapsed = time.perf_counter() - started
                rows.extend(self._success_rows(images, predictions, elapsed))
                if include_visualizations:
                    visualizations.update(self._make_visualizations(images))
            except Exception as exc:
                rows.extend(self._failure_rows(images, exc))

        rows.sort(key=lambda row: (row.path_to_study, row.image_uid))
        report = self._csv(rows)
        if not include_visualizations:
            return BatchArtifact(report, "batch_report.csv", "text/csv; charset=utf-8", rows)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("batch_report.csv", report)
            for name, content in visualizations.items():
                archive.writestr(f"visualizations/{name}", content)
        return BatchArtifact(output.getvalue(), "batch_result.zip", "application/zip", rows)

    def _extract(self, payload: bytes, root: Path) -> None:
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise AppError("UNSUPPORTED_MEDIA_TYPE", "Invalid ZIP archive", 415) from exc
        total = 0
        extracted = 0
        try:
            infos = archive.infolist()
            for info in infos:
                normalized = info.filename.replace("\\", "/")
                relative = PurePosixPath(normalized)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or (relative.parts and relative.parts[0].endswith(":"))
                ):
                    raise AppError("ZIP_PATH_TRAVERSAL", "Unsafe ZIP path", 422)
                if info.is_dir() or not normalized.lower().endswith(".dcm"):
                    continue
                total += info.file_size
                extracted += 1
                if total > self.max_unpacked_bytes or extracted > self.max_dicom_files:
                    raise AppError("UPLOAD_TOO_LARGE", "Batch archive unpacked limit exceeded", 413)
                target = root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source, target.open("wb") as destination:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if (
                            written > info.file_size
                            or total - info.file_size + written > self.max_unpacked_bytes
                        ):
                            raise AppError("UPLOAD_TOO_LARGE", "Batch archive expanded limit exceeded", 413)
                        destination.write(chunk)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("BATCH_ARCHIVE_READ_FAILED", "Batch archive could not be extracted", 422) from exc
        finally:
            archive.close()
        if extracted == 0:
            raise AppError("DICOM_INVALID", "No .dcm files found in batch archive", 422)

    @staticmethod
    def _inspect(root: Path, path: Path) -> _Image:
        relative = path.relative_to(root).as_posix()
        dataset = pydicom.dcmread(
            path,
            stop_before_pixels=True,
            force=False,
            specific_tags=["StudyInstanceUID", "SOPInstanceUID"],
        )
        study_uid = str(getattr(dataset, "StudyInstanceUID", "") or path.parent.relative_to(root).as_posix())
        image_uid = str(
            getattr(dataset, "SOPInstanceUID", "") or hashlib.sha256(path.read_bytes()).hexdigest()
        )
        return _Image(
            path=path,
            relative_path=relative,
            path_to_study=path.parent.relative_to(root).as_posix() or ".",
            study_uid=study_uid,
            image_uid=image_uid,
        )

    def _predict_with_timeout(self, paths: list[str]) -> list[StudyPrediction]:
        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_predict_worker,
            args=(self.ml_module, paths, result_queue),
        )
        process.start()
        process.join(self.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
            result_queue.close()
            raise TimeoutError(f"study processing exceeded {self.timeout_seconds:g} seconds")
        try:
            status, payload = result_queue.get(timeout=2)
        except queue.Empty as exc:
            raise RuntimeError(f"ML process exited with code {process.exitcode} without a result") from exc
        finally:
            result_queue.close()
        if status != "ok":
            raise RuntimeError(payload)
        try:
            return [StudyPrediction.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise ValueError(f"invalid StudyResult: {exc.errors(include_url=False)}") from exc

    @staticmethod
    def _success_rows(images: list[_Image], predictions: list[StudyPrediction], elapsed: float) -> list[BatchReportRow]:
        by_uid = {item.image_uid: item for item in predictions if item.image_uid}
        positional = iter(item for item in predictions if not item.image_uid)
        rows = []
        for image in images:
            prediction = by_uid.get(image.image_uid) or next(positional, None)
            if prediction is None:
                rows.append(BatchService._failure_row(image, "ML result is missing for image", now))
                continue
            rows.append(
                BatchReportRow(
                    path_to_study=image.path_to_study,
                    study_uid=image.study_uid,
                    image_uid=image.image_uid,
                    anatomical_region=prediction.anatomical_region,
                    quality_class=prediction.quality_class,
                    violation_type=prediction.violation_type,
                    processing_status="Success",
                    time_of_processing=elapsed,
                    confidence=prediction.confidence,
                    quality_prob=prediction.quality_prob,
                    findings=prediction.findings,
                )
            )
        return rows

    @staticmethod
    def _failure_row(image: _Image, message: str, now: datetime | None = None) -> BatchReportRow:
        return BatchReportRow(
            path_to_study=image.path_to_study,
            study_uid=image.study_uid,
            image_uid=image.image_uid,
            anatomical_region="",
            quality_class="",
            violation_type=message[:500],
            processing_status="Failure",
            time_of_processing=0.0,
        )

    @classmethod
    def _failure_rows(cls, images: list[_Image], exc: Exception) -> list[BatchReportRow]:
        message = f"{type(exc).__name__}: {str(exc)[:450]}"
        now = datetime.now(UTC)
        return [cls._failure_row(image, message, now) for image in images]

    @classmethod
    def _failure_for_unreadable(cls, root: Path, path: Path, exc: Exception) -> BatchReportRow:
        try:
            relative = path.relative_to(root).as_posix()
            relative_parent = path.parent.relative_to(root).as_posix() or "."
        except ValueError:
            relative = path.name
            relative_parent = "."
        try:
            image_uid = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            image_uid = hashlib.sha256(relative.encode()).hexdigest()
        image = _Image(
            path=path,
            relative_path=relative,
            path_to_study=relative_parent,
            study_uid=relative_parent,
            image_uid=image_uid,
        )
        return cls._failure_row(image, f"{type(exc).__name__}: {str(exc)[:450]}")

    def _make_visualizations(self, images: list[_Image]) -> dict[str, bytes]:
        result = {}
        for image in images:
            try:
                parsed = self.dicom.parse_bytes(image.path.read_bytes())
                pixels = self.dicom.preview_array(parsed, 1.0, 99.0)
                result[f"{image.image_uid}.png"] = encode_preview(pixels, image_format="png")
            except Exception:
                continue
        return result

    @classmethod
    def _csv(cls, rows: list[BatchReportRow]) -> bytes:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=cls.columns)
        writer.writeheader()
        for row in rows:
            values = row.model_dump(mode="json")
            writer.writerow({column: values[column] for column in cls.columns})
        return output.getvalue().encode("utf-8-sig")
