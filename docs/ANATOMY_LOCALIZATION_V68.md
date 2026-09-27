# V6.8 — anatomy localization payload

The API now exposes `anatomy_localization` per image when the production localizer can produce a candidate anatomy geometry.

This object is intended for visualization and audit. It is **not** a segmentation mask and must not be presented as a clinical defect contour.

## Spine
- `bbox`: normalized candidate lumbar corridor.
- `centerline`: normalized centerline points.
- `axis_degrees_physical`: physical-coordinate axis angle.
- `confidence`: localizer confidence.

## Hip
- `bbox`: normalized proximal-femur candidate box.
- `shaft_bbox`: normalized femoral-shaft candidate box.
- `side`: left/right internal anatomy side.
- `physical_margin_mm`: left/top/right/bottom available image margins around the candidate.
- `confidence`: localizer confidence.

The exported TЗ `anatomical_region` remains side-independent: `Проксимальный отдел бедра`.
The UI may use `side` for visualization, but it must not change the official output terminology.

No new clinical decision rule was introduced by this change.
