import type { components } from '../api/schema';

type Defect = components['schemas']['Defect'];

interface Props {
  defects: Defect[];
  onSelect: (defect: Defect) => void;
}

export function DefectList({
  defects,
  onSelect,
}: Props) {
  if (defects.length === 0) {
    return (
      <div className="defect-list__empty">
        Дефекты не обнаружены
      </div>
    );
  }

  return (
    <div className="defect-list">
      {defects.map((defect, index) => (
        <button
          key={`${defect.image_id}-${index}`}
          className="defect-list__item"
          onClick={() => onSelect(defect)}
        >
          <div>
            <strong>{defect.label}</strong>

            <div className="defect-list__type">
              Тип: {defect.type}
            </div>
          </div>

          <span>
            {Math.round(defect.confidence * 100)}%
          </span>
        </button>
      ))}
    </div>
  );
}