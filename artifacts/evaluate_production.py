"""Evaluate the frozen production output against canonical expert labels.

This script does NOT retrain any model and does NOT use the .joblib heads as a
replacement for the production decision. It evaluates an already-produced CSV
(e.g. data/training_batch.csv) and reconstructs left/right hip routing from the
same classify_study() logic used by the production adapter.

Typical usage from the repository root:
    python artifacts/evaluate_production.py \
      --predictions data/training_batch.csv \
      --manifest artifacts/canonical_manifest.json \
      --dicom-zip data/<training_zip>.zip

Outputs:
    artifacts/production_evaluation.md
    artifacts/production_criterion_metrics.csv
    artifacts/production_area_metrics.csv
    artifacts/production_evaluation.json
    artifacts/production_routing.csv
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import warnings
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import beta

# Import project code, not copied model logic.
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.dexa_baseline import classify_study

try:
    import pydicom
except ImportError:
    pydicom = None


@dataclass(frozen=True)
class ImageRecord:
    study_uid: str
    image_uid: str
    pixels: np.ndarray


CRITERIA = (
    ("spine_position", "spine", "Некорректная укладка"),
    ("spine_axis", "spine", "Не выравнена ось позвоночника"),
    ("spine_artifact", "spine", "Присутствуют посторонние предметы"),
    ("right_posrot", "femur_right", "Некорректная укладка"),
    ("right_roi", "femur_right", "Некорректная область интереса"),
    ("left_posrot", "femur_left", "Некорректная укладка"),
    ("left_roi", "femur_left", "Некорректная область интереса"),
)
CRITERION_MAP = {x[0]: x for x in CRITERIA}

AREA_CRITERIA = {
    "SPINE": ("spine_position", "spine_axis", "spine_artifact"),
    "HIP_RIGHT": ("right_posrot", "right_roi"),
    "HIP_LEFT": ("left_posrot", "left_roi"),
    "HIP": ("right_posrot", "right_roi", "left_posrot", "left_roi"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--predictions", type=Path, required=True, help="Existing production CSV, e.g. data/training_batch.csv")
    p.add_argument("--manifest", type=Path, default=ROOT / "artifacts" / "canonical_manifest.json")
    p.add_argument("--dicom-zip", type=Path, required=False, help="Optional labelled training ZIP used to reconstruct routing when --routing-csv is not supplied")
    p.add_argument("--routing-csv", type=Path, default=None, help="Precomputed current routing CSV with study_uid/image_uid/route")
    p.add_argument("--bootstrap", type=int, default=4000, help="Bootstrap replicates for 95%% CIs")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", type=Path, default=ROOT / "artifacts")
    return p.parse_args()


def load_manifest(path: Path) -> dict[str, dict[str, int | None]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {study["study_uid"]: study["labels"] for study in data["studies"]}


def _as_text(value: object) -> str:
    return str(value or "").strip()


def load_predictions(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).fillna({"violation_type": "", "findings": ""})
    required = {"study_uid", "image_uid", "quality_class", "violation_type"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Predictions CSV is missing columns: {', '.join(missing)}")
    return df


def _read_pixels(ds: pydicom.dataset.FileDataset) -> np.ndarray:
    pixels = np.asarray(ds.pixel_array, dtype=np.float32)
    if pixels.ndim > 2:
        # The public organizer data uses single-frame images. Keep the same
        # behavior as production for a frame if a multi-frame file appears.
        pixels = pixels[0]
    if pixels.ndim != 2:
        raise ValueError(f"Unsupported pixel shape {pixels.shape}")
    return pixels


def reconstruct_routing(dicom_zip: Path) -> pd.DataFrame:
    """Reconstruct the route for every output image with current production router."""
    if pydicom is None:
        raise RuntimeError("pydicom is required when --routing-csv is not supplied")
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    with zipfile.ZipFile(dicom_zip) as archive:
        names = sorted(name for name in archive.namelist() if name.lower().endswith(".dcm"))
        for name in names:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid value for VR UI")
                ds = pydicom.dcmread(io.BytesIO(archive.read(name)), force=False)
            study_uid = _as_text(getattr(ds, "StudyInstanceUID", ""))
            image_uid = _as_text(getattr(ds, "SOPInstanceUID", ""))
            if not study_uid or not image_uid:
                raise ValueError(f"Missing StudyInstanceUID/SOPInstanceUID in {name}")
            groups[study_uid].append(ImageRecord(study_uid, image_uid, _read_pixels(ds)))

    rows: list[dict[str, object]] = []
    for study_uid, images in sorted(groups.items()):
        # Match DexaBaselineAdapter's pixel deduplication before routing.
        unique: list[ImageRecord] = []
        digest_to_index: dict[bytes, int] = {}
        expanded: list[tuple[ImageRecord, int]] = []
        for image in images:
            digest = __import__("hashlib").md5(np.ascontiguousarray(image.pixels).tobytes()).digest()
            if digest not in digest_to_index:
                digest_to_index[digest] = len(unique)
                unique.append(image)
            expanded.append((image, digest_to_index[digest]))
        routes = classify_study([item.pixels for item in unique])
        by_index = {route.image_index: route for route in routes}
        for image, unique_index in expanded:
            route = by_index.get(unique_index)
            if route is None:
                raise RuntimeError(f"No route for {study_uid}/{image.image_uid}")
            rows.append(
                {
                    "study_uid": study_uid,
                    "image_uid": image.image_uid,
                    "route": route.region,
                    "route_index": route.image_index,
                    "side_shift": route.side_shift,
                    "symmetry": route.symmetry,
                    "ratio": route.ratio,
                }
            )
    return pd.DataFrame(rows)


def parse_violation_type(value: object) -> set[str]:
    return {item.strip() for item in _as_text(value).split(";") if item.strip()}


def study_prediction_flag(predictions: pd.DataFrame, study_uid: str, route: str, violation: str) -> int:
    rows = predictions[(predictions["study_uid"] == study_uid) & (predictions["route"] == route)]
    return int(any(violation in parse_violation_type(v) for v in rows["violation_type"]))


def metrics(y_true: Iterable[int], y_pred: Iterable[int]) -> dict[str, float | int]:
    y = np.asarray(list(y_true), dtype=int)
    pred = np.asarray(list(y_pred), dtype=int)
    tp = int(((y == 1) & (pred == 1)).sum())
    tn = int(((y == 0) & (pred == 0)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    sensitivity = tp / (tp + fn) if tp + fn else float("nan")
    specificity = tn / (tn + fp) if tn + fp else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return {
        "N": int(len(y)),
        "positive": int(y.sum()),
        "pred_positive": int(pred.sum()),
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "F1": f1,
        "Sensitivity": sensitivity,
        "Specificity": specificity,
    }


def bootstrap_ci(y_true: Iterable[int], y_pred: Iterable[int], B: int, seed: int) -> dict[str, tuple[float, float]]:
    y = np.asarray(list(y_true), dtype=int)
    pred = np.asarray(list(y_pred), dtype=int)
    if len(y) < 2 or B <= 0:
        return {"F1": (float("nan"), float("nan")), "Sensitivity": (float("nan"), float("nan")), "Specificity": (float("nan"), float("nan"))}
    rng = np.random.default_rng(seed)
    f1_values: list[float] = []
    sens_values: list[float] = []
    spec_values: list[float] = []
    for _ in range(B):
        idx = rng.integers(0, len(y), len(y))
        yy = y[idx]
        pp = pred[idx]
        m = metrics(yy, pp)
        if np.isfinite(m["Sensitivity"]):
            sens_values.append(float(m["Sensitivity"]))
        if np.isfinite(m["Specificity"]):
            spec_values.append(float(m["Specificity"]))
        f1_values.append(float(m["F1"]))

    def pct(values: list[float]) -> tuple[float, float]:
        if not values:
            return (float("nan"), float("nan"))
        return (float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975)))

    return {"F1": pct(f1_values), "Sensitivity": pct(sens_values), "Specificity": pct(spec_values)}


def wilson_ci(x: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def build_criterion_table(predictions: pd.DataFrame, labels: dict[str, dict[str, int | None]], B: int, seed: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for study_uid, study_labels in labels.items():
        for criterion, route, violation in CRITERIA:
            truth = study_labels.get(criterion)
            if truth is None:
                continue
            pred = study_prediction_flag(predictions, study_uid, route, violation)
            rows.append({"study_uid": study_uid, "criterion": criterion, "y": int(truth), "pred": int(pred)})
    raw = pd.DataFrame(rows)
    result: list[dict[str, object]] = []
    for criterion, group in raw.groupby("criterion", sort=True):
        m = metrics(group["y"], group["pred"])
        ci = bootstrap_ci(group["y"], group["pred"], B=B, seed=seed)
        result.append(
            {
                "criterion": criterion,
                **m,
                "F1_CI_low": ci["F1"][0], "F1_CI_high": ci["F1"][1],
                "Sensitivity_CI_low": ci["Sensitivity"][0], "Sensitivity_CI_high": ci["Sensitivity"][1],
                "Specificity_CI_low": ci["Specificity"][0], "Specificity_CI_high": ci["Specificity"][1],
                "warning": ("few_positive_cases" if int(m["positive"]) < 10 else ""),
            }
        )
    return pd.DataFrame(result).set_index("criterion")


def build_area_table(predictions: pd.DataFrame, labels: dict[str, dict[str, int | None]], B: int, seed: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for area, criteria in AREA_CRITERIA.items():
        y_all: list[int] = []
        p_all: list[int] = []
        for study_uid, study_labels in labels.items():
            available = [study_labels.get(c) for c in criteria if study_labels.get(c) is not None]
            if not available:
                continue
            y_all.append(int(any(v == 1 for v in available)))
            p_all.append(
                int(any(
                    study_prediction_flag(predictions, study_uid, CRITERION_MAP[c][1], CRITERION_MAP[c][2])
                    for c in criteria
                    if study_labels.get(c) is not None
                ))
            )
        m = metrics(y_all, p_all)
        ci = bootstrap_ci(y_all, p_all, B=B, seed=seed)
        rows.append({
            "area": area,
            **m,
            "F1_CI_low": ci["F1"][0], "F1_CI_high": ci["F1"][1],
            "Sensitivity_CI_low": ci["Sensitivity"][0], "Sensitivity_CI_high": ci["Sensitivity"][1],
            "Specificity_CI_low": ci["Specificity"][0], "Specificity_CI_high": ci["Specificity"][1],
        })
    return pd.DataFrame(rows).set_index("area")


def overall_quality_screen(predictions: pd.DataFrame, labels: dict[str, dict[str, int | None]], B: int, seed: int) -> tuple[dict[str, object], dict[str, tuple[float, float]]]:
    study_pred = predictions.groupby("study_uid")["quality_class"].max().to_dict()
    y: list[int] = []
    p: list[int] = []
    for study_uid, study_labels in labels.items():
        available = [value for value in study_labels.values() if value is not None]
        if not available:
            continue
        y.append(int(any(value == 1 for value in available)))
        p.append(int(study_pred.get(study_uid, 0)))
    return metrics(y, p), bootstrap_ci(y, p, B=B, seed=seed)


def fmt(x: object) -> str:
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def render_markdown(criterion: pd.DataFrame, area: pd.DataFrame, overall: dict[str, object], overall_ci: dict[str, tuple[float, float]], route: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Production evaluation — current frozen output")
    lines.append("")
    lines.append("This report evaluates the already-produced production CSV against the canonical study labels. It does not retrain models.")
    lines.append("")
    lines.append("## Overall quality screen")
    lines.append("")
    lines.append(f"**N={overall['N']} studies**; expert-positive={overall['positive']}; predicted-positive={overall['pred_positive']}.")
    lines.append("")
    lines.append(f"- F1: **{fmt(overall['F1'])}** (95% bootstrap CI {fmt(overall_ci['F1'][0])}–{fmt(overall_ci['F1'][1])})")
    lines.append(f"- Sensitivity: **{fmt(overall['Sensitivity'])}** (95% bootstrap CI {fmt(overall_ci['Sensitivity'][0])}–{fmt(overall_ci['Sensitivity'][1])})")
    lines.append(f"- Specificity: **{fmt(overall['Specificity'])}** (95% bootstrap CI {fmt(overall_ci['Specificity'][0])}–{fmt(overall_ci['Specificity'][1])})")
    lines.append("")
    lines.append("## Criterion-level")
    lines.append("")
    lines.append("| Criterion | N | Pos | Pred+ | TP | FP | FN | F1 | Sensitivity | Specificity | Note |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for idx, row in criterion.iterrows():
        note = "few positives" if row.get("warning", "") == "few_positive_cases" else ""
        lines.append(f"| {idx} | {int(row['N'])} | {int(row['positive'])} | {int(row['pred_positive'])} | {int(row['TP'])} | {int(row['FP'])} | {int(row['FN'])} | {fmt(row['F1'])} | {fmt(row['Sensitivity'])} | {fmt(row['Specificity'])} | {note} |")
    lines.append("")
    lines.append("95% bootstrap CIs are stored in `production_criterion_metrics.csv`. For rare criteria with very few positives, intervals are expected to be wide and should not be over-interpreted.")
    lines.append("")
    lines.append("## Area-level screening")
    lines.append("")
    lines.append("| Area | N | Pos | Pred+ | F1 | Sensitivity | Specificity |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for idx, row in area.iterrows():
        lines.append(f"| {idx} | {int(row['N'])} | {int(row['positive'])} | {int(row['pred_positive'])} | {fmt(row['F1'])} | {fmt(row['Sensitivity'])} | {fmt(row['Specificity'])} |")
    lines.append("")
    lines.append("## Routing sanity check")
    lines.append("")
    for route_name, count in route["route"].value_counts().items():
        lines.append(f"- {route_name}: {int(count)} images")
    lines.append(f"- Total routed images: {len(route)} across {route['study_uid'].nunique()} studies")
    lines.append("")
    lines.append("## Interpretation notes")
    lines.append("")
    lines.append("- This is a study-level aggregation of the image-level production CSV: a study is predicted positive when any relevant image is predicted positive.")
    lines.append("- Left/right hip criteria are evaluated after reconstructing the same current `classify_study()` route from the DICOM images, because the CSV's `anatomical_region` field intentionally does not encode side.")
    lines.append("- These are development-set measurements; they are not independent closed-test performance.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    labels = load_manifest(args.manifest)
    predictions = load_predictions(args.predictions)
    if args.routing_csv is not None:
        route = pd.read_csv(args.routing_csv)
        required_route = {"study_uid", "image_uid", "route"}
        missing_route = sorted(required_route.difference(route.columns))
        if missing_route:
            raise ValueError(f"Routing CSV is missing columns: {", ".join(missing_route)}")
    else:
        if args.dicom_zip is None:
            raise ValueError("provide --routing-csv or --dicom-zip")
        route = reconstruct_routing(args.dicom_zip)
    merged = predictions.merge(route[["study_uid", "image_uid", "route"]], on=["study_uid", "image_uid"], how="left")
    if merged["route"].isna().any():
        missing = int(merged["route"].isna().sum())
        raise RuntimeError(f"Could not reconstruct routing for {missing} prediction rows")

    # Criterion table uses a fixed seed per criterion by design in the current script.
    criterion = build_criterion_table(merged, labels, B=args.bootstrap, seed=args.seed)
    area = build_area_table(merged, labels, B=args.bootstrap, seed=args.seed)
    overall, overall_ci = overall_quality_screen(merged, labels, B=args.bootstrap, seed=args.seed)

    criterion.to_csv(args.out_dir / "production_criterion_metrics.csv")
    area.to_csv(args.out_dir / "production_area_metrics.csv")
    route.to_csv(args.out_dir / "production_routing.csv", index=False)
    report = render_markdown(criterion, area, overall, overall_ci, route)
    (args.out_dir / "production_evaluation.md").write_text(report, encoding="utf-8")

    payload = {
        "overall_quality_screen": {**overall, "CI": overall_ci},
        "criteria": criterion.reset_index().to_dict(orient="records"),
        "areas": area.reset_index().to_dict(orient="records"),
        "routing": route["route"].value_counts().to_dict(),
        "notes": [
            "study-level aggregation from image-level production CSV",
            "left/right reconstructed from current classify_study()",
            "development labels, not independent closed-test performance",
        ],
    }
    (args.out_dir / "production_evaluation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    print(report)
    print(f"Saved reports under {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
