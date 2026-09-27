/* eslint-disable react-hooks/set-state-in-effect */
import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState, useRef } from 'react';
import { Spin, Alert, Button, Space } from 'antd';
import { useReport } from '../hooks/useReport';
import { saveStudyCsvToFile } from '../api/studies';
import { useStudy } from '../hooks/useStudy';
import { usePredict } from '../hooks/usePredict';
import { ImageThumbnails } from '../components/dicom/ImageThumbnails';
import DicomViewer from '../components/dicom/DicomViewer';
import type { components } from '../api/schema';
import { DefectList } from '../components/DefectList';
import { QualityStatus } from '../components/QualityStatus';
import './StudyPage.css';

type Defect = components['schemas']['Defect'];
export default function StudyPage() {
  const navigate = useNavigate();
  const { studyId } = useParams<{ studyId: string }>();
   console.log('[StudyPage] studyId:', studyId);
  const { study, isLoading, error } = useStudy(studyId);
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [activeDefect, setActiveDefect] = useState<Defect | undefined>();
  const report = useReport({
    studyId,
    hasReport: study?.has_report ?? false,
  });
  const predictStartedRef = useRef<string | null>(null);

  const { mutate: runPredict, data: prediction, isPending: isPredicting, isLoading: isLoadingPrediction, mutationError } = usePredict({ studyId });

  useEffect(() => {
    if (
    studyId &&
      study?.status === 'parsed' &&
      !prediction &&
      !isLoadingPrediction &&
      !isPredicting &&
      predictStartedRef.current !== studyId
    ) {
      predictStartedRef.current = studyId;
      runPredict();
    }
  }, [
    studyId,
    study?.status,
    prediction,
    isLoadingPrediction,
    isPredicting,
  ]);

  useEffect(() => {
    if (!study?.images?.length) {
      setActiveImageId(null);
      return;}

    const stillExists = study.images.some(img => img.image_id === activeImageId);
    if (!stillExists) {
      setActiveImageId(study.images[0].image_id);
    }
  }, [study, activeImageId]);

  useEffect(() => {
    const defects = prediction?.defects ?? [];

    if (defects.length === 0) {
      setActiveDefect(undefined);
      return;
    }

    const currentStillExists = defects.some(
      (defect) =>
        defect === activeDefect
    );

    if (!currentStillExists) {
      setActiveDefect(defects[0]);
    }
  }, [prediction, activeDefect]);

  if (!studyId) {
    return <Alert type="error" message="Не указан ID исследования" />;
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Spin size="large" tip="Загрузка исследования..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="Ошибка загрузки"
          description={error.message}
          showIcon
        />
        
        <Button type="primary" onClick={() => navigate('/')} style={{ position: 'relative', top: '40px' }}>
          На главную
        </Button>
      </div>
    );
  }

  if (!study) {
    return <Alert type="warning" message="Исследование не найдено" showIcon />;
  }

  if (mutationError) {
    return <div style={{ padding: 24 }}><Alert type="error" showIcon message="Не удалось выполнить ML-анализ" description={mutationError.message} /><Button type="primary" onClick={() => runPredict()} style={{ marginTop: 16 }}>Повторить анализ</Button></div>;
  }

  const defects = prediction?.defects ?? [];

  const activeImage = study.images.find(
    (image) =>
      image.image_id === activeImageId
  );


  return (
  <div className="study-page">

    {/* левая панель */}

    <aside className="study-page__left-panel">
      <ImageThumbnails
        images={study.images}
        activeId={activeImageId}
        onSelect={(imageId) => {
          setActiveImageId(imageId);

          const selectedDefectBelongsToImage =
            activeDefect?.image_id === imageId;

          if (!selectedDefectBelongsToImage) {
            setActiveDefect(undefined);
          }
        }}
      />
    </aside>


    {/* dicom viewer */}

    <main className="study-page__main">

      {/* Верхняя информация Viewer */}

      <div className="study-page__viewer-header">

        <div className="study-page__viewer-title">
          <strong>DICOM Viewer</strong>
        </div>

        <div className="study-page__viewer-image-info">
          {activeImageId
            ? `Изображение: ${activeImageId.slice(0, 8)}`
            : 'Изображение не выбрано'}
        </div>

      </div>


      {/* Область изображения */}

      <div className="study-page__viewer-area">

        <DicomViewer
          previewUrl={activeImage?.preview_url}
          imageLabel={activeImage ? `DICOM ${activeImage.image_id}` : undefined}
        />

        {/* Информация о количестве дефектов */}

        {defects.length > 0 && (
          <div className="study-page__defects-counter">
            Дефектов: {defects.length}
          </div>
        )}

      </div>


      {/* Нижняя панель Viewer */}

      <div className="study-page__viewer-footer">
        {activeImage
          ? `${activeImage.frames} кадров`
          : 'Нет выбранного изображения'}
      </div>

    </main>


    {/* правая панель */}

    <aside className="study-page__right-panel">

      {/* Заголовок */}

      <div className="study-page__results-header">

        <h3 className="study-page__results-title">
          Результаты ML
        </h3>

        <div className="study-page__results-subtitle">
          Анализ качества исследования
        </div>

      </div>


      {/* Статус исследования */}

      <div className="study-page__study-status">

        <div className="study-page__study-status-label">
          Статус исследования
        </div>

        <strong>
          {study.status}
        </strong>

      </div>


      {/* качество статуса */}

      {isPredicting ? (
        <div className="study-page__no-prediction" style={{ textAlign: 'center', padding: '16px 0' }}>
          <Spin tip="Выполняется ML-анализ..." />
        </div>
      ) : prediction ? (
        <div className="study-page__quality-status">

          <QualityStatus
            status={prediction.quality_status}
            score={
              prediction.quality_score ?? null
            }
          />

        </div>
      ) : (
        <div className="study-page__no-prediction">

          Результат анализа ещё не получен.
          <Button 
            type="primary" 
            size="small" 
            style={{ marginTop: 8 }} 
            onClick={() => runPredict()}
          >
            Запустить анализ
          </Button>

        </div>
      )}

      {/* список дефектов */}

      <div className="study-page__defects-section">

        <div className="study-page__defects-header">

          <h4 className="study-page__defects-title">
            Обнаруженные дефекты
          </h4>

          <span className="study-page__defects-count">
            {defects.length}
          </span>

        </div>


        <DefectList
          defects={defects}
          onSelect={(defect) => {

            setActiveDefect(defect);

            setActiveImageId(defect.image_id);

          }}
        />

      </div>
      <div>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Button
            type="primary"
            block
            disabled={!study.has_prediction}
            onClick={() => {
              void saveStudyCsvToFile(
                study.study_id,
                `dexa-${study.study_id}-results.csv`,
              );
            }}
          >
            Скачать CSV-результаты
          </Button>
          <Button
            block
            loading={report.isGenerating}
            disabled={!study.has_prediction}
            onClick={() => report.generateAndDownload()}
          >
            {report.isGenerating
              ? 'Формирование отчёта...'
              : 'Скачать PDF-отчёт'}
          </Button>
        </Space>
        {report.reportError && (
          <Alert
            type="error"
            showIcon
            style={{ marginTop: 12 }}
            message="Не удалось сформировать отчёт"
            description={report.reportError.message}
          />
        )}
      </div>


      {prediction && activeImage && (() => {
        const imageResult = prediction.results?.find((item) => item.image_id === activeImage.image_id);
        if (!imageResult) return null;
        return (
          <div className="study-page__criteria">
            <div className="study-page__criteria-title">Критерии изображения</div>
            <div className="study-page__criteria-row"><span>Область</span><strong>{imageResult.anatomical_region}</strong></div>
            <div className="study-page__criteria-row"><span>Класс качества</span><strong>{imageResult.quality_class === 1 ? 'Нарушение' : 'Приемлемо'}</strong></div>
            {imageResult.violation_type?.length ? <div className="study-page__criteria-tags"><span>Нарушения</span>{imageResult.violation_type.map((item) => <span className="study-page__tag study-page__tag--danger" key={item}>{item}</span>)}</div> : null}
            {imageResult.findings?.length ? <div className="study-page__criteria-tags"><span>Находки</span>{imageResult.findings.map((item) => <span className="study-page__tag" key={item}>{item}</span>)}</div> : null}
          </div>
        );
      })()}

      {/* информация о модели */}

      {prediction && (
        <div className="study-page__model-info">

          <div className="study-page__model-title">
            <strong>ML-модель</strong>
          </div>

          <div className="study-page__model-row">
            Название:{' '}
            {prediction.model.name}
          </div>

          <div className="study-page__model-row">
            Версия:{' '}
            {prediction.model.version}
          </div>

        </div>
      )}

    </aside>

  </div>
  );
}