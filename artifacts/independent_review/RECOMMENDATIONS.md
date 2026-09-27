# RECOMMENDATIONS.md

## Status of this pass

This is one focused iteration (hip localization prioritized per
instruction), not the full five-track plan. Spine localization and a
systematic VerSe evaluation were **not** started — hip had the confirmed
concrete failure cases and the sparse-label problem, so it got the time
budget. Everything below is scoped to what was actually run; see
`CLAUDE_REVIEW.md` for the audit and `ANATOMY_RESEARCH.md` for the
external-dataset assessment.

## Approach comparison table

| Approach | Evidence | Metric | Runtime | Domain gap | Failure cases | Next action |
|---|---|---|---|---|---|---|
| **V6.5 baseline** (shaft-first classical CV, brightness threshold to proximal box) | Independently reproduced in this session on the raw dataset (not just re-read from docs) | pos ROC-AUC 0.731, AP 0.584, val n=35 (11 pos); ROI ROC-AUC 0.8125, val n=35 (3 pos) | milliseconds/image, CPU | None (native to our data) | `968726_right` (box jumps into ilium), `113784_L/R` (box never reaches head on a magnification-view acquisition) | Keep as the production fallback; both failure modes are now documented and reproducible test cases — add them to `test_hip_localization.py` as regression fixtures with the actual crops |
| **+ Hough-circle head-landmark clamp** (`patches/hip_head_landmark_v65_1.py`) | Ran on the same 150 labeled hip images, same split, same downstream classifier protocol | pos ROC-AUC 0.742 (+0.011), AP 0.633 (+0.049); ROI ROC-AUC 0.792 (**-0.021**) | +~5-10ms/image (one extra Hough transform), CPU | None | Fixes the visually-confirmed `968726_right` ilium-jump case (before/after image included); does **not** fix `113784` (scale-invariance issue — head circle radius range is tuned to typical image width, misses on magnification views); mixed effect on ROI target | **Do not promote to production yet.** The pos improvement and roi regression are both within noise for n_val=35/11/3 — this sample size cannot distinguish a real 0.01–0.05 AUC change from chance. Needs a larger validation set (or bootstrap CI on the existing one) before any promotion decision. Treat as a promising, working, but *unproven* refinement |
| **Scale-invariant proximal search window** (re-express `0.42*h`-style fractions as multiples of detected shaft width/length instead of full image height) | Not implemented — diagnosed only (`113784` root-caused to this) | n/a | n/a | n/a | n/a | **Highest-value next experiment.** This is the one concrete, well-understood fix that neither the baseline nor the head-landmark patch addresses. Should be scoped as its own small change to `_proximal_box`, tested against both `968726` and `113784`, before combining with the head-landmark patch |
| **Pelvis COCO dataset pretraining/prior** | Inspected directly (not from filename/memory) | n/a — not attempted | n/a | **Large**: pediatric patient, conventional full-pelvis radiograph, DDH/fracture annotation targets, not adult DXA proximal-femur | n/a | **Do not pursue** for femur localization pretraining. Population and modality mismatch is too large to expect useful transfer; would cost engineering time for likely-negative or misleading results |
| **VerSe CT prior for spine** | Not evaluated this pass (spine track not started) | n/a | n/a | Large (3D CT vs 2D DXA projection) — only geometric/statistical priors (expected vertebra count/shape ratios) look transferable, not pixel-level model weights | n/a | Defer to the spine track; use only as a plausibility-check prior on an L1–L5 landmark result, not as a segmentation model to run directly |
| **External pretrained models found in literature search** (DXA U-Net/RF femur contour papers, HipLandmark, FemoralCoordinateSystem) | Literature search only, see `ANATOMY_RESEARCH.md` | n/a | n/a | Low (DXA-native papers) to high (3D mesh tools) | n/a | No confirmed public, license-clear weights found for the DXA-native papers in this pass. **Action**: check for released code/weights from the JBMR Plus / CLSA-CaMos authors before assuming this path is closed — worth one follow-up search, not a training investment yet |

## Bootstrap check on the head-landmark patch (done in this pass)

Study-level bootstrap (2000 resamples, resampling validation *studies*
with replacement, not individual images, to respect the study-level
grouping) on the `pos` target, baseline vs. head-landmark patch
(`experiments/bootstrap_ci.py`, results in `experiments/bootstrap_ci.json`):

| | point estimate | 95% CI |
|---|---|---|
| Baseline ROC-AUC | 0.731 | [0.516, 0.903] |
| Head-landmark-patched ROC-AUC | 0.742 | [0.526, 0.913] |
| Difference (patched − baseline) | +0.011 | **[-0.095, +0.124]** |

P(patched > baseline) across resamples = 0.61.

**FACT/INFERENCE**: the difference's 95% CI crosses zero comfortably. This
confirms the suspicion in the table above — on n_val=35 (11 positives),
this experiment **cannot distinguish "the patch helps" from "the patch
does nothing" from chance**, even though it visibly fixes one concrete
failure image (`968726_right`). Both things are true at once: the patch
is a correct, targeted fix for a real bug, and the current validation set
is too small to certify an aggregate metric improvement from it. Report it
as "fixes a confirmed failure mode, aggregate effect not yet
statistically distinguishable from zero" — not as "improves AUC."

## What I would actually do next, in order

1. **Fix scale-invariance in `_proximal_box`** (the `113784` failure). This
   is a well-understood, scoped geometry change, not a research question —
   highest value per unit effort.
2. ~~Re-run the head-landmark patch evaluation with a bootstrap CI~~ — done
   above; confirms the effect is real-but-unproven at this sample size.
3. Only after (1): decide whether to combine both fixes and re-run
   the full protocol once more, then update `STATUS_V6.6.md` with FACT-only
   language, matching the discipline already used in `STATUS_V65.md`.
4. Start the spine track (VerSe-informed centerline/axis plausibility
   check) using the same protocol discipline: train-only tuning,
   study-level split, one fixed validation pass.

## Explicit non-recommendations

- Do not pretrain on the Pelvis dataset for femur localization (see above).
- Do not attempt to fine-tune a VerSe CT model directly on 2D DXA images.
- Do not promote the head-landmark patch to the main pipeline without a
  larger or bootstrap-validated evaluation — the current n_val is too
  small to trust a point-estimate win.
- Do not treat the `590815` misrouting bug as urgent (1/252 images), but
  do add it as a regression test once triaged.
