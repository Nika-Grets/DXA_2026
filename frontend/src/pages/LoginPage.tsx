import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { BackendError } from '../api/client';
import { useAuth } from '../auth/AuthContext';

const { Title, Text } = Typography;

type Mode = 'login' | 'register';

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('login');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const submit = async (values: { email: string; password: string; fullName?: string }) => {
    setError(null);
    setBusy(true);
    try {
      if (mode === 'register') {
        await register(values.email, values.fullName ?? '', values.password);
      } else {
        await login(values.email, values.password);
      }
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof BackendError ? err.message : 'Не удалось выполнить вход');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <Card className="login-card">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2} style={{ marginBottom: 4 }}>DEXA Quality Check</Title>
            <Text type="secondary">Вход в систему проверки качества DICOM-исследований</Text>
          </div>

          {error && <Alert type="error" showIcon message={error} />}

          <Form layout="vertical" onFinish={submit} requiredMark={false}>
            {mode === 'register' && (
              <Form.Item label="ФИО" name="fullName" rules={[{ required: true, min: 2, message: 'Введите ФИО' }]}>
                <Input autoComplete="name" />
              </Form.Item>
            )}
            <Form.Item label="Email" name="email" rules={[{ required: true, type: 'email', message: 'Введите корректный email' }]}>
              <Input autoComplete="email" />
            </Form.Item>
            <Form.Item label="Пароль" name="password" rules={[{ required: true, min: mode === 'register' ? 12 : 1, message: mode === 'register' ? 'Минимум 12 символов' : 'Введите пароль' }]}>
              <Input.Password autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>
              {mode === 'login' ? 'Войти' : 'Создать аккаунт'}
            </Button>
          </Form>

          <Button type="link" block onClick={() => { setError(null); setMode(mode === 'login' ? 'register' : 'login'); }}>
            {mode === 'login' ? 'Нет аккаунта? Зарегистрироваться' : 'Уже есть аккаунт? Войти'}
          </Button>
        </Space>
      </Card>
    </div>
  );
}
