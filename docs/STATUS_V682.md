# V6.8.2 — experimental hip landmark candidates

## Scope
Added an experimental, explainable candidate-landmark detector for proximal femur visualization.
It produces candidate points for femoral head, neck, shaft axis and a greater-trochanter proxy.

## Important status
These are **candidate landmarks**, not expert-validated clinical landmarks and are **not used by the production quality decision**.

## Development evaluation
On the 150 available hip-side rows from the canonical training set, a 5-fold StudyInstanceUID-grouped OOF experiment gave:

- candidate-landmark feature model for position/rotation: ROC-AUC 0.487, PR-AUC 0.238;
- candidate-landmark feature model for ROI: ROC-AUC 0.591, PR-AUC 0.085.

Therefore the candidate landmark feature vector is retained for visualization/research only and is not promoted to production scoring.

Some individual geometric cues showed signal (for example a normalized shaft/proximal extent cue reached univariate AUC ~0.68 for position/rotation), but the combined model did not generalize in grouped OOF evaluation. This is insufficient evidence for production use.

## Validation limitation
The repository test suite cannot currently be collected in this environment because `pydicom` is absent. The new module passes Python compilation and a direct synthetic smoke test. Dependency pinning/containerization remains a release-candidate task.
