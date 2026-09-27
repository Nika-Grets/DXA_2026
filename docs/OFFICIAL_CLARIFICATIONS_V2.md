# Official clarifications V2 applied

Source: `Разъяснения по вопросам ЛЦТ_V2`.

Applied decisions:

- Physical pixel size is fixed for the dataset: **Y = 1.05 mm/px, X = 0.60 mm/px**.
- The dataset uses one scanner/device variant.
- `violation_type` is a closed Russian-language list. Multiple violations are separated with `;`; no violation means an empty field.
- Spine: `Некорректная укладка`, `Не выравнена ось позвоночника`, `Присутствуют посторонние предметы`.
- Hip: `Некорректная укладка`, `Некорректная область интереса`.
- `quality_prob` is emitted in `[0,1]` as an additional probability of violation.
- `anatomical_region` has only two official values: `Поясничный отдел позвоночника` and `Проксимальный отдел бедра`; left/right is intentionally not exposed.

The internal terminology codes remain stable so the official dictionary can later replace only the mapping layer.
