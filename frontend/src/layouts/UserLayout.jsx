import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useMatch, useNavigate } from 'react-router-dom';
import { Sparkles, SquarePen, MessageSquare, Mail, Bell, Settings, LogOut, Trash2, Menu, X } from 'lucide-react';
import { chatApi, noticeApi } from '../api';
import { useAuth } from '../contexts/AuthContext';
import NoticeBell from '../components/NoticeBell';

function groupConversations(list) {
  const today = new Date().toDateString();
  const weekAgo = Date.now() - 7 * 86400000;
  const groups = { 今日: [], '過去7日間': [], それ以前: [] };
  list.forEach((c) => {
    const t = Date.parse(c.updatedAt);
    if (new Date(t).toDateString() === today) groups['今日'].push(c);
    else if (t > weekAgo) groups['過去7日間'].push(c);
    else groups['それ以前'].push(c);
  });
  return Object.entries(groups).filter(([, v]) => v.length);
}

export default function UserLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const conversationId = useMatch('/chat/:conversationId')?.params.conversationId;
  const [conversations, setConversations] = useState([]);
  const [notices, setNotices] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const reloadConversations = useCallback(() => chatApi.listConversations().then(setConversations), []);
  const reloadNotices = useCallback(() => noticeApi.listMine().then(setNotices), []);

  useEffect(() => {
    reloadConversations();
    reloadNotices();
  }, [reloadConversations, reloadNotices]);

  useEffect(() => setSidebarOpen(false), [location.pathname]);

  const markRead = async (id) => {
    await noticeApi.markRead(id);
    reloadNotices();
  };

  const removeConversation = async (e, id) => {
    e.preventDefault();
    e.stopPropagation();
    await chatApi.deleteConversation(id);
    await reloadConversations();
    if (id === conversationId) navigate('/chat');
  };

  const importantUnread = notices.find((n) => n.priority === 'important' && !n.read);

  return (
    <div className="user-shell">
      <aside className={`user-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark sm"><Sparkles size={16} /></span>
            社内ナビAI
            <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(false)} aria-label="閉じる"><X size={18} /></button>
          </div>
          <button className="btn btn-block new-chat" onClick={() => navigate('/chat')}>
            <SquarePen size={16} /> 新しいチャット
          </button>
        </div>

        <nav className="history">
          {groupConversations(conversations).map(([label, items]) => (
            <div key={label} className="history-group">
              <p className="history-label">{label}</p>
              {items.map((c) => (
                <NavLink key={c.id} to={`/chat/${c.id}`} className="history-item">
                  <MessageSquare size={14} />
                  <span className="truncate">{c.title}</span>
                  <button className="history-delete" onClick={(e) => removeConversation(e, c.id)} aria-label="削除"><Trash2 size={14} /></button>
                </NavLink>
              ))}
            </div>
          ))}
          {!conversations.length && <p className="history-empty">まだ会話はありません</p>}
        </nav>

        <div className="sidebar-bottom">
          <NavLink to="/inquiries" className="side-link"><Mail size={16} /> 問い合わせ履歴</NavLink>
          <NavLink to="/notices" className="side-link"><Bell size={16} /> お知らせ</NavLink>
          {user.role !== 'user' && <NavLink to="/admin" className="side-link"><Settings size={16} /> 管理画面へ</NavLink>}
          <div className="user-chip">
            <span className="avatar">{user.name[0]}</span>
            <div className="user-chip-text">
              <strong>{user.name}</strong>
              <span>{user.department}</span>
            </div>
            <button className="icon-btn" onClick={logout} title="ログアウト"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
      {sidebarOpen && <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} />}

      <div className="user-main">
        <header className="user-header">
          <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="メニュー"><Menu size={18} /></button>
          <span className="header-title truncate">
            {conversations.find((c) => c.id === conversationId)?.title ?? ''}
          </span>
          <NoticeBell notices={notices} onRead={markRead} />
        </header>
        {importantUnread && (
          <div className="notice-banner">
            <span className="badge badge-red">重要</span>
            <span className="truncate">{importantUnread.title}</span>
            <button className="link-btn" onClick={() => navigate('/notices')}>詳細</button>
            <button className="icon-btn" onClick={() => markRead(importantUnread.id)} aria-label="閉じる"><X size={14} /></button>
          </div>
        )}
        <Outlet context={{ reloadConversations, notices, markRead }} />
      </div>
    </div>
  );
}
