import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Spinner from './components/common/Spinner';
import LoginPage from './pages/LoginPage';
import UserLayout from './layouts/UserLayout';
import AdminLayout from './layouts/AdminLayout';
import ChatPage from './pages/user/ChatPage';
import MyInquiriesPage from './pages/user/MyInquiriesPage';
import NoticesPage from './pages/user/NoticesPage';
import AccountsPage from './pages/admin/AccountsPage';
import AccountCreatePage from './pages/admin/AccountCreatePage';
import DocumentsPage from './pages/admin/DocumentsPage';
import DocumentUploadPage from './pages/admin/DocumentUploadPage';
import NoticesAdminPage from './pages/admin/NoticesAdminPage';
import NoticeFormPage from './pages/admin/NoticeFormPage';
import NotificationSettingsPage from './pages/admin/NotificationSettingsPage';
import InquiriesAdminPage from './pages/admin/InquiriesAdminPage';
import InquiryDetailPage from './pages/admin/InquiryDetailPage';
import LogsPage from './pages/admin/LogsPage';

function RequireAuth({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/chat" replace />;
  return children;
}

function AdminHome() {
  const { user } = useAuth();
  return <Navigate to={user.role === 'admin' ? '/admin/accounts' : '/admin/inquiries'} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* 利用者画面 */}
      <Route element={<RequireAuth><UserLayout /></RequireAuth>}>
        <Route path="/chat/:conversationId?" element={<ChatPage />} />
        <Route path="/inquiries" element={<MyInquiriesPage />} />
        <Route path="/notices" element={<NoticesPage />} />
      </Route>

      {/* 管理画面（管理者・部署担当者） */}
      <Route path="/admin" element={<RequireAuth roles={['admin', 'staff']}><AdminLayout /></RequireAuth>}>
        <Route index element={<AdminHome />} />
        <Route path="inquiries" element={<InquiriesAdminPage />} />
        <Route path="inquiries/:id" element={<InquiryDetailPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="documents/upload" element={<DocumentUploadPage />} />
        <Route path="notices" element={<NoticesAdminPage />} />
        <Route path="notices/new" element={<NoticeFormPage />} />
        <Route path="notices/:id/edit" element={<NoticeFormPage />} />
        <Route path="accounts" element={<RequireAuth roles={['admin']}><AccountsPage /></RequireAuth>} />
        <Route path="accounts/new" element={<RequireAuth roles={['admin']}><AccountCreatePage /></RequireAuth>} />
        <Route path="notification-settings" element={<RequireAuth roles={['admin']}><NotificationSettingsPage /></RequireAuth>} />
        <Route path="logs" element={<RequireAuth roles={['admin']}><LogsPage /></RequireAuth>} />
      </Route>

      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
