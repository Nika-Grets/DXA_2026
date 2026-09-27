/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect } from 'react';
import { getCachedFile } from '../utils/fileCache';

/**
 * Хук для получения локально закэшированного DICOM-файла
 * по studyId. Возвращает файл асинхронно из IndexedDB.
 */
export function useFileCache(studyId: string | undefined) {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!studyId) {
      setFile(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);

    getCachedFile(studyId)
      .then((cached) => {
        if (!cancelled) {
          setFile(cached ?? null);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFile(null);
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [studyId]);

  return { file, isLoading };
}