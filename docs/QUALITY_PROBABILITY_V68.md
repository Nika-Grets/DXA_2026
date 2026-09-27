# `quality_prob` semantics — V6.8

- Range: `[0,1]`.
- Meaning: continuous **image-level risk of a quality violation**.
- `0` means low detected violation risk; `1` means high detected violation risk.
- It is distinct from `confidence`: confidence describes the deterministic decision/localizer confidence, while `quality_prob` is intended for ranking and ROC/PR analysis.
- The deterministic production decision path is not switched to ML probabilities by this field.
- When criterion models are available, their probabilities are included; deterministic violation risk is also included. The reported value is the maximum risk across applicable signals.
- The current score is **not clinically calibrated** and must not be interpreted as a validated probability of a patient-level event.
