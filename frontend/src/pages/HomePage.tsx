import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LoadingOutlined,
  FileOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import {
  Upload,
  Progress,
  Typography,
  Alert,
  Space,
  Card,
  Result,
  Button,
  Divider,
} from 'antd';
import type { UploadProps } from 'antd';
import { uploadStudy } from '../api/studies';
import { BackendError } from '../api/client';
import { getUserFriendlyMessage } from '../api/errors';
import { validateFile } from '../utils/fileValidation';
import {
  savePendingFile,
  promotePendingFile,
} from '../utils/fileCache';
import cloud_upload_icon from '../assets/cloud_upload_icon.png';
import './HomePage.css'


const { Dragger } = Upload;
const { Title, Text } = Typography;

type UploadState =
  | {
      phase: 'idle';
    }
  | {
      phase: 'uploading';
      progress: number;
      fileName: string;
      fileSize: number;
    }
  | {
      phase: 'success';
      studyId: string;
      fileName: string;
    }
  | {
      phase: 'error';
      message: string;
      fileName?: string;
    };

export default function HomePage() {
  const navigate = useNavigate();

  const [state, setState] = useState<UploadState>({
    phase: 'idle',
  });

  //Обработка выбранного DICOM-файла.

  const handleBeforeUpload = useCallback(
    async (file: File): Promise<false> => {

      const validationError = validateFile(file);

      if (validationError) {
        setState({
          phase: 'error',
          message: validationError.message,
          fileName: file.name,
        });

        return false;
      }

      try {
        await savePendingFile(file);
      } catch (error) {
        console.error(
          'Не удалось сохранить DICOM-файл в IndexedDB:',
          error,
        );
      }

      setState({
        phase: 'uploading',
        progress: 0,
        fileName: file.name,
        fileSize: file.size,
      });

      // Отправляем файл на Backend

      try {
        const study = await uploadStudy(
          file,
          (progress) => {
            setState((previousState) => {
              if (previousState.phase !== 'uploading') {
                return previousState;
              }

              return {
                ...previousState,
                progress,
              };
            });
          },
        );

        // После получения study_id переносим файл из временного ключа в постоянный

        await promotePendingFile(study.study_id);

        setState({
          phase: 'success',
          studyId: study.study_id,
          fileName: file.name,
        });

        setTimeout(() => {
          navigate(`/study/${study.study_id}`);
        }, 600);
      } catch (error) {
        console.error('Ошибка загрузки DICOM:', error);

        const message =
          error instanceof BackendError
            ? getUserFriendlyMessage(error)
            : 'Не удалось загрузить файл. Проверьте соединение и попробуйте снова.';

        setState({
          phase: 'error',
          message,
          fileName: file.name,
        });
      }
      return false;
    },
    [navigate],
  );

  //Сброс состояния после ошибки.
  const handleReset = useCallback(() => {
    setState({
      phase: 'idle',
    });
  }, []);


 // const handleOpenStudy = useCallback(() => {
 //   if (state.phase !== 'success') {
 //     return;
 //   }

 //   navigate(`/study/${state.studyId}`);
 // }, [navigate, state]);

  // Форматирование размера файла.
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) {
      return `${bytes} Б`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} КБ`;
    }

    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  };

  return (
  <div className="home-page">
    <Card className="home-page__card">
      <Space
        direction="vertical"
        size="large"
        className="home-page__content"
      >
        {/* Заголовок страницы */}

        <div className="home-page__header">
          <Title level={2} className="home-page__title">
            Загрузка исследований
          </Title>

          <Text type="secondary">
            Загрузите DICOM-исследование для проверки качества
            снимков
          </Text>
        </div>

        {/* IDLE */}

        {state.phase === 'idle' && (
          <>
            <Dragger
              className="home-page__dragger"
              accept=".dcm,.dicom,.zip,application/dicom,application/zip"
              multiple={false}
              showUploadList={false}
              beforeUpload={
                handleBeforeUpload as UploadProps['beforeUpload']
              }
              disabled={false}
            >
              <p className="ant-upload-drag-icon">
                <img style={{ position: 'relative', top: '11px' }} src={cloud_upload_icon} alt="upload icon" height="78px" width="78px" ></img>
              </p>

              <p className="ant-upload-text">
                Перетащите исследование сюда
              </p>

              <p className="ant-upload-text">
                или
              </p>

              <Button
                type="primary"
                icon={<FileOutlined />}
              >
                Выбрать файл
              </Button>

              <p className="ant-upload-hint home-page__upload-hint">
                Поддерживаются DICOM-файлы
                <br />

                <Text type="secondary">
                  .dcm, .dicom
                </Text>

                {' '}и{' '}

                <Text type="secondary">
                  .zip
                </Text>
              </p>

              <Text type="secondary">
                Максимальный размер: 500 МБ
              </Text>
            </Dragger>

            <Divider />

            <Alert
              className="home-page__alert"
              type="info"
              showIcon
              message="Поддерживаемые исследования"
              description="DEXA, позвоночный отдел (L1–L4), проксимальный отдел бедра."
            />
          </>
        )}

        {/* загрузка */}

        {state.phase === 'uploading' && (
          <Card
            bordered
            className="home-page__upload-card"
          >
            <Space
              direction="vertical"
              size="middle"
              className="home-page__upload-content"
            >
              <LoadingOutlined className="home-page__loading-icon" />

              <div>
                <Text strong>
                  Загружаем исследование
                </Text>

                <br />

                <Text type="secondary">
                  {state.fileName}
                </Text>

                <br />

                <Text type="secondary">
                  {formatFileSize(state.fileSize)}
                </Text>
              </div>

              <Progress
                className="home-page__progress"
                percent={state.progress}
                status={
                  state.progress < 100
                    ? 'active'
                    : 'success'
                }
              />

              <Text type="secondary">
                {state.progress < 100
                  ? `Загрузка на сервер — ${state.progress}%`
                  : 'Файл передан, обрабатываем исследование…'}
              </Text>
            </Space>
          </Card>
        )}

        {/* success */}

        {state.phase === 'success' && (
          <Card className="home-page__result-card">
            <Result
              status="success"
              icon={<CheckCircleOutlined />}
              title="Исследование загружено"
              subTitle={
                <>
                  Файл{' '}
                  <Text strong>
                    {state.fileName}
                  </Text>{' '}
                  успешно загружен.

                  <br />

                  Исследование распознано и готово
                  к проверке.
                </>
              }
             
            />
          </Card>
        )}

        {/* ошибка */}

        {state.phase === 'error' && (
          <Card className="home-page__result-card">
            <Result
              status="error"
              icon={<CloseCircleOutlined />}
              title="Не удалось загрузить исследование"
              subTitle={
                state.fileName
                  ? `Файл: ${state.fileName}`
                  : undefined
              }
              extra={
                <Button
                  type="primary"
                  onClick={handleReset}
                >
                  Попробовать снова
                </Button>
              }
            />

            <Alert
              className="home-page__error-alert"
              type="error"
              showIcon
              message="Ошибка загрузки"
              description={state.message}
            />
          </Card>
        )}
      </Space>
    </Card>
  </div>
);
}