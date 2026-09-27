import { get, set, del } from 'idb-keyval';

const KEY_PREFIX = 'dicom:file:';
const TEMP_KEY = 'dicom:file:pending';

/**
 * Сохраняем файл во временное хранилище (до получения study_id).
 */
export async function savePendingFile(file: File): Promise<void> {
  await set(TEMP_KEY, file);
}

/**
 * Получаем временный файл.
 */
export async function getPendingFile(): Promise<File | undefined> {
  return await get<File>(TEMP_KEY);
}

/**
 * После успешной загрузки переносим файл под постоянный ключ study_id.
 */
export async function promotePendingFile(studyId: string): Promise<void> {
  const file = await getPendingFile();
  if (file) {
    await set(KEY_PREFIX + studyId, file);
    await del(TEMP_KEY);
  }
}

/**
 * Получаем локальный файл по study_id (для открытия в Cornerstone).
 */
export async function getCachedFile(studyId: string): Promise<File | undefined> {
  return await get<File>(KEY_PREFIX + studyId);
}

/**
 * Удаляем файл из кэша (при logout или очистке).
 */
export async function clearCachedFile(studyId: string): Promise<void> {
  await del(KEY_PREFIX + studyId);
}