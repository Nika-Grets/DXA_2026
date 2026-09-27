from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Term:
    code: str
    display_name: str
    category: str  # violation | finding | system
    affects_quality: bool


# Stable internal codes. The organiser-facing wording is isolated here and can be
# replaced when the final terminology dictionary arrives.
TERM_CATALOG: dict[str, Term] = {
    "SPINE_POSITION": Term("SPINE_POSITION", "Некорректная укладка", "violation", True),
    "SPINE_AXIS": Term("SPINE_AXIS", "Не выравнена ось позвоночника", "violation", True),
    "SPINE_ARTIFACT": Term("SPINE_ARTIFACT", "Присутствуют посторонние предметы", "violation", True),
    "HIP_POSITION_ROTATION": Term("HIP_POSITION_ROTATION", "Некорректная укладка", "violation", True),
    "HIP_ROI": Term("HIP_ROI", "Некорректная область интереса", "violation", True),
    "SCOLIOSIS": Term("SCOLIOSIS", "Сколиоз", "finding", False),
    "ENDOPROSTHESIS": Term("ENDOPROSTHESIS", "Эндопротез", "finding", False),
    "NON_DXA_ANATOMY": Term("NON_DXA_ANATOMY", "Неожиданные данные", "system", True),
    "INVALID_IMAGE": Term("INVALID_IMAGE", "Неожиданные данные", "system", True),
}


def term_name(code: str) -> str:
    return TERM_CATALOG.get(code, Term(code, code, "system", True)).display_name
