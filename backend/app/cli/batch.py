import argparse
import sys
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.batch_service import BatchService
from app.services.dicom_service import DicomService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process a local DICOM dataset directory or ZIP")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("batch_report.csv"))
    parser.add_argument("--visualizations", action="store_true")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    settings = Settings()
    service = BatchService(
        ml_module=settings.ml_study_module,
        timeout_seconds=settings.batch_timeout_seconds,
        max_archive_bytes=settings.max_zip_bytes,
        max_unpacked_bytes=settings.max_unpacked_bytes,
        max_dicom_files=settings.max_dicom_files,
        dicom=DicomService(settings.max_decoded_pixels, False),
    )
    try:
        artifact = service.process_path(
            arguments.source,
            include_visualizations=arguments.visualizations,
        )
        output = arguments.output
        if arguments.visualizations and output.suffix.lower() != ".zip":
            output = output.with_suffix(".zip")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(artifact.content)
        print(f"written={output} rows={len(artifact.rows)}")
        return 0
    except AppError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"BATCH_FAILED: {type(exc).__name__}: {str(exc)[:500]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
