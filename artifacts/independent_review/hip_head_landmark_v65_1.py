"""Experimental femoral-head landmark cue via Hough circle detection, used to
anchor the proximal-femur box more robustly than a pure column-brightness
threshold. Hypothesis: the femoral head is the only strongly circular bright
structure near the shaft's proximal end; anchoring on it should prevent the
box from drifting into the iliac wing / acetabular rim when the brightness
threshold used by _proximal_box "leaks" upward through a bright pelvic
region.
"""
import sys, json
from pathlib import Path
import numpy as np
import cv2
sys.path.insert(0, '/home/claude/work/dxa_v65/v64/backend')
from app.ml.dexa_baseline import _normalize
from app.ml.hip_localizer import localize_hip, _candidate_mask, _shaft_candidate, _proximal_box

def find_femoral_head(image, shaft, side):
    """Look for a circular bright blob above the shaft top, biased toward the
    shaft's own x-position (the head sits directly above/slightly medial to
    the shaft, not laterally over the wing)."""
    x = _normalize(image)
    h, w = x.shape
    if shaft is None:
        return None
    _, cx, shaft_top, sbw, sbh = shaft
    # Search window: above the shaft, modest width around shaft x.
    y0 = max(0, int(shaft_top - 0.30 * h))
    y1 = min(h, int(shaft_top + 0.06 * h))
    x0 = max(0, int(cx - 0.20 * w))
    x1 = min(w, int(cx + 0.20 * w))
    win = x[y0:y1, x0:x1]
    if win.size == 0:
        return None
    win8 = (np.clip(win, 0, 1) * 255).astype(np.uint8)
    win8 = cv2.GaussianBlur(win8, (5, 5), 0)
    min_r = max(4, int(0.035 * w))
    max_r = max(min_r + 2, int(0.09 * w))
    circles = cv2.HoughCircles(
        win8, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max(8, int(0.06 * w)),
        param1=80, param2=18, minRadius=min_r, maxRadius=max_r,
    )
    if circles is None:
        return None
    best = None
    for cxx, cyy, r in circles[0]:
        gx, gy = x0 + cxx, y0 + cyy
        # Prefer circles close to (above) the shaft top and near shaft x.
        dist_score = float(np.exp(-(((gx - cx) / (0.15 * w)) ** 2)))
        height_score = float(np.exp(-(((gy - (shaft_top - 0.10 * h)) / (0.18 * h)) ** 2)))
        score = dist_score * height_score
        if best is None or score > best[0]:
            best = (score, gx, gy, r)
    return best  # (score, x, y, r) in pixel coords


def localize_hip_v2(image, side):
    """Baseline localizer, refined by clamping the proximal box top using the
    detected femoral-head circle when available and consistent."""
    base = localize_hip(image, side)
    x = _normalize(image)
    h, w = x.shape
    mask = _candidate_mask(x)
    shaft = _shaft_candidate(mask, x, side)
    head = find_femoral_head(image, shaft, side)
    info = dict(head_found=head is not None)
    if shaft is None or head is None:
        return base, info
    score, hx, hy, r = head
    info.update(head_score=score, head_xy=(hx / w, hy / h), head_r=r / w)
    if score < 0.25:
        return base, info
    bx, by, bw, bh = base.bone_bbox
    # Clamp box top to the head circle (with small margin), preventing the
    # "jumps into iliac wing" failure where by is well above the head.
    head_top = max(0.0, (hy - 1.6 * r) / h)
    new_by = max(by, head_top) if head_top > by else by
    # only shrink (make box lower / smaller), never grow beyond original box,
    # to keep this a conservative refinement.
    if new_by > by:
        new_bh = (by + bh) - new_by
        if new_bh > 0.05:
            info['adjusted'] = True
            return base.__class__(
                side=base.side, bone_bbox=(bx, new_by, bw, new_bh), roi_bbox=base.roi_bbox,
                bone_center=(bx + bw/2, new_by + new_bh/2), roi_margin_px=base.roi_margin_px,
                confidence=base.confidence, physical_margin_mm=base.physical_margin_mm,
                shaft_bbox=base.shaft_bbox, shaft_score=base.shaft_score,
            ), info
    info['adjusted'] = False
    return base, info
