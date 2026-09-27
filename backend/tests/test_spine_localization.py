import numpy as np

from app.ml.dexa_baseline import classify_study
from app.ml.spine_localizer import localize_spine


def test_three_region_routing_uses_middle_side_shift_for_spine():
    h, w = 300, 300
    # Synthetic images with controllable top-vs-bottom mass shifts.
    def img(shift):
        a = np.zeros((h, w), np.float32)
        for y in range(h):
            cx = int(w * (0.5 + shift * (1 - y / h)))
            a[y, max(0, cx - 12):min(w, cx + 13)] = 1.0
        return a
    out = classify_study([img(-0.25), img(0.01), img(0.27)])
    assert {x.image_index: x.region for x in out} == {0: "femur_left", 1: "spine", 2: "femur_right"}


def test_spine_localizer_returns_normalized_geometry():
    a = np.zeros((300, 300), np.float32)
    for y in range(20, 280):
        cx = int(145 + 0.08 * (y - 150))
        a[y, max(0, cx - 8):cx + 9] = 1.0
    loc = localize_spine(a)
    assert 0 <= loc.bbox[0] <= 1
    assert 0 < loc.bbox[2] <= 1
    assert len(loc.centerline) >= 8
    assert loc.axis_degrees >= 0


def test_region_prediction_keeps_source_image_index():
    h, w = 300, 300
    def img(shift):
        a = np.zeros((h, w), np.float32)
        for y in range(h):
            cx = int(w * (0.5 + shift * (1 - y / h)))
            a[y, max(0, cx - 12):min(w, cx + 13)] = 1.0
        return a
    out = classify_study([img(0.27), img(0.01), img(-0.25)])
    assert {x.image_index: x.region for x in out} == {0: "femur_right", 1: "spine", 2: "femur_left"}


def test_spine_localizer_uses_physical_spacing_for_axis_angle():
    from math import degrees, atan, tan, radians
    from app.ml.profile import PIXEL_X_MM, PIXEL_Y_MM

    h, w = 360, 360
    target_physical = 10.0
    pixel_slope = tan(radians(target_physical)) * PIXEL_Y_MM / PIXEL_X_MM
    image = np.zeros((h, w), dtype=np.float32)
    for y in range(25, 335):
        cx = int(180 + pixel_slope * (y - 180))
        image[y, max(0, cx - 7):min(w, cx + 8)] = 1.0
    loc = localize_spine(image)

    assert abs(loc.axis_degrees_physical - target_physical) < 2.0
    # Because the image pixels are anisotropic, the raw pixel-space angle is
    # materially different from the physical angle for this synthetic case.
    assert abs(loc.axis_degrees - loc.axis_degrees_physical) > 3.0


def test_evaluate_quality_uses_localizer_physical_axis(monkeypatch):
    import app.ml.spine_localizer as spine_module
    from app.ml.spine_localizer import SpineLocalization
    from app.ml.dexa_baseline import evaluate_quality

    loc = SpineLocalization(
        bbox=(0.40, 0.08, 0.20, 0.84),
        centerline=tuple((0.5, y / 10) for y in range(11)),
        axis_degrees=17.0,
        axis_degrees_physical=4.0,
        confidence=0.95,
    )
    monkeypatch.setattr(spine_module, "localize_spine", lambda image: loc)

    image = np.tile(np.linspace(0, 1, 100, dtype=np.float32), (100, 1))
    _, _, violations, _ = evaluate_quality(image, "spine")
    assert "SPINE_AXIS" not in violations
