# ANATOMY_RESEARCH.md — external datasets, priors, literature

Scope of this pass: assess the two supplied external resources (Pelvis
COCO dataset, VerSe) firsthand, plus a targeted (not exhaustive) literature
search for proximal-femur / lumbar-spine localization approaches
transferable to DXA. This is a first pass, not a systematic review —
flagged as such per item.

## 1. Supplied external datasets (inspected directly, not from memory)

### Pelvis_v1i_coco-segmentation (`Pelvis_v1i_coco-segmentation_1.zip`)

| Field | Value |
|---|---|
| Format | COCO instance segmentation, Roboflow export |
| Size | 320 train / 91 valid / 47 test images |
| Categories | `Femur`, `FEMUR`, `ILIAK`, `OBTURATOR`, `PUBIS`, `SUORCIL`, `TEARDROP` |
| Modality | Conventional AP pelvis radiograph (**not DXA**) |
| Population | **Pediatric** — sample image metadata reads "2 yaşında" (age 2), institution Hacettepe Üniversitesi (Turkey); visible open growth plates, genital shielding position typical of pediatric hip series |
| Task the annotations serve | Looks like hip dysplasia / pelvic-fracture landmark segmentation (teardrop, obturator, iliac wing, pubis are classic DDH/fracture-grading structures), not proximal-femur-for-BMD localization |

**FACT**: I extracted and visually inspected the dataset directly (not
taking the filename at face value). It is a full bilateral pelvis view of
a pediatric patient, radiographically very different from an adult
single-hip DXA scan: different bone density/contrast physics, open
epiphyseal plates, different FOV (both hips + full pelvis + partial
spine/abdomen vs. one hip cropped to femur/acetabulum), and a different
annotation purpose (fracture/dysplasia structures vs. neck/head/trochanter
ROI for BMD).

**INFERENCE**: this dataset is **not a good source for supervised
pretraining or fine-tuning** of a proximal-femur-for-DXA localizer. Pixel
statistics, patient age/bone maturity, and FOV are all mismatched.
**Where it could still help**, narrowly: as a source of *coarse pelvis
shape/symmetry priors* (e.g., where the ilium/obturator foramen sit
relative to the acetabulum, for a classical-geometry sanity check) — but
even that requires care given the pediatric proportions are not adult
proportions. I would not spend engineering budget here beyond that; it
does not address either of the two failure modes found in `CLAUDE_REVIEW.md`
(anatomical-ambiguity jump into the ilium, or scale-invariance on
magnification views).

**RECOMMENDATION**: do not pretrain on this dataset for the femur
localizer. If reused at all, use only the `FEMUR` mask's coarse shape
statistics (e.g. head/neck aspect ratio) as a sanity-check prior, and
document the population mismatch explicitly if it is mentioned in the
presentation, so it isn't mistaken for adult-DXA-relevant pretraining.

### VerSe (`verse-main.zip`)

**FACT**: not deeply re-inspected pixel-by-pixel in this pass (time
budget went to the hip track first, per the stated priority). Known
facts from its own documentation: 374 multi-detector **CT** scans, 355
patients, voxel-level vertebra segmentation/labelling, MICCAI 2019/2020
challenge, code at `github.com/anjany/verse`.

**INFERENCE**: the transferable part is **not** pixel appearance (CT vs.
2D projection DXA are radiometrically unrelated) but **relative vertebral
geometry** — e.g., typical L1–L5 aspect ratios, expected vertebral count
and spacing, which could inform a sanity-check prior for "does this
inter-vertebral spacing pattern look like a plausible lumbar spine" once
a spine axis/centerline is already extracted from the DXA image by some
other (2D) means. Directly reusing a VerSe-trained CT segmentation model
on a 2D DXA projection is not meaningful — the modality gap (3D CT
Hounsfield volumes vs. a single 2D absorptiometry projection) is larger
than a typical fine-tuning gap.

**RECOMMENDATION**: do not spend budget trying to run or fine-tune a
VerSe CT model on our 2D images directly. If used at all, extract only
the *statistical priors* (expected vertebra count/shape ratios) as a
plausibility check on the L1–L5/Th12 landmark localization, not as a
model-weights transfer. This should be revisited after a first spine
localization pass exists to check against — I have not yet built one in
this session (hip was prioritized).

## 2. Literature / GitHub search (targeted, not exhaustive)

For each, transferability is judged specifically against *our* task:
localize proximal femur (neck/head/trochanter) on a single-hip DXA AP
image with pixel spacing X=0.60mm, Y=1.05mm, and evaluate a 3/3/2 cm
visualization-margin criterion.

| Method | Modality | Task | Code/weights | License | Domain gap to us | What's actually reusable |
|---|---|---|---|---|---|---|
| Automated femoral landmarking via U-Net contour + geometry (JBMR Plus, 2024/25, PMC13367575) | **DXA** (555 scans) | Femur contour segmentation → geometric landmarks for fracture-risk SSAM | Not confirmed public (paper only, no repo found in this pass) | Unknown | **Lowest** — same modality, same clinical population, IoU 91.6%, Dice 0.95 reported | Architecture/approach description only, unless authors release weights — worth a direct outreach/check, but nothing to `pip install` today |
| CNN contour detection of hip/proximal femur on DXA (CLSA/CaMos cohorts) | **DXA** (209 subjects) | 5-layer U-Net femur segmentation from hip DXA | Not found public | Unknown | Low — same modality | Confirms a small U-Net (5 layers) is sufficient for DXA femur contour at this data scale; a useful architecture reference if we ever have enough masks to train one ourselves |
| Femur segmentation in DXA via decision tree / regional random forest (Hussain et al., several papers) | DXA | Classical ML (RF/decision tree) segmentation + geometric landmark extraction, JI up to ~0.996 on contour | Not found public | Unknown | Low | Confirms classical-CV / classical-ML approaches (not deep learning) are viable for DXA femur contour at small dataset sizes — supports continuing to invest in the classical-geometry line V6.5 already uses, rather than assuming only deep learning can work |
| HipLandmark (PMC13544418, github.com/MahdieAghasi/HipLandmark) | **Conventional pelvis X-ray**, adult | 28-landmark hip/pelvis annotation, deep model | **Public code + dataset** | Check repo | Moderate — different modality (plain radiograph vs DXA) and much higher resolution (avg 3092×8259px) than our images | Landmark *definitions* (head-neck axis, hip joint orientation axis) are directly reusable as a feature/QA vocabulary even without reusing the model; not directly runnable on our pixel scale/statistics without retraining |
| FemoralCoordinateSystem (github.com/RWTHmediTEC/FemoralCoordinateSystem) | 3D surface models (CT-derived) | Anatomical coordinate system fitting on a 3D femur mesh | **Public code** | Check repo | High — needs a 3D mesh, we have a single 2D projection | Not directly usable; conceptually confirms head-neck axis + shaft axis is the standard anatomical basis, matching what V6.5 already tries to do in 2D |
| Feature Pyramid Network for proximal femur fracture detection (Nature Sci Rep, 2024) | Plain radiography | Fracture detection, not positioning/QC | Not found public | Unknown | Different task entirely (pathology, not positioning QC) | Not applicable to our QC task |

**Overall INFERENCE**: no off-the-shelf, license-clear, DXA-specific
pretrained model/weights turned up in this pass that we could legally and
practically drop into inference today. The most relevant work (DXA-native
U-Net/RF femur contour papers) doesn't have confirmed public weights.
This somewhat validates the project's current approach: classical,
explainable, geometry-first localization is a reasonable choice given (a)
no ready-made transferable model exists, and (b) 100 studies is not
enough to train a U-Net from scratch with confidence. The improvement
lever that came out of this pass is **not** "go find a pretrained model" —
it's "borrow the anatomical landmark vocabulary (head/neck/trochanter
axis, head-circle-based anchoring) from the classical/DXA literature and
add it to the existing geometry pipeline," which is exactly what
`patches/hip_head_landmark_v65_1.py` in this delivery does as a first
step.

**RECOMMENDATION for next iteration**: if pursuing this further, directly
email/check for the JBMR Plus and CLSA/CaMos U-Net authors' code
availability (papers are recent, 2024–2026, code may be released after
review) before assuming a from-scratch retrain is the only path.
