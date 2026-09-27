from collections.abc import Callable
from typing import Protocol, TypeAlias

from app.schemas.batch import StudyResult


class PredictStudy(Protocol):
    def __call__(self, dicom_paths: list[str]) -> StudyResult: ...


PredictStudyCallable: TypeAlias = Callable[[list[str]], StudyResult]  # noqa: UP040
