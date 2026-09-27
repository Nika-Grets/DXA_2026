import time

import pydicom


def predict_study(dicom_paths: list[str]) -> list[dict]:
    if any("ml-failure" in path for path in dicom_paths):
        raise RuntimeError("synthetic study failure")
    if any("slow-study" in path for path in dicom_paths):
        time.sleep(5)
    result = []
    for path in dicom_paths:
        dataset = pydicom.dcmread(path, stop_before_pixels=True)
        result.append(
            {
                "image_uid": str(dataset.SOPInstanceUID),
                "anatomical_region": "lumbar_spine",
                "quality_class": "acceptable",
                "violation_type": "none",
            }
        )
    return result
