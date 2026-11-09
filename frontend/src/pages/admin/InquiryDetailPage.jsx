import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Sparkles, FileText, Send } from 'lucide-react';
import { inquiryApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../contexts/ToastContext';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import { INQUIRY_STATUS } from '../../constants';
import { formatDateTime } from '../../utils/format';

export default function InquiryDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { data: q, setData } = useFetch(() => inquiryApi.get(id), [id]);
  const [reply, setReply] = useState('');
  const [resolveAfter, setResolveAfter] = useState(false);
  const [sending, setSending] = useState(false);

  if (!q) return <Spinner />;

  const update = async (patch, message) => {
    setData(await inquiryApi.update(id, patch));
    toast(message);
  };

  const sendReply = async () => {
    setSending(true);
    let next = await inquiryApi.reply(id, reply);
    if (resolveAfter) next = await inquiryApi.update(id, { status: 'resolved' });
    setData(next);
    setReply('');
    setSending(false);
    toast(`${q.userName} さんに回答を送信しました`);
  };

  return (
    <div className="admin-page">
      <Link to="/admin/inquiries" className="back-link"><ArrowLeft size={14} /> 問い合わせ一覧</Link>
      <div className="page-header">
        <div>
          <p className="muted small mono">{q.number}</p>
          <h1>{q.subject}</h1>
        </div>
        <StatusBadge map={INQUIRY_STATUS} value={q.status} />
      </div>

      <div className="detail-layout">
        <div className="stack">
          <div className="card">
            <div className="reply-head">
              <strong>{q.userName}（{q.userDepartment}）</strong>
              <span className="muted small">{formatDateTime(q.createdAt)}</span>
            </div>
            <pre className="preview-body plain">{q.body}</pre>
          </div>

          {q.replies.map((r) => (
            <div key={r.id} className="card reply-card">
              <div className="reply-head">
                <strong>{r.author}（{q.department}）</strong>
                <span className="muted small">{formatDateTime(r.createdAt)}</span>
              </div>
              <p className="pre-wrap">{r.body}</p>
            </div>
          ))}

          {q.status !== 'resolved' && (
            <div className="card stack-sm">
              <span className="field-label">回答を入力</span>
              <textarea className="input" rows={5} value={reply} onChange={(e) => setReply(e.target.value)} placeholder={`${q.userName} さんへの回答`} />
              <div className="row between">
                <label className="check"><input type="checkbox" checked={resolveAfter} onChange={(e) => setResolveAfter(e.target.checked)} /> 送信後に「解決済み」にする</label>
                <button className="btn btn-primary" disabled={!reply.trim() || sending} onClick={sendReply}><Send size={14} /> 回答を送信</button>
              </div>
            </div>
          )}
        </div>

        <aside className="stack">
          <div className="card stack-sm">
            <span className="field-label">対応状況</span>
            <select className="input" value={q.status} onChange={(e) => update({ status: e.target.value }, '対応状況を変更しました')}>
              {Object.entries(INQUIRY_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <span className="field-label">担当者</span>
            <div className="row gap-sm">
              <span className="grow">{q.assignee ?? <span className="muted">未割当</span>}</span>
              {q.assignee !== user.name && <button className="btn btn-sm" onClick={() => update({ assignee: user.name }, '担当者になりました')}>自分が担当</button>}
            </div>
            <dl className="meta-grid compact">
              <dt>宛先</dt><dd>{q.department}</dd>
              <dt>最終更新</dt><dd>{formatDateTime(q.updatedAt)}</dd>
            </dl>
          </div>

          <div className="card stack-sm ai-context">
            <p className="section-label"><Sparkles size={14} /> AIとのやり取り（自動添付）</p>
            <span className="field-label">元の質問</span>
            <p>{q.context.question}</p>
            {q.context.aiAnswerSummary && (
              <>
                <span className="field-label">AIの回答（要約）</span>
                <p className="muted">{q.context.aiAnswerSummary}</p>
              </>
            )}
            <span className="field-label">AIが確認した資料</span>
            {q.context.sources.length ? (
              <ul className="plain-list">
                {q.context.sources.map((s) => <li key={s}><FileText size={13} /> {s}</li>)}
              </ul>
            ) : (
              <p className="muted small">該当資料なし</p>
            )}
            <p className="muted small">同様の質問が多い場合は、資料の追加・更新をご検討ください。</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
