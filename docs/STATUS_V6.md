# DXA V6 status

## This iteration

- Integrated the leakage-safe classical criterion heads into the runtime adapter as optional benchmark heads.
- Kept deterministic geometry/routing as a guardrail and fallback.
- Spine now consumes the benchmark probabilities for position, axis and artifact in addition to the explicit geometry checks.
- Hip position/rotation consumes the corresponding side-specific benchmark head plus geometry.
- ROI heads are intentionally not used to fabricate a definitive ROI violation because their positive support is too small for reliable deployment.
- No fake localization boxes are produced for learned criteria.
- Official output terminology remains isolated from internal criterion codes.

## Important limitation

The fitted classical heads are a benchmark, not a clinically validated model. V6 therefore does not claim production-level sensitivity/specificity. The next improvement should be anatomical landmark localization, followed by calibration and threshold selection on a held-out study split.
