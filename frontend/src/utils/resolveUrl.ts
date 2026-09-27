export const API_URL: string = 
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Преобразовать относительный путь в полный URL.
 * 
 * @example
 * resolveUrl('/api/v1/studies/abc/preview/def')
 * // → 'http://localhost:8000/api/v1/studies/abc/preview/def'
 * 
 * resolveUrl('https://cdn.example.com/image.png')
 * // → 'https://cdn.example.com/image.png' (уже полный)
 */
export function resolveUrl(path: string): string {
  // Если путь уже абсолютный — возвращаем как есть
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  // Если путь не начинается с "/", добавляем слэш
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  return `${API_URL}${normalizedPath}`;
}

