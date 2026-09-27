# Spine artifact routing decision — V6.9 MVP

## Scope

This is a development/regression audit of the organiser training set (100 studies, 499 DICOM). It is **not** an independent test result.

## Finding

The main failure mode for the spine-artifact head was the study router truncating any study with more than three images:

```python
if len(images) > 3:
    images = images[:3]
```

The organiser set contains 44 studies with more than three images. In several artifact-positive studies, the spine image occurs after the first three images, so the old route could send a hip image into the spine criterion heads.

## Routing fix

The working production router now:

1. keeps all images in studies with more than three images;
2. classifies images independently as anatomy candidates;
3. selects one spine candidate using the smallest absolute superior/inferior side-shift, with top/bottom ratio as a tie-breaker;
4. retains the strongest available left/right hip candidates by lateral shift;
5. keeps a conservative central-image fallback if no independent image is classified as spine.

A regression test was added for a four-image study where the spine is the fourth image.

## Audit result

Compared with the previous first-three route:

- 100 studies total;
- 44 studies had >3 images;
- 16/100 study-level spine selections changed;
- 15/44 selections changed among >3-image studies;
- 2/17 artifact-positive studies changed to a later spine candidate.

For those two positive studies, the full-data diagnostic `spine_artifact.joblib` probability changed from approximately `1.6e-6` to `0.996` and from `0.0049` to `0.994`, respectively.

Across the 99 labelled studies, applying the **final full-data artifact model** to the newly routed spine image gives 17/17 positives and 0/82 negatives at threshold 0.50. This is deliberately recorded only as a **forensic regression signal**: the final model was fitted on these labels, so these numbers must not be presented as validation performance.

## Production decision for the intermediate MVP

**Enable `spine_artifact` in the intermediate MVP path, with an explicit development/regression-only caveat.**

Reason: this is a mandatory organiser criterion, and leaving the head disabled produces zero artifact detections by construction. The corrected routing audit shows that the old route could feed hip images into the spine head, while the existing fitted artifact head separates the corrected spine candidates strongly on the development set.

This is not independent validation: the fitted head used the same labelled studies. The previous leakage-safe OOF result (AUC about 0.546, N=99, positives=17) belongs to the old routing and cannot be reused as validation of the corrected route. Before final claims, regenerate study-grouped OOF with the corrected router.

For the intermediate MVP, the head is enabled because the alternative is a structurally guaranteed zero for a mandatory criterion; the limitation is recorded in `artifacts/MVP_EVALUATION_CURRENT.md`.

## Related criteria

The same >3-image routing bug can affect `spine_position` and `spine_axis`, because those criteria also consume the routed spine image. Therefore their existing OOF metrics should likewise be treated as evidence for the **old route**, not as validation of the corrected route.

## Verification limits

- Full pytest could not be executed in the current shell because `pydicom==3.0.1` is not installed and the environment has no network access to install it.
- Python syntax compilation succeeded for the modified router and regression test.
- The new four-image routing regression case was executed directly and selected image index 3 as spine.
- Docker verification could not be run because Docker is not installed in this shell.
