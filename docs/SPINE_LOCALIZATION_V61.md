# V6.1 — spine anatomical localization

## What changed

The region router no longer selects the spine image in a standard 3-image DXA study by the minimum top/bottom intensity ratio alone.

For the common `spine + left hip + right hip` layout it now uses the anatomical side-shift pattern:

- spine: smallest `abs(side_shift)`;
- left hip: most negative `side_shift`;
- right hip: most positive `side_shift`.

If the expected left/right separation is absent, the previous ratio-based fallback remains active.

## Why

On the 72 studies whose non-null labels indicate all three regions, the three-image pattern had:

- no case with the middle/near-zero side shift outside the expected spine range;
- `abs(side_shift)` for the selected spine image: max ≈ 0.083;
- single-image spine references: median `abs(side_shift)` ≈ 0.019.

This is a routing sanity check, not an image-level ground-truth accuracy measurement, because the spreadsheet labels describe study-level anatomical regions and contain known incomplete-label cases.

## Spine localizer

`backend/app/ml/spine_localizer.py` adds an explainable candidate localizer:

1. robust percentile normalization;
2. central-band restriction;
3. Gaussian smoothing / bright-bone emphasis;
4. dynamic-programming path with a smoothness constraint;
5. normalized anatomical corridor (`bbox`);
6. centerline sampled to 32 points;
7. image-axis and physical-axis angle estimates.

The localization geometry is **not yet used as the final validated quality decision**. The existing criterion heads remain the benchmark baseline until anatomy+geometry is evaluated leakage-safely.

## Known data caveat

Two studies have image content indicating additional hip regions while the spreadsheet's non-null labels do not list those regions. These are retained as known label anomalies rather than counted as routing errors.
