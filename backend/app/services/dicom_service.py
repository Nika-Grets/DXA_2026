from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.pixels import apply_modality_lut, apply_voi_lut
from pydicom.uid import generate_uid

from app.core.exceptions import AppError

SAFE_TAGS = (
    "Modality",
    "Manufacturer",
    "ManufacturerModelName",
    "Rows",
    "Columns",
    "NumberOfFrames",
    "PixelSpacing",
    "SliceThickness",
    "KVP",
    "Exposure",
    "WindowCenter",
    "WindowWidth",
    "PhotometricInterpretation",
    "BitsStored",
    "BitsAllocated",
    "RescaleSlope",
    "RescaleIntercept",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
)

DEIDENTIFICATION_KEEP_TAGS = {
    *SAFE_TAGS,
    "SOPClassUID",
    "SamplesPerPixel",
    "PlanarConfiguration",
    "HighBit",
    "PixelRepresentation",
    "PixelData",
    "FloatPixelData",
    "DoubleFloatPixelData",
    "PixelAspectRatio",
    "ImageType",
    "SmallestImagePixelValue",
    "LargestImagePixelValue",
    "VOILUTFunction",
    "PresentationLUTShape",
    "LossyImageCompression",
    "LossyImageCompressionRatio",
    "LossyImageCompressionMethod",
    "RedPaletteColorLookupTableDescriptor",
    "GreenPaletteColorLookupTableDescriptor",
    "BluePaletteColorLookupTableDescriptor",
    "RedPaletteColorLookupTableData",
    "GreenPaletteColorLookupTableData",
    "BluePaletteColorLookupTableData",
    "SharedFunctionalGroupsSequence",
    "PerFrameFunctionalGroupsSequence",
    "BurnedInAnnotation",
}
PSEUDONYMIZED_UID_TAGS = ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")


@dataclass(slots=True)
class ParsedDicom:
    dataset: Dataset
    pixels: np.ndarray
    metadata: dict[str, Any]
    frames: int


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)) or value.__class__.__name__ == "MultiValue":
        return [_plain(item) for item in value]
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)


def _safe_metadata(dataset: Dataset, frames: int) -> dict[str, Any]:
    metadata = {name: _plain(getattr(dataset, name)) for name in SAFE_TAGS if hasattr(dataset, name)}
    metadata["NumberOfFrames"] = frames
    return metadata


def _sanitize_sequence(dataset: Dataset) -> None:
    dataset.remove_private_tags()
    for element in list(dataset):
        if element.keyword not in DEIDENTIFICATION_KEEP_TAGS:
            del dataset[element.tag]
            continue
        if element.VR == "SQ":
            for item in element.value:
                _sanitize_sequence(item)


class DicomService:
    def __init__(
        self,
        max_decoded_pixels: int = 50_000_000,
        require_burned_in_annotation_no: bool = True,
    ) -> None:
        self.max_decoded_pixels = max_decoded_pixels
        self.require_burned_in_annotation_no = require_burned_in_annotation_no

    def parse_bytes(self, data: bytes) -> ParsedDicom:
        try:
            dataset = pydicom.dcmread(BytesIO(data), force=False)
        except Exception as exc:
            raise AppError("DICOM_INVALID", "File is not a supported DICOM", 422) from exc
        if "PixelData" not in dataset:
            raise AppError("DICOM_PIXEL_DATA_MISSING", "DICOM has no pixel data", 422)
        rows = int(getattr(dataset, "Rows", 0) or 0)
        columns = int(getattr(dataset, "Columns", 0) or 0)
        frames_declared = int(getattr(dataset, "NumberOfFrames", 1) or 1)
        samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
        if rows <= 0 or columns <= 0:
            raise AppError("DICOM_DIMENSIONS_INVALID", "DICOM dimensions are invalid", 422)
        if rows * columns * frames_declared * samples > self.max_decoded_pixels:
            raise AppError("DICOM_TOO_MANY_PIXELS", "Decoded DICOM pixel limit exceeded", 413)
        try:
            raw = dataset.pixel_array
            pixels = np.asarray(apply_modality_lut(raw, dataset), dtype=np.float32)
            # ML inference consumes numeric pixel intensities directly.  For
            # MONOCHROME1, lower stored values represent brighter pixels;
            # normalize to MONOCHROME2 semantics before any percentile-based
            # anatomy detection.  The current public dataset is MONOCHROME2,
            # but closed/test DICOMs may legitimately use MONOCHROME1.
            if str(getattr(dataset, "PhotometricInterpretation", "")) == "MONOCHROME1":
                finite = pixels[np.isfinite(pixels)]
                if finite.size:
                    lo, hi = float(finite.min()), float(finite.max())
                    pixels = (hi + lo) - pixels
        except Exception as exc:
            raise AppError("DICOM_PIXEL_DECODE_FAILED", "DICOM pixel data cannot be decoded", 422) from exc
        frames = int(getattr(dataset, "NumberOfFrames", 1) or 1)
        if frames > 1 and pixels.ndim < 3:
            frames = 1
        return ParsedDicom(dataset, pixels, _safe_metadata(dataset, frames), frames)

    def deidentify(self, parsed: ParsedDicom, uid_map: dict[str, str]) -> bytes:
        dataset = parsed.dataset
        burned_in = str(getattr(dataset, "BurnedInAnnotation", "")).upper()
        if self.require_burned_in_annotation_no and burned_in == "YES":
            raise AppError(
                "DICOM_BURNED_IN_ANNOTATION_PRESENT",
                "DICOM declares BurnedInAnnotation=YES",
                422,
            )

        _sanitize_sequence(dataset)
        for keyword in PSEUDONYMIZED_UID_TAGS:
            if hasattr(dataset, keyword):
                original = str(getattr(dataset, keyword))
                setattr(dataset, keyword, uid_map.setdefault(original, generate_uid()))

        dataset.PatientIdentityRemoved = "YES"
        dataset.DeidentificationMethod = "DEXA metadata allowlist; UID pseudonymization"
        dataset.BurnedInAnnotation = "NO"
        transfer_syntax = dataset.file_meta.TransferSyntaxUID
        file_meta = FileMetaDataset()
        file_meta.TransferSyntaxUID = transfer_syntax
        if hasattr(dataset, "SOPClassUID"):
            file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
        if hasattr(dataset, "SOPInstanceUID"):
            file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
        dataset.file_meta = file_meta

        parsed.metadata = _safe_metadata(dataset, parsed.frames)
        output = BytesIO()
        try:
            dataset.save_as(output, enforce_file_format=True)
        except Exception as exc:
            raise AppError("DICOM_DEIDENTIFICATION_FAILED", "DICOM could not be de-identified", 422) from exc
        return output.getvalue()

    def load(self, path: Path) -> ParsedDicom:
        return self.parse_bytes(path.read_bytes())

    def preview_array(
        self,
        parsed: ParsedDicom,
        lower_percentile: float,
        upper_percentile: float,
    ) -> np.ndarray:
        image = parsed.pixels[0] if parsed.frames > 1 else parsed.pixels
        if image.ndim == 3 and image.shape[-1] in (3, 4):
            image = image[..., :3].mean(axis=-1)
        try:
            has_window = hasattr(parsed.dataset, "WindowCenter") and hasattr(parsed.dataset, "WindowWidth")
            # parse_bytes() already converts MONOCHROME1 pixels to MONOCHROME2
            # semantics. Re-applying a photometric inversion here would make the
            # preview differ from the pixels used by ML. For MONOCHROME1 keep the
            # normalized inference image as the display source; for MONOCHROME2
            # retain the optional VOI LUT behavior.
            if str(getattr(parsed.dataset, "PhotometricInterpretation", "")) == "MONOCHROME1":
                display = np.asarray(image, dtype=np.float32)
            else:
                display = (
                    np.asarray(apply_voi_lut(image, parsed.dataset), dtype=np.float32) if has_window else image
                )
        except Exception:
            display = image
        finite = display[np.isfinite(display)]
        if finite.size == 0:
            normalized = np.zeros(display.shape, dtype=np.uint8)
        else:
            low, high = np.percentile(finite, [lower_percentile, upper_percentile])
            if high <= low:
                normalized = np.zeros(display.shape, dtype=np.uint8)
            else:
                normalized = np.clip((display - low) / (high - low), 0, 1)
                normalized = np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0)
                normalized = (normalized * 255).round().astype(np.uint8)
        return normalized
