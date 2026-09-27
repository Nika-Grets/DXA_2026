import numpy as np

from app.ml.hip_localizer import localize_hip


def test_hip_localizer_returns_normalized_boxes_and_shaft():
    image = np.zeros((300, 300), dtype=np.float32)
    image[90:280, 135:170] = 1.0
    loc = localize_hip(image, side="right")
    for box in (loc.bone_bbox, loc.roi_bbox, loc.shaft_bbox):
        x, y, w, h = box
        assert 0 <= x <= 1 and 0 <= y <= 1
        assert 0 <= w <= 1 and 0 <= h <= 1
        assert x + w <= 1.000001 and y + h <= 1.000001
    assert loc.shaft_score > 0
    assert loc.confidence > 0


def test_hip_roi_margin_reports_available_physical_space():
    image = np.zeros((300, 300), dtype=np.float32)
    image[90:280, 135:170] = 1.0
    right = localize_hip(image, side="right")
    left = localize_hip(image, side="left")
    # physical_margin_mm = (left, top, right, bottom) available from the
    # anatomical candidate to the image borders; it is not a fixed 20/30 mm pad.
    assert right.physical_margin_mm[0] >= 0
    assert right.physical_margin_mm[2] >= 0
    assert right.physical_margin_mm[1] >= 0
    assert right.physical_margin_mm[3] >= 0
    assert left.physical_margin_mm[0] >= 0
    assert left.physical_margin_mm[2] >= 0


def test_hip_localizer_provides_physical_roi_margins_for_production_criterion():
    from app.ml.dexa_baseline import evaluate_quality

    image = np.zeros((300, 300), dtype=np.float32)
    image[90:280, 135:170] = 1.0
    status, _, violations, _ = evaluate_quality(image, "femur_right")

    assert status in {"acceptable", "issue_detected"}
    # The synthetic candidate has ample physical top/bottom/lateral margins;
    # the ROI criterion should therefore not be raised solely because the
    # production path now uses the anatomical localizer.
    assert "HIP_ROI" not in violations


def test_evaluate_quality_raises_hip_roi_when_physical_margin_is_insufficient(monkeypatch):
    import app.ml.hip_localizer as hip_module
    from app.ml.hip_localizer import HipLocalization
    from app.ml.dexa_baseline import evaluate_quality

    low_margin = HipLocalization(
        side="right",
        bone_bbox=(0.60, 0.20, 0.20, 0.20),
        roi_bbox=(0.60, 0.20, 0.20, 0.20),
        bone_center=(0.70, 0.30),
        roi_margin_px=(50.0, 10.0, 10.0, 20.0),
        confidence=0.9,
        physical_margin_mm=(30.0, 10.0, 6.0, 20.0),
        shaft_bbox=(0.65, 0.35, 0.08, 0.35),
        shaft_score=0.9,
    )
    monkeypatch.setattr(hip_module, "localize_hip", lambda image, side=None: low_margin)

    image = np.tile(np.linspace(0, 1, 100, dtype=np.float32), (100, 1))
    _, _, violations, _ = evaluate_quality(image, "femur_right")
    assert "HIP_ROI" in violations
