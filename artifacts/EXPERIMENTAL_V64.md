# V6.4 experimental notes

This checkpoint is an experimental continuation of V6.3.

## Hip localization
- Retains the femoral-shaft-first proximal femur localizer.
- Tested an additional local proximal-continuity cue; it did not materially change the aggregate localization score distribution, so it is not claimed as a validated improvement.
- Tested Hough-line shaft detection; it is inferior/unstable because pelvic edges can be selected. It is kept only as an experiment, not used by the main pipeline.

## Anatomy + geometry quality experiment
A leakage-safe study-level experiment was run using only training studies for fitting and the fixed 20-study validation split for evaluation.

Features: canonicalized proximal-femur crop + localizer geometry.
- pos/rotation: ROC-AUC 0.595 with logistic regression; HOG+SVM exploratory ROC-AUC up to 0.769 on this small validation set.
- ROI: only 4 positive training labels and 3 validation positives; logistic ROC-AUC 0.729 and HOG+SVM up to 0.781, but F1 at default threshold was 0.0. This is too sparse to treat as a reliable model.

Important: existing serialized benchmark heads in the main V6.x pipeline were not used as validation metrics in this experiment because their training provenance must be audited before any claim of leakage-safe performance.

## Interpretation
The main architectural conclusion is that the anatomy layer is useful, but the current 100-study dataset is too small/sparse for a trustworthy ROI classifier from geometry alone. The 3/3/2 rule is retained as a physical/interpretive criterion, not a hard image-border rule.
