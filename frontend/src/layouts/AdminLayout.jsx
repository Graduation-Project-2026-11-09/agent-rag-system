import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Sparkles, Inbox, FileText, Upload, Megaphone, BellRing, Users, UserPlus, History, MessageSquare, LogOut, Menu } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { ROLES } from '../constants';

const NAV = [
  { section: '業務', items: [{ to: '/admin/inquiries', label: '問い合わせ管理', icon: Inbox, roles: ['admin', 'staff'] }] },
  {
    section: 'ドキュメント',
    items: [
      { to: '/admin/documents', label: '資料一覧', icon: FileText, roles: ['admin', 'staff'], end: true },
      { to: '/admin/documents/upload', label: '資料アップロード', icon: Upload, roles: ['admin', 'staff'] },
    ],
  },
  {
    section: 'お知らせ・通知',
    items: [
      { to: '/admin/notices', label: 'お知らせ配信', icon: Megaphone, roles: ['admin', 'staff'] },
      { to: '/admin/notification-settings', label: '通知設定', icon: BellRing, roles: ['admin'] },
    ],
  },
  {
    section: 'アカウント',
    items: [
      { to: '/admin/accounts', label: 'アカウント管理', icon: Users, roles: ['admin'], end: true },
      { to: '/admin/accounts/new', label: 'アカウント作成', icon: UserPlus, roles: ['admin'] },
    ],
  },
  { section: '分析', items: [{ to: '/admin/logs', label: '利用履歴', icon: History, roles: ['admin'] }] },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="admin-shell">
      <aside className={`admin-sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark sm"><Sparkles size={16} /></span>
          社内ナビAI <span className="badge badge-blue">管理</span>
        </div>
        <nav className="admin-nav">
          {NAV.map((group) => {
            const items = group.items.filter((i) => i.roles.includes(user.role));
            if (!items.length) return null;
            return (
              <div key={group.section} className="nav-group">
                <p className="nav-label">{group.section}</p>
                {items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink key={to} to={to} end={end} className="side-link">
                    <Icon size={16} /> {label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <NavLink to="/chat" className="side-link"><MessageSquare size={16} /> チャット画面へ</NavLink>
          <div className="user-chip">
            <span className="avatar">{user.name[0]}</span>
            <div className="user-chip-text">
              <strong>{user.name}</strong>
              <span>{ROLES[user.role].label}{user.role === 'staff' && `（${user.handlesDepartment}）`}</span>
            </div>
            <button className="icon-btn" onClick={logout} title="ログアウト"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}
      <main className="admin-main">
        <button className="icon-btn mobile-only admin-menu-btn" onClick={() => setOpen(true)} aria-label="メニュー"><Menu size={18} /></button>
        <Outlet />
      </main>
    </div>
  );
}
