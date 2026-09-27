import pytest
from pydantic import ValidationError

from app.schemas.prediction import BBoxROI, PolygonROI


def test_bbox_must_fit_normalized_bounds():
    with pytest.raises(ValidationError):
        BBoxROI(x=0.8, y=0.1, width=0.3, height=0.2)


def test_polygon_requires_three_normalized_points():
    with pytest.raises(ValidationError):
        PolygonROI(points=[(0.0, 0.0), (1.1, 0.5)])
