import { Inbox } from 'lucide-react';

export default function EmptyState({ icon: Icon = Inbox, title, children }) {
  return (
    <div className="empty-state">
      <Icon size={32} strokeWidth={1.5} />
      <p className="empty-title">{title}</p>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}
