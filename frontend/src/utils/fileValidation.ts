export type ValidationError = {
  code: 'INVALID_EXTENSION' | 'INVALID_TYPE' | 'TOO_SMALL';
  message: string;
};

const ALLOWED_EXTENSIONS = ['.dcm', '.dicom', '.zip'];
const ALLOWED_MIME_TYPES = [
  'application/dicom',
  'application/zip',
  'application/x-zip-compressed',
  'application/octet-stream', // fallback — некоторые ОС отдают его для .dcm
];
const MIN_FILE_SIZE = 1024; // 1 КБ — DICOM меньше не бывает

/**
 * Валидирует файл на клиенте. Возвращает null, если всё ок.
 */
export function validateFile(file: File): ValidationError | null {
  // 1. Проверяем расширение
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return {
      code: 'INVALID_EXTENSION',
      message: `Неподдерживаемое расширение "${ext}". Ожидаются: ${ALLOWED_EXTENSIONS.join(', ')}`,
    };
  }

  // 2. Проверяем MIME-тип (мягкая проверка — браузеры иногда отдают странные типы)
  if (file.type && !ALLOWED_MIME_TYPES.includes(file.type)) {
    return {
      code: 'INVALID_TYPE',
      message: `Неподдерживаемый MIME-тип "${file.type}"`,
    };
  }

  // 3. Минимальный размер
  if (file.size < MIN_FILE_SIZE) {
    return {
      code: 'TOO_SMALL',
      message: 'Файл слишком мал и, скорее всего, повреждён',
    };
  }

  return null;
}