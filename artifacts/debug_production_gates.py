"""Debug why specific production violation types never fire.

Current targets:
  * SPINE_ARTIFACT
  * HIP_POSITION_ROTATION

No model is trained. The script inspects the actual code path, current feature
ranges, and the stored OOF benchmark predictions/models.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.ml.dexa_baseline import _load_quality_models


def load_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", type=Path, default=ROOT / "data" / "training_batch.csv")
    return p.parse_args()


def main() -> int:
    args = load_args()
    settings = Settings()
    models = _load_quality_models()
    print("=== SPINE_ARTIFACT ===")
    print(f"ENABLE_EXPERIMENTAL_BENCHMARK_HEADS = {settings.enable_experimental_benchmark_heads}")
    if not settings.enable_experimental_benchmark_heads:
        print("Production `_criterion_prob()` returns None for benchmark heads.")
        print("Therefore the current production `evaluate_quality()` cannot append SPINE_ARTIFACT.")
    print("Stored calibrator status:")
    cal = json.loads((ROOT / "artifacts" / "models" / "quality_calibrators.json").read_text(encoding="utf-8"))
    print({k: bool(v.get("enabled")) for k, v in cal.items()})
    print("OOF head evidence:")
    oof = json.loads((ROOT / "artifacts" / "v68_oof" / "oof_predictions.json").read_text(encoding="utf-8"))
    for crit in ("spine_artifact", "right_posrot", "left_posrot"):
        y = np.asarray(oof[crit]["y"], dtype=int)
        p = np.asarray(oof[crit]["p"], dtype=float)
        pred = p >= 0.5
        tp = int(((y == 1) & pred).sum()); tn = int(((y == 0) & ~pred).sum())
        fp = int(((y == 0) & pred).sum()); fn = int(((y == 1) & ~pred).sum())
        sens = tp / (tp + fn) if tp + fn else float("nan")
        spec = tn / (tn + fp) if tn + fp else float("nan")
        print(f"  {crit}: OOF AUC is documented in docs/ML_BASELINE_RESULTS.md; @0.5 TP={tp} FP={fp} FN={fn} TN={tn}; sensitivity={sens:.3f}; specificity={spec:.3f}")

    print("\n=== HIP_POSITION_ROTATION ===")
    print("The deterministic production trigger is any of:")
    print("  localizer confidence < 0.20")
    print("  bbox width < 0.25")
    print("  bbox height < 0.65")
    print("  |bbox center_x - 0.5| > 0.28")
    print("  benchmark p_pos >= 0.50 (only when experimental heads are enabled)")
    print("  |side_shift| < 0.015")
    print("The current CSV contains only the following Russian violation label for this code path when it actually fires:")
    pred = pd.read_csv(args.predictions).fillna({"violation_type": ""})
    counts = pred[pred["violation_type"].astype(str).str.contains("Некорректная укладка", regex=False)]["study_uid"].nunique()
    rows = pred[pred["violation_type"].astype(str).str.contains("Некорректная укладка", regex=False)]
    print(f"  {len(rows)} image rows / {counts} studies")
    print("  The route-aware production evaluation separates those image rows into spine vs left/right hip.")
    print("\nConclusion for the frozen V6.9 behavior: hip rotation is not directly measured by a rotation-specific anatomical feature; with benchmark heads disabled, the model cannot use the stored posrot classifiers. The surviving deterministic fallback is too weak to detect the expert-labeled rotation cases consistently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
