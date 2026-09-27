import { Layout, Typography, Button, Space } from 'antd';
import { Outlet, Link } from 'react-router-dom';
import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import logo from '../assets/logo.png';
import { useAuth } from '../auth/AuthContext';

const { Header, Content } = Layout;

export default function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <Layout style={{ height: '100vh', minHeight: 0, overflow: 'hidden' }}>
      <Header className="app-header">
        <Link to="/" className="app-header__logo">
          <img src={logo} alt="DEXA quality check" />
        </Link>
        <Space>
          <Typography.Text className="app-header__user"><UserOutlined /> {user?.full_name}</Typography.Text>
          <Button type="text" icon={<LogoutOutlined />} onClick={() => void logout()} className="app-header__logout">Выйти</Button>
        </Space>
      </Header>
      <Content><Outlet /></Content>
    </Layout>
  );
}
