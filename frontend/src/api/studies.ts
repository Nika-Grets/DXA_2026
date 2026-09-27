import { API_URL, parseResponse, resolveApiUrl, BackendError } from './client';
import { authorizedFetch, fetchPreviewBlob, getAccessToken, refreshTokens } from './auth';
import type { components } from './schema';

type StudySummary = components['schemas']['StudySummary'];
type PredictionResponse = components['schemas']['PredictionResponse'];
type ReportResponse = components['schemas']['ReportResponse'];

// ─── POST /api/v1/upload ──────────────────────────────────────────────────────
/**
 * Загружает один DICOM-файл или ZIP-архив.
 * Возвращает StudySummary с study_id и списком изображений.
 *
 * ⚠️ Не устанавливайте Content-Type вручную — браузер сам добавит
 *    правильный multipart boundary.
 */
export function uploadStudy(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<StudySummary> {
  const send = (retried: boolean): Promise<StudySummary> => new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    });

    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText) as StudySummary); }
        catch (err) { reject(err); }
        return;
      }

      if (xhr.status === 401 && !retried && getAccessToken()) {
        try {
          const tokens = await refreshTokens();
          const retry = send(true);
          void tokens;
          retry.then(resolve).catch(reject);
          return;
        } catch {
          // Fall through to the regular API error below.
        }
      }

      try {
        const errorBody = JSON.parse(xhr.responseText) as { error: { code: string; message: string; details: unknown } };
        reject(new BackendError(errorBody.error.code, errorBody.error.message, errorBody.error.details, xhr.status));
      } catch {
        reject(new BackendError('HTTP_ERROR', `HTTP ${xhr.status}`, null, xhr.status));
      }
    };

    xhr.onerror = () => reject(new BackendError('NETWORK_ERROR', 'Сетевая ошибка', null));
    xhr.ontimeout = () => reject(new BackendError('TIMEOUT', 'Превышено время ожидания', null));
    xhr.timeout = 120_000;
    xhr.open('POST', `${API_URL}/api/v1/upload`);
    const token = getAccessToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  });

  return send(false);
}

// ─── GET /api/v1/studies/{study_id} ──────────────────────────────────────────
/**
 * Получает текущее состояние исследования.
 * Используется для поллинга статуса после загрузки.
 */
export async function getStudy(studyId: string): Promise<StudySummary> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}`);
  return parseResponse<StudySummary>(response);
}

// ─── GET /api/v1/studies/{study_id}/prediction ───────────────────────────────
export async function getPrediction(studyId: string): Promise<PredictionResponse> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}/prediction`);
  return parseResponse<PredictionResponse>(response);
}

// ─── POST /api/v1/studies/{study_id}/predict ─────────────────────────────────
/**
 * Запускает ML-анализ.
 *
 * ⚠️ Операция СИНХРОННАЯ — результат возвращается сразу в ответе.
 *    Не нужно поллить после этого запроса.
 *    На время выполнения показывайте спиннер и блокируйте кнопку.
 */
export async function predictStudy(studyId: string): Promise<PredictionResponse> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}/predict`, {
    method: 'POST',
  });
  return parseResponse<PredictionResponse>(response);
}

// ─── POST /api/v1/studies/{study_id}/report ──────────────────────────────────
/**
 * Генерирует PDF-отчёт.
 *
 * ⚠️ Возвращает 409, если исследование ещё не прошло предсказание.
 */
export async function generateReport(studyId: string): Promise<ReportResponse> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}/report`, {
    method: 'POST',
  });
  return parseResponse<ReportResponse>(response);
}

// ─── GET /api/v1/studies/{study_id}/report ───────────────────────────────────
/**
 * Скачивает готовый PDF-отчёт.
 * Возвращает Blob с содержимым файла.
 */
export async function downloadReport(studyId: string): Promise<Blob> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}/report`);

  if (!response.ok) {
    await parseResponse(response); // кинет BackendError
  }

  return response.blob();
}

/**
 * Альтернатива: открывает отчёт в новой вкладке браузера.
 * Удобно, если пользователь хочет просмотреть перед скачиванием.
 */
export function openReportInBrowser(studyId: string): void {
  window.open(`${API_URL}/api/v1/studies/${studyId}/report`, '_blank');
}

// ─── GET /api/v1/studies/{study_id}/preview/{image_id} ───────────────────────
/**
 * Возвращает абсолютный URL превью изображения.
 * Сам запрос не делает — просто склеивает путь.
 */
export function getPreviewUrl(previewUrl: string): string {
  return resolveApiUrl(previewUrl);
}

//функция, которая превращает Blob в настоящий файл для пользователя
export async function loadPreviewBlob(previewUrl: string): Promise<string> {
  return fetchPreviewBlob(resolveApiUrl(previewUrl));
}


// ─── GET /api/v1/studies/{study_id}/csv ─────────────────────────────────────
/** Скачивает итоговую CSV-таблицу в формате выходного контракта ДепЗдрава. */
export async function downloadStudyCsv(studyId: string): Promise<Blob> {
  const response = await authorizedFetch(`/api/v1/studies/${studyId}/csv`);
  if (!response.ok) {
    await parseResponse(response);
  }
  return response.blob();
}

export async function saveStudyCsvToFile(
  studyId: string,
  fileName = 'dexa-results.csv',
): Promise<void> {
  const blob = await downloadStudyCsv(studyId);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function saveReportToFile(
  studyId: string,
  fileName = 'dicom-report.pdf'
): Promise<void> {
  const blob = await downloadReport(studyId);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
