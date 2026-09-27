# Frontend integration status — V6.9 MVP

## Completed

- Added login/register UI for the backend Bearer-token authentication.
- Access and refresh tokens are stored locally and rotated through `/api/v1/auth/refresh`.
- Protected routes redirect unauthenticated users to `/login`.
- API requests automatically attach `Authorization: Bearer ...` and retry once after a 401 using the refresh token.
- DICOM preview and thumbnail requests are fetched as authenticated blobs, because the backend protects preview endpoints.
- Study page now reads an existing `/prediction` result before starting a new ML prediction.
- Per-image `results`, `violation_type`, and `findings` are surfaced in the study panel.
- Logout is wired to `/api/v1/auth/logout`.

## Backend contract used

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/upload`
- `GET /api/v1/studies/{study_id}`
- `GET /api/v1/studies/{study_id}/prediction`
- `POST /api/v1/studies/{study_id}/predict`
- `GET /api/v1/studies/{study_id}/preview/{image_id}`
- `POST/GET /api/v1/studies/{study_id}/report`

## Environment limitation

The current execution environment does not have the complete frontend `node_modules` cache and has no registry access. `npm ci` therefore cannot finish, so `npm run build` cannot currently be executed here. The source changes are saved in the project; build verification should be run in the normal development environment with `npm ci && npm run build`.

The local Python environment also lacks `pwdlib`, so the backend cannot be started directly in this sandbox; this is an environment dependency issue, not a frontend source error.
