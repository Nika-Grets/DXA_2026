import numpy as np

from app.ml.dexa_baseline import classify_study


def _hip(shift: float) -> np.ndarray:
    # Uniform body-like signal with a superior/inferior centroid shift.
    image = np.zeros((120, 100), dtype=np.float32)
    image[:, 20:80] = 0.2
    image[:60, int(30 + shift * 100):int(70 + shift * 100)] = 1.0
    image[60:, 40:60] = 1.0
    return image


def test_two_image_bilateral_hip_study_does_not_force_spine():
    out = classify_study([_hip(-0.25), _hip(0.25)])
    assert {item.region for item in out} == {"femur_left", "femur_right"}
    assert {item.image_index for item in out} == {0, 1}


def test_two_image_spine_and_hip_keeps_independent_routes():
    spine = np.ones((120, 100), dtype=np.float32)
    hip = _hip(0.25)
    out = classify_study([spine, hip])
    by_index = {item.image_index: item.region for item in out}
    assert by_index[0] == "spine"
    assert by_index[1] == "femur_right"


def test_large_study_keeps_spine_after_first_three_images():
    spine = np.ones((120, 100), dtype=np.float32)
    out = classify_study([_hip(-0.25), _hip(0.25), _hip(0.25), spine])
    by_index = {item.image_index: item.region for item in out}
    assert by_index[3] == "spine"
    assert by_index[0] == "femur_left"
    assert by_index[1] == "femur_right"
