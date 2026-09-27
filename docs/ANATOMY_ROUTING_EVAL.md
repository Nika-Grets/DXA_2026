# Anatomy routing sanity check

On the supplied 100-study dataset, the current deterministic study router was compared with region evidence inferred from non-null criterion labels.

- 100 studies checked.
- 98/100 (98%) had an exact match between the router's region set and the region set implied by non-null labels.
- The two apparent mismatches are documented exceptions rather than demonstrated routing failures: both studies contain hip images with endoprosthesis while the corresponding hip criterion labels are missing.
- Therefore 98% is a **sanity-check statistic, not a formal routing accuracy metric**. The dataset's missing-label semantics are explicitly known to have anomalies.

The two exception studies are:

- `2.25.11175860580562939441493697221497597640` — right hip endoprosthesis; right-hip criterion labels missing.
- `2.25.12798473087614376830819854616447908612` — bilateral hip endoprosthesis; hip criterion labels missing.

Visual inspection confirms that the router is finding the hip images in these cases.

## Consequence for the next model

Region routing is no longer the main bottleneck. The next effort should concentrate on anatomical localization/landmarks and criterion-specific geometry, especially spine-axis localization and hip ROI construction.
