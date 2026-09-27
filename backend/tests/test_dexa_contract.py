from uuid import uuid4
import numpy as np

from app.ml.dexa_baseline import DexaBaselineAdapter
from app.terminology import term_name


def test_official_violation_wording():
    assert term_name("SPINE_POSITION") == "Некорректная укладка"
    assert term_name("SPINE_AXIS") == "Не выравнена ось позвоночника"
    assert term_name("SPINE_ARTIFACT") == "Присутствуют посторонние предметы"
    assert term_name("HIP_POSITION_ROTATION") == "Некорректная укладка"
    assert term_name("HIP_ROI") == "Некорректная область интереса"


def test_output_contract_is_binary_and_side_agnostic():
    image = np.zeros((300, 300), dtype=np.uint8)
    image[50:250, 130:170] = 220
    result = DexaBaselineAdapter().predict_study([
        (uuid4(), image, {
            "StudyInstanceUID": "study",
            "SOPInstanceUID": "image",
            "Manufacturer": "GE Healthcare",
            "ManufacturerModelName": "Lunar Prodigy Advance",
        })
    ]).results[0]
    assert result.quality_class in (0, 1)
    assert 0 <= result.quality_prob <= 1
    assert result.anatomical_region in {
        "Поясничный отдел позвоночника",
        "Проксимальный отдел бедра",
    }
