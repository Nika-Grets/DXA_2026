import type { BackendError } from './client';

// ─── Словарь сообщений ────────────────────────────────────────────────────────
// Ключ — значение поля `error.code` из ответа бэкенда
// Значение — текст, который увидит пользователь
const ERROR_MESSAGES: Record<string, string> = {
  // Исследования
  STUDY_NOT_FOUND: 'Исследование не найдено',
  INVALID_STUDY_STATE: 'Операция недоступна в текущем состоянии исследования',

  // Загрузка и валидация DICOM
  DICOM_INVALID: 'Файл не является корректным DICOM',
  DICOM_PIXEL_DATA_MISSING: 'В файле отсутствуют пиксельные данные',
  DICOM_PIXEL_DECODE_FAILED: 'Не удалось декодировать изображение',
  UPLOAD_TOO_LARGE: 'Файл превышает допустимый размер',
  ZIP_PATH_TRAVERSAL: 'Недопустимая структура ZIP-архива',

  // ML
  ML_INPUT_UNSUPPORTED: 'Данный тип исследования не поддерживается для анализа',
  ML_INFERENCE_FAILED: 'Ошибка выполнения ML-модели',

  // Отчёт
  REPORT_NOT_FOUND: 'Отчёт не найден',
  REPORT_GENERATION_FAILED: 'Не удалось сгенерировать отчёт',

  // Технические
  HTTP_ERROR: 'Сервер вернул ошибку',
  NETWORK_ERROR: 'Не удалось связаться с сервером',
};

// ─── Функция получения сообщения ──────────────────────────────────────────────
// Если код не найден в словаре — возвращаем оригинальное сообщение от бэкенда
export function getUserFriendlyMessage(error: BackendError): string {
  return ERROR_MESSAGES[error.code] ?? error.message ?? 'Произошла неизвестная ошибка';
}

// ─── Опционально: логирование для разработчиков ───────────────────────────────
// В продакшене может отправлять в Sentry/логгер
export function logError(error: BackendError): void {
  console.error(
    `[API Error] code=${error.code}, status=${error.httpStatus ?? 'N/A'}`,
    error.message,
    error.details,
  );
}