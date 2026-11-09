import { useState } from 'react';
import { ChevronDown, Mail } from 'lucide-react';
import { inquiryApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/common/Badge';
import EmptyState from '../../components/common/EmptyState';
import Spinner from '../../components/common/Spinner';
import { INQUIRY_STATUS } from '../../constants';
import { formatDateTime } from '../../utils/format';

export default function MyInquiriesPage() {
  const { data, loading } = useFetch(() => inquiryApi.listMine(), []);
  const [openId, setOpenId] = useState(null);

  return (
    <div className="user-page">
      <h1>問い合わせ履歴</h1>
      <p className="muted">AIのチャットから担当部署へ送信した問い合わせと、その回答を確認できます。</p>

      {loading && <Spinner />}
      {data && !data.length && <EmptyState icon={Mail} title="問い合わせはまだありません">AIが社内資料だけでは解決できないと判断した場合に、チャットから問い合わせを作成できます。</EmptyState>}

      <div className="card-list">
        {data?.map((q) => {
          const open = openId === q.id;
          return (
            <div key={q.id} className="card inquiry-card">
              <button className="inquiry-head" onClick={() => setOpenId(open ? null : q.id)}>
                <div className="inquiry-head-main">
                  <span className="row gap-sm">
                    <StatusBadge map={INQUIRY_STATUS} value={q.status} />
                    <span className="muted small">{q.number}・{q.department}</span>
                  </span>
                  <strong>{q.subject}</strong>
                </div>
                <span className="muted small nowrap">{formatDateTime(q.createdAt)}</span>
                <ChevronDown size={16} className={`chev ${open ? 'up' : ''}`} />
              </button>
              {open && (
                <div className="inquiry-detail">
                  <p className="section-label">送信した内容</p>
                  <pre className="preview-body">{q.body}</pre>
                  <p className="section-label">担当部署からの回答</p>
                  {q.replies.length ? (
                    q.replies.map((r) => (
                      <div key={r.id} className="reply">
                        <div className="reply-head">
                          <strong>{r.author}</strong>
                          <span className="muted small">{q.department}・{formatDateTime(r.createdAt)}</span>
                        </div>
                        <p className="pre-wrap">{r.body}</p>
                      </div>
                    ))
                  ) : (
                    <p className="muted small">まだ回答はありません。回答があると通知されます。</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
