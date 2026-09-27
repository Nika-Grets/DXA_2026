import type { components } from './schema';
type ApiError = components['schemas']['ApiError']; 

// ─── Базовый URL ──────────────────────────────────────────────────────────────
// Берём из переменных окружения (.env), фолбэк — локальный бэкенд
export const API_URL = import.meta.env.VITE_API_URL || window.location.origin;

// ─── Класс ошибки ─────────────────────────────────────────────────────────────
// Единый формат для всех ошибок бэкенда. Компоненты ловят именно этот класс.
export class BackendError extends Error {
  /** Доменный код ошибки, например "STUDY_NOT_FOUND" */
  public code: string;
  
  /** Дополнительные детали (могут быть любым объектом или null) */
  public details: unknown;
  
  /** HTTP-статус ответа, если известен */
  public httpStatus?: number;

  constructor(
    code: string,
    /** Человекочитаемое сообщение от бэкенда */
    message: string,
    details: unknown = null,
    httpStatus?: number,
  ) {
    super(message);
    this.name = 'BackendError';
    this.code = code;
    this.details = details;
    this.httpStatus = httpStatus;
  }
}

// ─── Универсальный парсер ответов ─────────────────────────────────────────────
// Используется всеми функциями в studies.ts
export async function parseResponse<T>(response: Response): Promise<T> {
  // Успех — просто парсим JSON
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  // Ошибка — пытаемся извлечь тело в формате ApiError
  let apiError: ApiError;
  try {
    apiError = await response.json();
  } catch {
    // Тело не JSON (например, 502 от прокси) — кидаем базовую ошибку
    throw new BackendError(
      'HTTP_ERROR',
      `Сервер вернул ошибку ${response.status}`,
      null,
      response.status,
    );
  }

  // Преобразуем в BackendError с доменным кодом
  throw new BackendError(
    apiError.error.code,
    apiError.error.message,
    apiError.error.details,
    response.status,
  );
}

// ─── Утилита для сборки абсолютных URL ────────────────────────────────────────
// preview_url приходит относительным ("/api/v1/studies/.../preview/...")
// Нужно склеить с базовым адресом бэкенда
export function resolveApiUrl(path: string): string {
  if (path.startsWith('http')) return path; // уже абсолютный
  return new URL(path, API_URL).toString();
}