# DXA V5 status

## Applied organiser clarifications

The official V2 clarification has been incorporated into the API/output contract:

- pixel geometry: X=0.60 mm/px, Y=1.05 mm/px;
- one device variant in the dataset;
- closed Russian `violation_type` vocabulary;
- semicolon-separated multiple violations and empty value when there is no violation;
- `quality_prob` in [0,1];
- `quality_class` as integer 0/1;
- `anatomical_region` exposes only spine vs proximal femur; laterality is not part of this field.

## ML benchmark

A first study-grouped criterion benchmark has been trained and evaluated. The detailed metrics are in `docs/ML_BASELINE_RESULTS.md`, with fitted benchmark artifacts in `artifacts/models/`.

This benchmark is deliberately not treated as the final model. The weakest criteria are spine positioning/artifact and left ROI, while the dataset has very few positive ROI labels. The next model iteration should focus on anatomy localization and physical geometry.
