import './QualityStatus.css';


interface QualityStatusProps {
  status: 'acceptable' | 'issue_detected';
  score: number | null;
}

export function QualityStatus({
  status,
  score,
}: QualityStatusProps) {
  const isAcceptable = status === 'acceptable';

  const scorePercent =
    score === null
      ? 0
      : Math.max(
          0,
          Math.min(100, score * 100)
        );

  return (
    <section
      className={`quality-status ${
        isAcceptable
          ? 'quality-status--success'
          : 'quality-status--warning'
      }`}
    >
      {/* Заголовок */}

      <div className="quality-status__heading">
        <strong>
          {isAcceptable
            ? 'Качество приемлемое'
            : 'Обнаружены дефекты'}
        </strong>

        <span>
          {score !== null
            ? `${Math.round(scorePercent)}%`
            : 'Нет оценки'}
        </span>
      </div>


      {/* Progress bar */}

      <div className="quality-status__bar">
        <div
          className="quality-status__bar-fill"
          style={{
            width: `${scorePercent}%`,
          }}
        />
      </div>


      {/* Описание */}

      <p className="quality-status__description">
        {isAcceptable
          ? 'Существенных проблем качества не обнаружено.'
          : 'Требуется проверка обнаруженных дефектов.'}
      </p>
    </section>
  );
}