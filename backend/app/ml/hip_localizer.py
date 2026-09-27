"""Explainable proximal-femur localization for DXA.

The localizer is intentionally conservative and is not presented as a clinical
segmentation model.  It uses a femoral-shaft-first geometry cue: the proximal
femur is anchored to a long, vertically oriented shaft rather than selected
from a generic bright connected component.  This reduces confusion with the
pelvis and with superior/medial bone structures that can be present in the hip
view.

The TЗ ROI criterion is represented separately from the candidate anatomical
box.  The criterion asks whether the image provides at least 30 mm of
visualization above and below the area of interest and at least 20 mm toward
the lateral image edge (right edge for the right hip, left edge for the left
hip).  We therefore report *available* physical margins instead of expanding
the bone box by an arbitrary number of pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np

from app.ml.dexa_baseline import _crop_black_edge_mask, _normalize, side_shift
from app.ml.profile import PIXEL_X_MM, PIXEL_Y_MM


@dataclass(frozen=True, slots=True)
class HipLocalization:
    side: str
    bone_bbox: tuple[float, float, float, float]
    roi_bbox: tuple[float, float, float, float]
    bone_center: tuple[float, float]
    roi_margin_px: tuple[float, float, float, float]
    confidence: float
    physical_margin_mm: tuple[float, float, float, float]
    shaft_bbox: tuple[float, float, float, float]
    shaft_score: float


def _candidate_mask(x: np.ndarray) -> np.ndarray:
    """High-density bone mask with a vertical closing operation."""
    h, w = x.shape
    mask = _crop_black_edge_mask(x)
    finite = x[mask & np.isfinite(x)]
    if finite.size == 0:
        return np.zeros_like(x, dtype=np.uint8)
    threshold = float(np.percentile(finite, 86.0))
    m = ((x >= threshold) & mask).astype(np.uint8)
    kx = max(3, int(round(0.020 * w)) // 2 * 2 + 1)
    ky = max(7, int(round(0.045 * h)) // 2 * 2 + 1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((ky, kx), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return m


def _shaft_candidate(mask: np.ndarray, image: np.ndarray, side: str):
    """Find a long, side-consistent femoral-shaft candidate."""
    h, w = mask.shape
    y0 = int(0.42 * h)
    lower = mask[y0:]
    # Strengthen long vertical cortex/shaft fragments without requiring a single
    # connected component from shaft to the proximal head.
    m = cv2.morphologyEx(lower, cv2.MORPH_CLOSE, np.ones((21, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 3), np.uint8))
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(m, 8)
    target = 0.62 if side == "right" else 0.38
    best = None
    for i in range(1, n):
        xs, ys, bw, bh, area = stats[i]
        cx, cy = centroids[i]
        if bh < 0.20 * h or area < max(20, 0.002 * h * w):
            continue
        side_score = float(np.exp(-((cx / w - target) / 0.23) ** 2))
        vertical = float(np.clip(bh / (0.55 * h), 0.0, 1.0))
        narrow = float(1.0 - np.clip((bw / w - 0.22) / 0.35, 0.0, 1.0))
        xa = max(0, int(cx - 0.035 * w))
        xb = min(w, int(cx + 0.035 * w))
        yy0 = max(y0, y0 + ys)
        yy1 = min(h, y0 + ys + bh)
        if yy1 > yy0 and xb > xa:
            local = image[yy0:yy1, xa:xb]
            support = float((local >= np.percentile(local, 65)).mean())
        else:
            support = 0.0

        # A true femoral shaft should have a plausible *proximal continuation*
        # into the neck/head region.  This is deliberately local: we do not
        # reward a large bright pelvic mass merely because it is connected to
        # the shaft by morphology.
        up0 = max(0, int(y0 + ys - 0.22 * h))
        up1 = max(up0 + 1, int(y0 + ys))
        band_w = max(5, int(0.055 * w))
        ux0 = max(0, int(cx - band_w)); ux1 = min(w, int(cx + band_w))
        up = image[up0:up1, ux0:ux1]
        if up.size:
            q = float(np.percentile(up, 70.0))
            rows = (up >= q).mean(axis=1)
            # longest local run of rows with cortical/neck support
            run = best_run = 0
            for rv in rows:
                run = run + 1 if rv >= 0.18 else 0
                best_run = max(best_run, run)
            proximal_support = float(np.clip(best_run / max(6.0, 0.10 * h), 0.0, 1.0))
        else:
            proximal_support = 0.0

        score = (0.34 * side_score + 0.28 * vertical + 0.12 * narrow +
                 0.08 * support + 0.18 * proximal_support)
        candidate = (score, cx, y0 + ys, bw, bh)
        if best is None or score > best[0]:
            best = candidate
    return best


def _proximal_box(mask: np.ndarray, image: np.ndarray, shaft, side: str):
    """Construct a conservative proximal-femur box anchored to the shaft."""
    h, w = mask.shape
    _, cx, shaft_top, shaft_bw, shaft_bh = shaft
    band = max(6, int(0.09 * w))
    xa = max(0, int(cx - band))
    xb = min(w, int(cx + band))
    col = image[:, xa:xb].mean(axis=1)
    # Look above the shaft for the proximal expansion, but do not jump through a
    # large central pelvic region. A short gap is allowed for cortical breaks.
    local_top = max(0, int(shaft_top - 0.42 * h))
    local_bottom = min(h, int(shaft_top + 0.12 * h))
    ref = image[local_top:local_bottom, xa:xb]
    threshold = float(np.percentile(ref, 72.0)) if ref.size else 0.7
    sig = (col >= threshold).astype(np.uint8)
    sig = cv2.morphologyEx(sig[:, None], cv2.MORPH_CLOSE, np.ones((11, 1), np.uint8)).ravel()
    inds = np.where(sig[local_top : shaft_top + 1] > 0)[0]
    prox_top = local_top + int(inds[0]) if inds.size else max(0, int(shaft_top - 0.12 * h))
    # Do not allow a single bright pelvic column to drag the box to the very top
    # of the image; the proximal femur should remain close to the shaft entry.
    prox_top = max(prox_top, int(shaft_top - 0.30 * h))

    # Width is deliberately modest: it captures head/neck/trochanter context,
    # while avoiding a broad pelvis bbox.
    # Use a fixed anatomical context width rather than the morphology component
    # width: the latter can become very broad when pelvis and shaft cortex touch.
    half_w = 0.18 * w
    bx = max(0.0, float(cx - half_w))
    bx1 = min(float(w), float(cx + half_w))
    y0 = max(0.0, float(prox_top) - 0.02 * h)
    y1 = min(float(h), float(shaft_top + 0.18 * h))
    if y1 <= y0:
        y1 = min(float(h), y0 + 0.20 * h)
    return bx / w, y0 / h, (bx1 - bx) / w, (y1 - y0) / h


def localize_hip(image: np.ndarray, side: str | None = None) -> HipLocalization:
    x = _normalize(image)
    h, w = x.shape
    if side not in {"left", "right"}:
        side = "right" if side_shift(x) >= 0 else "left"
    mask = _candidate_mask(x)
    shaft = _shaft_candidate(mask, x, side)
    if shaft is None:
        # Safe fallback: keep the old broad candidate only when no shaft evidence
        # exists, and expose low confidence so downstream code can abstain.
        bx, by, bw, bh, conf = 0.25, 0.20, 0.50, 0.60, 0.05
        shaft_bbox = (bx, 0.42, bw, 0.58)
        shaft_score = 0.0
    else:
        shaft_score, scx, sty, sbw, sbh = shaft
        bx, by, bw, bh = _proximal_box(mask, x, shaft, side)
        conf = float(np.clip(0.35 + 0.65 * shaft_score, 0.0, 1.0))
        shaft_bbox = (max(0.0, (scx - sbw / 2) / w), sty / h, sbw / w, sbh / h)

    cx, cy = bx + bw / 2.0, by + bh / 2.0

    # IMPORTANT: the TЗ requires available visualization margins around the
    # anatomical area. It does not ask us to enlarge the bbox by 2/3 cm.
    left_mm = bx * w * PIXEL_X_MM
    right_mm = (1.0 - (bx + bw)) * w * PIXEL_X_MM
    top_mm = by * h * PIXEL_Y_MM
    bottom_mm = (1.0 - (by + bh)) * h * PIXEL_Y_MM
    lateral_mm = right_mm if side == "right" else left_mm

    # A candidate visualization window is retained for overlays only. It is not
    # itself the quality decision.
    margin_x = 20.0 / PIXEL_X_MM
    margin_y = 30.0 / PIXEL_Y_MM
    x0 = max(0.0, bx * w - (margin_x if side == "left" else 0.0))
    x1 = min(float(w), (bx + bw) * w + (margin_x if side == "right" else 0.0))
    y0 = max(0.0, by * h - margin_y)
    y1 = min(float(h), (by + bh) * h + margin_y)
    roi = (x0 / w, y0 / h, max(0.0, (x1 - x0) / w), max(0.0, (y1 - y0) / h))

    physical = (left_mm, top_mm, right_mm, bottom_mm)
    roi_px = (left_mm / PIXEL_X_MM, top_mm / PIXEL_Y_MM,
              right_mm / PIXEL_X_MM, bottom_mm / PIXEL_Y_MM)
    return HipLocalization(
        side=side,
        bone_bbox=(bx, by, bw, bh),
        roi_bbox=roi,
        bone_center=(cx, cy),
        roi_margin_px=roi_px,
        confidence=conf,
        physical_margin_mm=physical,
        shaft_bbox=shaft_bbox,
        shaft_score=float(shaft_score),
    )
