# CLAUDE_REVIEW.md — Technical audit of DXA V6.5

Scope: `backend/app` (routing, localizer, adapter), `artifacts/*_v65.py`
(training/eval scripts), `docs/STATUS_*`, `docs/EXPERIMENTAL_V64.md`,
`tests/`, and the serialized artifacts in `artifacts/`.

Every claim below is labeled:
- **FACT** — verified directly against the code/data in this checkpoint.
- **EXPERIMENT** — I ran something and observed a result (script included).
- **INFERENCE** — my interpretation of a FACT/EXPERIMENT.
- **RECOMMENDATION** — what to do about it.

Everything here was reproduced independently in this session: I unpacked
the raw `НД_для_обучения.zip` DICOMs myself (not the cached `/mnt/data/...`
arrays the original scripts expect, which don't exist in this sandbox),
rebuilt a manifest, re-ran routing and localization, and re-ran the
training/eval protocol from scratch. Where my numbers match the numbers
already written in `STATUS_V65.md` / `EXPERIMENTAL_V64.md`, that is an
independent reproducibility check, not a re-statement of the same run.

## 1. Study-level split / leakage

- **FACT**: `artifacts/study_split.json` is a `{StudyInstanceUID: "train"|"validation"}`
  dict, 80 train / 20 validation studies, zero overlap by construction
  (single dict keyed by UID — a study cannot be in both).
- **FACT**: my manifest, rebuilt independently from the raw DICOMs, contains
  exactly the same 100 study UIDs as `study_split.json` (100/100 match).
- **FACT**: `experiment_cv_models_v65.py` / `feature_builder_v65.py` select
  models only via `GroupKFold` on **train** studies (`groups=study_uid`),
  and evaluate once on the fixed validation split with no threshold tuning
  on validation (`pred = p >= .5`, not a validation-fit threshold).
- **EXPERIMENT**: I reimplemented the same protocol independently
  (`experiments/exp_hip_baseline_reproduction.py`) against my own DICOM
  load path and got val ROC-AUC 0.731 for hip pos/rotation and 0.8125 for
  hip ROI — consistent with the 0.73 / 0.729–0.781 already claimed in
  `STATUS_V65.md` / `EXPERIMENTAL_V64.md`.
- **INFERENCE**: the leakage-safety claims in the docs are real, not just
  asserted. This is the one area I would **not** prioritize re-auditing
  further.

## 2. Region routing

- **FACT**: `classify_study` routed my independently-loaded images into
  99 spine / 79 femur_left / 74 femur_right (labels file has 99 / 78 / 72
  respectively) — routing is highly consistent with expert labels.
- **BUG (FACT)**: study `...590815` is routed to `femur_left`, but the
  underlying image is visually a **lumbar spine** acquisition (vertebral
  bodies, not a hip). See `full_hip_montage_153_images.png`, tile
  `590815_left`. This is a genuine misrouting case, not a localization
  problem — `classify_study` picked the wrong region for one image in this
  100-study set.
- **RECOMMENDATION**: pull this study's DICOM tags (`BodyPartExamined`,
  `SeriesDescription`, image aspect ratio) and check whether the routing
  heuristic can be made to reject a "femur" call when the image aspect
  ratio / symmetry profile looks like a spine series. One misroute in 252
  images is not urgent, but it should be added to the routing test suite
  as a regression case once triaged.

## 3. Hip localization — real failure cases (not hypothetical)

I rendered all 153 hip images with `bone_bbox` (red) and `shaft_bbox`
(green) overlaid (`full_hip_montage_153_images.png`) instead of relying on
the existing 10-image cherry-picked montage. Two distinct, reproducible
failure modes:

- **FACT**: `968726_right` — the proximal box is anchored well above the
  femoral head, over the iliac wing. Root cause in `_proximal_box`: the
  column-brightness threshold crossing can propagate upward through a
  bright pelvic region before it hits the head, since the check is a 1-D
  brightness signal along a fixed-width column, not an anatomical
  landmark.
- **FACT**: `113784_left/right` — a differently-scaled/cropped acquisition
  (magnification view, femoral head fills most of the frame). The box
  stays near the shaft and never reaches the head at all. Root cause: the
  proximal search window (`local_top = shaft_top - 0.42*h`, etc. in
  `hip_localizer.py`) is expressed as a **fixed fraction of full image
  height**, which assumes a roughly constant physical field-of-view across
  acquisitions. On a tighter/zoomed acquisition this fraction is wrong in
  absolute pixels, and the search window simply doesn't reach the head.
  This is a **different bug class** from #1 (anatomical ambiguity vs.
  scale invariance) and is not fixed by the head-landmark patch below.
- **EXPERIMENT**: see `ANATOMY_RESEARCH.md`/`RECOMMENDATIONS.md` and
  `patches/hip_head_landmark_v65_1.py` for a targeted fix attempt at #1.
  #2 (scale invariance) is flagged but **not fixed** in this pass — a real
  fix means expressing the proximal search window as a multiple of the
  detected shaft width/length instead of image height, which is a small
  but non-trivial change to `_proximal_box` geometry and needs its own
  validation pass before being trusted.

## 4. ROI criterion

- **FACT**: ROI positive labels are extremely sparse: 4 train / 3
  validation across both sides combined (matches
  `artifacts/anatomy_priors/hip_localization_eval_v63.json`:
  `roi_label_pos: 7`). Any ROC-AUC/F1 computed on 3 validation positives
  should be treated as indicative, not a real estimate of validation
  performance — its own confidence interval spans nearly the whole [0,1]
  range at that sample size.
- **FACT**: the code already avoids fabricating a fixed-pixel 3/3/2 cm rule
  from image borders (per `DXA_NEXT_PHASE.md`, "V6.3 correction") and
  instead reports *available physical margin* separately from the
  anatomical bbox. This matches the ТЗ's own figure (margins, not a fixed
  padding operation) and Q&A pixel spacing (X=0.60mm/px, Y=1.05mm/px).
  This is a correct design decision, not a shortcut.
- **INFERENCE**: given n=7 positives total, no supervised ROI classifier
  trained on this data alone can be validated to a level that supports a
  strong claim either way. This matches the project's own conclusion in
  `EXPERIMENTAL_V64.md` — I did not find a reason to override it.

## 5. Reproducibility / documentation gaps

- **FACT**: `experiment_cv_models_v65.py`, `feature_builder_v65.py`,
  `train_anatomy_quality_v64.py` all hard-code absolute paths under
  `/mnt/data/...` (the original developer's machine). None of them run
  as-is outside that machine; I had to rebuild the whole data-loading path
  from the raw DICOM zip to reproduce anything.
- **RECOMMENDATION**: before final submission, these scripts need either
  (a) a config/env-var for the data root, or (b) to be replaced by a
  single documented entry point that takes `--data-root` and rebuilds the
  manifest from raw DICOMs + the labels workbook, the way I did in
  `experiments/build_manifest.py`. Otherwise "reproduce this on a new
  DICOM set" (a hard README requirement) is not actually possible for a
  third party.

## 6. Robustness gaps not yet triggered by this dataset

- **FACT**: every DICOM in `НД_для_обучения.zip` has
  `PhotometricInterpretation = MONOCHROME2` (checked all 499 files).
  `prediction_service.py` passes `parsed.pixels` (modality LUT applied)
  straight to `classify_study`/`localize_hip` with **no MONOCHROME1
  inversion**, unlike `dicom_service.preview_array`, which does invert for
  MONOCHROME1. If the organizer's closed test set contains any MONOCHROME1
  image, the high-percentile bone mask in `hip_localizer._candidate_mask`
  would threshold on soft tissue instead of bone, i.e. exactly the
  "picks something bright but wrong" failure class the project is trying
  to eliminate.
- **RECOMMENDATION**: apply the same MONOCHROME1 inversion in the
  inference path that `dicom_service.preview_array` already does for
  display, and add one synthetic MONOCHROME1 test case to
  `test_hip_localization.py` / `test_spine_localization.py`.

## What's already good (don't touch without reason)

- Study-level split discipline and GroupKFold-only-on-train model
  selection is correctly implemented and independently reproducible.
- The decision not to fabricate ROI verdicts from image borders, and to
  keep scoliosis/endoprosthesis as separate non-violation findings, is
  correct per the official Q&A and already implemented
  (`app/terminology`, `DXA_NEXT_PHASE.md`).
- Region routing is solid (only one misroute found in 252 images).
- Experimental heads are correctly gated behind
  `ENABLE_EXPERIMENTAL_BENCHMARK_HEADS` and off by default until their
  training provenance is audited — this is the right call, I did not find
  a reason to promote them yet.
