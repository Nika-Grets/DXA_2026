"""Lightweight, explainable spine anatomical localization for DXA.

This is an anatomical candidate localizer, not a clinical vertebral segmentation model.
It returns a smooth central path through the lumbar spine image plus an approximate axis.
The path is intentionally conservative and can be replaced by a trained landmark model
without changing the downstream quality interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan, degrees

import cv2
import numpy as np

from app.ml.dexa_baseline import _normalize
from app.ml.profile import PIXEL_X_MM, PIXEL_Y_MM


@dataclass(frozen=True, slots=True)
class SpineLocalization:
    bbox: tuple[float, float, float, float]
    centerline: tuple[tuple[float, float], ...]
    axis_degrees: float
    axis_degrees_physical: float
    confidence: float


def _smooth_path(image: np.ndarray) -> tuple[np.ndarray, float]:
    x = _normalize(image)
    h, w = x.shape

    # The lumbar column is expected near the image centre. Keeping a central band
    # suppresses ribs/arms without assuming an exact acquisition crop.
    x0 = int(0.35 * w)
    x1 = int(0.65 * w)
    z = cv2.GaussianBlur(x, (0, 0), sigmaX=1.2)
    z = np.power(np.clip(z, 0.0, 1.0), 2.0)
    z[: int(0.08 * h)] *= 0.5
    z[int(0.92 * h) :] *= 0.5
    z = cv2.GaussianBlur(z, (0, 0), sigmaX=1.5, sigmaY=3.0)
    z = z[:, x0:x1]

    n = z.shape[1]
    max_step = 3
    transition_penalty = 0.35
    dp = np.full((h, n), -1e9, dtype=np.float32)
    prev = np.zeros((h, n), dtype=np.int32)
    dp[0] = z[0]

    for y in range(1, h):
        for j in range(n):
            lo = max(0, j - max_step)
            hi = min(n, j + max_step + 1)
            js = np.arange(lo, hi)
            values = dp[y - 1, lo:hi] - transition_penalty * (js - j) ** 2
            k = int(np.argmax(values))
            dp[y, j] = z[y, j] + values[k]
            prev[y, j] = js[k]

    j = int(np.argmax(dp[-1]))
    path = np.empty(h, dtype=np.int32)
    path[-1] = j
    for y in range(h - 1, 0, -1):
        path[y - 1] = prev[y, path[y]]
    path = path + x0

    path_score = float(np.mean(z[np.arange(h), path - x0]))
    # Contrast of the selected path against the central-band background.
    central_mean = float(np.mean(z))
    confidence = float(np.clip(0.5 + 1.5 * (path_score - central_mean), 0.0, 1.0))
    return path, confidence


def localize_spine(image: np.ndarray) -> SpineLocalization:
    path, confidence = _smooth_path(image)
    h, w = image.shape[:2]
    y = np.arange(h, dtype=np.float32)

    # Ignore the extreme image margins when fitting the axis.
    keep = (y >= 0.10 * h) & (y <= 0.90 * h)
    yy = y[keep]
    xx = path[keep].astype(np.float32)
    slope = float(np.polyfit(yy, xx, 1)[0]) if len(xx) >= 3 else 0.0
    angle = abs(degrees(atan(slope)))
    physical_slope = slope * PIXEL_X_MM / PIXEL_Y_MM
    angle_physical = abs(degrees(atan(physical_slope)))

    # The bbox is a conservative anatomical corridor around the centerline.
    half_width = max(0.10 * w, 24.0)
    x_min = float(np.clip(np.min(path) - half_width, 0, w - 1) / w)
    x_max = float(np.clip(np.max(path) + half_width, 1, w) / w)
    y_min, y_max = 0.08, 0.92

    # Downsample the path for transport/visualization.
    idx = np.linspace(0, h - 1, min(32, h)).astype(int)
    centerline = tuple((float(path[i] / w), float(i / max(1, h - 1))) for i in idx)
    return SpineLocalization(
        bbox=(x_min, y_min, max(0.0, x_max - x_min), y_max - y_min),
        centerline=centerline,
        axis_degrees=float(angle),
        axis_degrees_physical=float(angle_physical),
        confidence=confidence,
    )
