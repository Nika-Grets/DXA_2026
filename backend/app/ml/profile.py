"""Acquisition profile for the organiser's current DXA data."""

MANUFACTURER = "GE Healthcare"
MODEL = "Lunar Prodigy Advance"
PIXEL_X_MM = 0.60
PIXEL_Y_MM = 1.05


def is_expected_device(metadata: dict) -> bool:
    manufacturer = str(metadata.get("Manufacturer", "") or "").strip().lower()
    model = str(metadata.get("ManufacturerModelName", "") or "").strip().lower()
    return manufacturer == MANUFACTURER.lower() and MODEL.lower() in model
