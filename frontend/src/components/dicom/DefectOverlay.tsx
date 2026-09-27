import type { components } from '../../api/schema';
import "./DefectOverlay.css";

type Defect = components['schemas']['Defect'];

interface Props {
  defects: Defect[];
  activeDefect?: Defect;
  onSelect: (defect: Defect) => void;
}

export function DefectOverlay({
  defects,
  activeDefect,
  onSelect,
}: Props) {
  return (
    <svg
      className="defect-overlay"
      viewBox="0 0 1000 1000"
      preserveAspectRatio="none"
    >
      {defects.map((defect, index) => {
        const roi = defect.roi;

        if (roi.type !== 'bbox') {
          return null;
        }

        const active = activeDefect === defect;

        return (
          <g
            key={`${defect.image_id}-${index}`}
            onClick={() => onSelect(defect)}
            style={{ cursor: 'pointer' }}
          >
            <rect
              x={roi.x * 1000}
              y={roi.y * 1000}
              width={roi.width * 1000}
              height={roi.height * 1000}
              fill="none"
              stroke={active ? '#facc15' : '#ef4444'}
              strokeWidth={active ? 5 : 3}
            />

            <text
              x={roi.x * 1000}
              y={Math.max(20, roi.y * 1000 - 8)}
              fill="#ffffff"
              stroke="#000000"
              strokeWidth="1"
              paintOrder="stroke"
              fontSize="22"
            >
              {defect.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}