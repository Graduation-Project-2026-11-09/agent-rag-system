import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { formatRelative } from '../utils/format';

export default function NoticeBell({ notices, onRead }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const unread = notices.filter((n) => !n.read).length;

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div className="bell" ref={ref}>
      <button className="icon-btn" onClick={() => setOpen((v) => !v)} aria-label="お知らせ">
        <Bell size={18} />
        {unread > 0 && <span className="bell-dot">{unread}</span>}
      </button>
      {open && (
        <div className="dropdown bell-panel">
          <p className="dropdown-title">お知らせ</p>
          {notices.slice(0, 5).map((n) => (
            <button key={n.id} className={`bell-item ${n.read ? '' : 'unread'}`} onClick={() => onRead(n.id)}>
              <span className="bell-item-title">
                {n.priority === 'important' && <span className="badge badge-red">重要</span>} {n.title}
              </span>
              <span className="muted small">{formatRelative(n.publishAt)}</span>
            </button>
          ))}
          {!notices.length && <p className="muted small pad">お知らせはありません</p>}
          <Link to="/notices" className="dropdown-footer" onClick={() => setOpen(false)}>すべて見る</Link>
        </div>
      )}
    </div>
  );
}
