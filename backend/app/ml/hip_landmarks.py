"""Experimental candidate landmarks for proximal-femur visualization.

These are geometry candidates, not clinical landmarks and are not used by the
production quality decision in V6.8.2. They are deliberately exposed with
confidence so a later version can validate them against expert landmarks.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import cv2
import numpy as np
from app.ml.dexa_baseline import _normalize
from app.ml.hip_localizer import _candidate_mask, _shaft_candidate, localize_hip

@dataclass(frozen=True, slots=True)
class HipLandmarkCandidates:
    side: str
    shaft_center: tuple[float, float]
    shaft_axis: tuple[float, float]
    femoral_head: tuple[float, float] | None
    femoral_head_radius: float
    neck_center: tuple[float, float] | None
    greater_trochanter_proxy: tuple[float, float] | None
    confidence: float
    method: str = "shaft_distance_transform_v1"

    def to_dict(self):
        return asdict(self)


def detect_hip_landmarks(image: np.ndarray, side: str) -> HipLandmarkCandidates:
    x = _normalize(image)
    h, w = x.shape
    loc = localize_hip(x, side)
    shaft = _shaft_candidate(_candidate_mask(x), x, side)
    if shaft is None:
        return HipLandmarkCandidates(side, loc.bone_center, (0.0, -1.0), None, 0.0, None, None, 0.05)

    score, sx, sty, sbw, sbh = shaft
    # Canonical frame: lateral direction is +x for both sides.
    z = x if side == "right" else np.fliplr(x)
    csx = sx if side == "right" else w - sx
    x0 = max(0, int(csx - .24*w)); x1 = min(w, int(csx + .30*w))
    y0 = max(0, int(sty - .32*h)); y1 = min(h, int(sty + .20*h))
    crop = z[y0:y1, x0:x1]
    H, W = crop.shape
    if crop.size < 500:
        return HipLandmarkCandidates(side, (csx/w, sty/h), (0.0,-1.0), None, 0.0, None, None, float(.35+.65*score))

    q = float(np.percentile(crop, 78.0))
    mask = (crop >= q).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))

    # Head candidate: center of largest local distance-transform radius.
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    yy, xx = np.indices(dt.shape)
    valid = (yy < .72*H) & (xx > .10*W) & (xx < .92*W)
    d = dt.copy(); d[~valid] = 0
    _, radius, _, (hx, hy) = cv2.minMaxLoc(d)
    if (not np.isfinite(radius)) or radius <= 2 or radius > 0.20*W:
        radius = 0.0
    head = None if radius <= 2 else ((x0+hx)/w, (y0+hy)/h)

    # Row-width profile: broad proximal expansion -> local waist -> shaft.
    rows=[]
    for y in range(int(.12*H), int(.88*H)):
        xs=np.where(mask[y]>0)[0]
        if xs.size >= 3:
            rows.append((y, xs.min(), xs.max()))
    neck=None; tro=None
    if rows:
        widths=np.array([b-a+1 for _,a,b in rows], dtype=float)
        imax=int(np.argmax(widths))
        tail=np.arange(imax+1,len(rows))
        if tail.size:
            j=int(tail[np.argmin(widths[tail])]); yy0,a,b=rows[j]
            neck=((x0+(a+b)/2)/w, (y0+yy0)/h)
        # Lateral-most bright extent below head is a conservative trochanter proxy.
        k0=max(0, int(.25*len(rows))); k1=max(k0+1, int(.82*len(rows)))
        rr=rows[k0:k1]
        if rr:
            yy0,a,b=max(rr, key=lambda t:t[2])
            tro=((x0+b)/w, (y0+yy0)/h)

    confidence=float(np.clip(.35 + .45*score + .20*np.clip(radius/(.10*w),0,1),0,1))
    # Axis points from shaft center toward its distal direction (down image).
    shaft_center=(csx/w, sty/h)
    axis=(0.0, 1.0)
    return HipLandmarkCandidates(side, shaft_center, axis, head, float(radius/w), neck, tro, confidence)
