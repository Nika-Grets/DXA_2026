import { Empty } from 'antd';
import { ThumbnailCard } from './ThumbnailCard';
import type { components } from '../../api/schema';
import './ImageThumbnails.css';

type ImageSummary = components['schemas']['ImageSummary'];
interface Props {
  images: ImageSummary[];
  activeId: string | null;
  onSelect: (imageId: string) => void;
}

export function ImageThumbnails({ images, activeId, onSelect }: Props) {
  if (images.length === 0) {
    return (
      <div className="thumbnails-container">
        <Empty description="Нет изображений" />
      </div>
    );
  }

  return (
    <div className="thumbnails-container">
      <div className="thumbnails-header">
        <span className="thumbnails-header__title">Изображения</span>
        <span className="thumbnails-header__count">{images.length}</span>
      </div>

      <div className="thumbnails-grid" role="list">
        {images.map((image) => (
          <ThumbnailCard
            key={image.image_id}
            image={image}
            isActive={image.image_id === activeId}
            onClick={() => onSelect(image.image_id)}
          />
        ))}
      </div>
    </div>
  );
}