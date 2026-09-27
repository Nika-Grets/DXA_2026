import { useEffect, useState } from 'react';
import { loadPreviewBlob } from '../../api/studies';
import './DicomViewer.css';

interface Props {
  previewUrl?: string;
  imageLabel?: string;
}

export default function DicomViewer({ previewUrl, imageLabel }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(previewUrl));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    setError(null);
    setLoading(Boolean(previewUrl));

    if (!previewUrl) return () => { cancelled = true; };

    loadPreviewBlob(previewUrl)
      .then((url) => {
        objectUrl = url;
        if (!cancelled) setSrc(url);
        else URL.revokeObjectURL(url);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Не удалось загрузить preview изображения');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [previewUrl]);

  return (
    <div className="dicom-viewer">
      <div className="dicom-viewer__toolbar">
        {!loading && src && !error && <span className="dicom-viewer__status">Изображение загружено</span>}
      </div>
      <div className="dicom-viewer__canvas">
        {!previewUrl && <div className="dicom-viewer__placeholder">Изображение не выбрано</div>}
        {loading && <div className="dicom-viewer__placeholder">Загрузка изображения...</div>}
        {src && !loading && <img className="dicom-viewer__image" src={src} alt={imageLabel ?? 'DICOM preview'} draggable={false} />}
        {error && <div className="dicom-viewer__error">{error}</div>}
      </div>
    </div>
  );
}
