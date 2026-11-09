import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Bell } from 'lucide-react';
import Badge from '../../components/common/Badge';
import EmptyState from '../../components/common/EmptyState';
import { formatDateTime } from '../../utils/format';

export default function NoticesPage() {
  const { notices, markRead } = useOutletContext();
  const [openId, setOpenId] = useState(null);

  const toggle = (n) => {
    setOpenId(openId === n.id ? null : n.id);
    if (!n.read) markRead(n.id);
  };

  return (
    <div className="user-page">
      <h1>お知らせ</h1>
      {!notices.length && <EmptyState icon={Bell} title="お知らせはありません" />}
      <div className="card-list">
        {notices.map((n) => (
          <div key={n.id} className={`card notice-card ${n.read ? '' : 'unread'}`}>
            <button className="notice-head" onClick={() => toggle(n)}>
              {!n.read && <span className="unread-dot" />}
              {n.priority === 'important' && <Badge tone="red">重要</Badge>}
              <strong className="grow">{n.title}</strong>
              <span className="muted small nowrap">{formatDateTime(n.publishAt)}</span>
            </button>
            {openId === n.id && <p className="notice-body pre-wrap">{n.body}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
