# DXA Quality Control — Release Candidate V6.9

MVP/Release Candidate для автоматической проверки качества DXA DICOM-исследований.

Система принимает одиночные DICOM/ZIP-исследования, группирует изображения по `StudyInstanceUID`, определяет анатомическую область, оценивает критерии качества и возвращает машиночитаемый результат через API и интерфейс.

> **Статус:** intermediate MVP / release candidate. Система не является клинически валидированным диагностическим инструментом. Development OOF-метрики не являются независимым финальным тестом.

## 1. Назначение

Проверка технического качества DXA-изображений перед использованием исследования:

- чтение и валидация DICOM;
- работа с исследованием целиком, а не только с именами файлов;
- маршрутизация spine / proximal femur;
- бинарный класс качества: `quality` / `violation`;
- выдача типа нарушения;
- дополнительные находки, не являющиеся нарушениями качества;
- экспорт результата в CSV/XLSX и PDF;
- web-интерфейс для загрузки исследования и просмотра результата.

## 2. Что реализовано в MVP

### Поддерживаемые области

- поясничный отдел позвоночника;
- проксимальный отдел бедра.

### Критерии

Для spine реализованы проверки положения, оси и артефактов.

Для hip реализованы проверки положения/ротации и физического запаса до границ изображения для ROI.

`SCOLIOSIS` и `ENDOPROSTHESIS` являются **findings**, а не quality violations: они не должны сами по себе переводить `quality_class` в нарушение.

### Основной pipeline

```text
DICOM / ZIP
    ↓
DICOM validation + safe metadata
    ↓
StudyInstanceUID grouping
    ↓
anatomical routing
    ↓
criterion models + deterministic geometry
    ↓
quality_prob (risk of quality violation)
    ↓
quality_score = 1 - quality_prob
    ↓
quality_class + violation_type + findings
    ↓
CSV / XLSX / PDF / Web UI
```

## 3. Ограничения

- Часть критериев основана на proxy/geometric features, а не на полноценных клинических landmarks.
- `right_posrot` имеет OOF-поддержку и включён в production decision path.
- `spine_artifact` включён в текущий MVP decision path, но его corrected-routing OOF-метрики недостаточно сильны для заявления о независимой валидации.
- ROI/landmark экспериментальные ветки не включены в production decision path.
- Независимый закрытый финальный test set отсутствует в разработческой среде.
- `quality_prob` следует интерпретировать как технический risk score нарушения качества, а не как вероятность заболевания или клинический прогноз.
- Система не заменяет оценку медицинским специалистом.

Подробные решения и provenance находятся в `artifacts/`.

## 4. Структура проекта

```text
backend/
  app/
    api/             REST API
    core/            settings, security, exceptions
    db/              SQLAlchemy models
    external_ml/     ML adapter / batch boundary
    ml/              routing, localization, quality baseline
    schemas/         Pydantic API contracts
    services/        upload, prediction, report, storage
    templates/       report template
  tests/

frontend/
  src/
    api/             authenticated API clients
    auth/            login/protected routes
    components/      UI components
    pages/           application pages

artifacts/
  models/            serialized benchmark heads
  *oof*/             OOF evaluation artifacts
  *decision*.md      production decisions / provenance
  *.json/*.csv       manifests and evaluation outputs

docs/
  official terminology and organizer clarifications

data/                local runtime data; do not submit
.training_dicom/     local training/reference DICOM; do not submit
```

## 5. Системные требования и зависимости

### Backend

- Python 3.13
- FastAPI
- Uvicorn
- Pydantic / pydantic-settings
- NumPy / SciPy
- scikit-learn
- pydicom
- Pillow
- OpenCV
- SQLAlchemy / Alembic
- ReportLab
- PyJWT / pwdlib
- Jinja2

Точные версии зафиксированы в `requirements.txt`.

### Frontend

- Node.js 22+
- npm
- React 19
- Vite
- Ant Design
- React Query
- React Router

Точные версии зафиксированы в `frontend/package-lock.json`.

## 6. Запуск без Docker

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env
```

Запуск backend:

```bash
cd backend
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Запуск frontend:

```bash
cd frontend
npm ci
npm run dev
```

Backend:

```text
http://localhost:8000
```

Swagger UI в development:

```text
http://localhost:8000/docs
```

Health:

```text
http://localhost:8000/health
```

## 7. Docker

Создать локальный `.env`:

```bash
cp .env.example .env
```

Для production обязательно заменить секреты и включить production security settings.

Сборка и запуск:

```bash
docker compose up --build
```

Проверка:

```bash
curl http://localhost:8000/health
```

`data/` подключается как Docker volume `dexa_data`, поэтому runtime database и загруженные исследования не должны храниться в submission archive.

## 8. API

Основные endpoint'ы:

| Method | Endpoint | Назначение |
|---|---|---|
| `GET` | `/health` | техническая проверка |
| `POST` | `/api/v1/auth/register` | регистрация |
| `POST` | `/api/v1/auth/login` | получение токенов |
| `GET` | `/api/v1/auth/me` | текущий пользователь |
| `POST` | `/api/v1/upload` | загрузка DICOM/ZIP |
| `POST` | `/api/v1/batch` | пакетная обработка ZIP |
| `GET` | `/api/v1/studies` | список исследований |
| `GET` | `/api/v1/studies/{study_id}` | исследование |
| `POST` | `/api/v1/studies/{study_id}/predict` | inference |
| `GET` | `/api/v1/studies/{study_id}/prediction` | результат inference |
| `POST` | `/api/v1/studies/{study_id}/report` | генерация PDF |
| `GET` | `/api/v1/studies/{study_id}/report` | получение PDF |
| `GET` | `/api/v1/studies/{study_id}/preview/{image_id}` | preview изображения |

Большинство пользовательских endpoint'ов требуют `Authorization: Bearer <token>`.

## 9. Input / Output

### Input

- один DICOM-файл;
- ZIP с DICOM-исследованием;
- для batch — ZIP с несколькими исследованиями.

DICOM проходит валидацию. В частности, при включённой настройке `REQUIRE_BURNED_IN_ANNOTATION_NO` требуется явное `BurnedInAnnotation=NO`.

### Output contract

Для результата на уровне image/region используются:

```text
path_to_study
study_uid
image_uid
anatomical_region
quality_class
violation_type
processing_status
time_of_processing
confidence
quality_prob
findings
```

`quality_class`:

```text
0 = acceptable
1 = quality violation
```

`quality_prob`:

```text
[0, 1] = continuous technical risk score of a quality violation
```

`quality_score`:

```text
1 - quality_prob
```

`violation_type` содержит только критерии, которые относятся к качеству изображения.

`findings` используется для дополнительных находок, например `SCOLIOSIS` и `ENDOPROSTHESIS`.

## 10. Model, preprocessing и postprocessing

### Preprocessing

- DICOM pixel data → NumPy;
- normalization по 1/99 percentile;
- проверка конечности значений и вырожденных изображений;
- safe DICOM metadata;
- routing по изображению/исследованию;
- для hip учитываются физические размеры пикселя.

### Model / inference

Текущий baseline сочетает:

1. анатомический routing;
2. deterministic geometry;
3. сериализованные benchmark criterion heads;
4. OOF-derived calibration maps для поддержанных score heads.

Production-default benchmark heads контролируются через `ENABLE_EXPERIMENTAL_BENCHMARK_HEADS`. По умолчанию экспериментальные головы не включаются.

### Postprocessing

- aggregation по `StudyInstanceUID`;
- удаление дублей вычислений при сохранении результата для каждого исходного DICOM;
- перевод criterion codes в официальные термины;
- формирование `quality_class`, `violation_type`, `findings`;
- расчёт `quality_prob` и complementary `quality_score`.

## 11. Evaluation и воспроизводимость

Основной development protocol:

- `StratifiedGroupKFold(5)`;
- group = `StudyInstanceUID`;
- OOF predictions;
- bootstrap 95% CI на уровне исследований.

Ключевые артефакты:

```text
artifacts/canonical_manifest.json
artifacts/study_split_canonical.json
artifacts/model_provenance_v68.json
artifacts/models/quality_calibrators.json
artifacts/corrected_routing_oof/
artifacts/mvp_eval/
```

Финальные `.joblib`, переобученные на всех размеченных данных, не следует трактовать как независимую test estimate.

## 12. Известные ошибки и обработка

- **Некорректный/неподдерживаемый DICOM:** upload отклоняется с контролируемой API-ошибкой.
- **Отсутствует обязательная деидентификация (`BurnedInAnnotation=NO`):** исследование блокируется согласно настройке безопасности.
- **Не удалось определить анатомическую область:** inference завершается ошибкой, а не создаёт случайный регион.
- **Нет prediction перед PDF:** endpoint отчёта возвращает `409`.
- **Ошибка генерации PDF:** возвращается `REPORT_GENERATION_FAILED`; runtime PDF не считается готовым.
- **Повторяющиеся изображения:** вычисление дедуплицируется, но output сохраняет строку для каждого исходного изображения.
- **Исследование содержит более трёх изображений:** routing не обрезает список до первых трёх; spine/hip candidates выбираются по всем изображениям.

## 13. Security

При `APP_ENV=production` приложение требует:

- уникальный `JWT_SECRET_KEY` длиной не менее 32 символов;
- `DATA_ENCRYPTION_KEYS`;
- `FORCE_HTTPS=true`;
- `ENABLE_DOCS=false`.

## 14. Tests

```bash
pytest -q
```

Минимальная проверка после сборки:

```bash
curl http://localhost:8000/health
```

Frontend production build:

```bash
cd frontend
npm ci
npm run build
```

## 15. Дальнейшая работа

1. Расширить и независимо валидировать criterion-level models.
2. Добавить полноценные landmark/ROI модели с отдельной closed test set.
3. Провести независимую финальную оценку на закрытом наборе.
4. Расширить поддержку всех обязательных классов/критериев из финального ТЗ.
5. Улучшить визуализацию реальных backend localization/defect annotations.
6. Подготовить финальную документацию и демонстрационный сценарий.


## Веб-интерфейс и экспорт результатов

После завершения ML-анализа страница исследования предоставляет:
- **Скачать CSV-результаты** — итоговая таблица по выходному контракту ДепЗдрава;
- **Скачать PDF-отчёт** — структурированный отчёт исследования.

CSV содержит обязательные поля выходного контракта и дополнительные `confidence`, `quality_prob`, `findings`.

## Docker Compose: backend + frontend

Production-like smoke test запускается одной командой:

```bash
docker compose build
docker compose up
```

После запуска:
- frontend: `http://localhost:5173`
- backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

Перед запуском создайте `.env` из `.env.example`:

```bash
cp .env.example .env
```

Frontend собирается отдельным multi-stage Dockerfile и отдаётся через nginx; `/api/*` проксируется на `dexa-backend`.
