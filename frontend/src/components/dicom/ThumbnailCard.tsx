import { useEffect, useState } from 'react';
import { Tag, Spin } from 'antd';
import { FileImageOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { loadPreviewBlob } from '../../api/studies';
import type { components } from '../../api/schema';
import './ThumbnailCard.css';

type ImageSummary = components['schemas']['ImageSummary'];

interface Props { image: ImageSummary; isActive: boolean; onClick: () => void; }

export function ThumbnailCard({ image, isActive, onClick }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null); setLoading(true); setHasError(false);
    loadPreviewBlob(image.preview_url)
      .then((url) => { objectUrl = url; if (!cancelled) setSrc(url); else URL.revokeObjectURL(url); })
      .catch(() => { if (!cancelled) setHasError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [image.preview_url]);

  const isMultiFrame = image.frames > 1;
  const modality = (image.metadata?.Modality as string) ?? 'IMG';

  return (
    <div className={`thumbnail-card ${isActive ? 'thumbnail-card--active' : ''}`} onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}>
      <div className="thumbnail-card__image-wrapper">
        {loading && !hasError && <div className="thumbnail-card__loader"><Spin size="small" /></div>}
        {hasError ? <div className="thumbnail-card__error"><FileImageOutlined /><span>Нет превью</span></div> : src && <img src={src} alt={`Снимок ${image.image_id.slice(0, 8)}`} className="thumbnail-card__image" draggable={false} />}
        {isMultiFrame && <div className="thumbnail-card__frames-badge"><PlayCircleOutlined /><span>{image.frames}</span></div>}
      </div>
      <div className="thumbnail-card__info">
        <Tag color="blue" className="thumbnail-card__modality">{modality}</Tag>
        <span className="thumbnail-card__id" title={image.image_id}>{image.image_id.slice(0, 8)}</span>
      </div>
    </div>
  );
}
