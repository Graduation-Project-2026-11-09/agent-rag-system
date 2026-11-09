import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Pencil, Trash2, Mail, MonitorSmartphone } from 'lucide-react';
import { noticeApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import { NOTICE_PRIORITY, NOTICE_STATUS } from '../../constants';
import { formatDateTime, formatPercent, visibilityLabel } from '../../utils/format';

export default function NoticesAdminPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, reload } = useFetch(() => noticeApi.list(), []);
  const [status, setStatus] = useState('');
  const [target, setTarget] = useState(null);

  const list = data?.filter((n) => !status || n.status === status);

  const remove = async () => {
    await noticeApi.remove(target.id);
    setTarget(null);
    toast('お知らせを削除しました');
    reload();
  };

  return (
    <div className="admin-page">
      <PageHeader
        title="お知らせ配信"
        description="従業員のチャット画面・メールに配信するお知らせを管理します"
        actions={<Link to="/admin/notices/new" className="btn btn-primary"><Plus size={16} /> お知らせを作成</Link>}
      />
      <div className="tabs">
        {[['', 'すべて'], ...Object.entries(NOTICE_STATUS).map(([k, v]) => [k, v.label])].map(([k, label]) => (
          <button key={k} className={status === k ? 'active' : ''} onClick={() => setStatus(k)}>
            {label}
            <span className="tab-count">{data?.filter((n) => !k || n.status === k).length ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table className="table clickable">
          <thead>
            <tr><th>タイトル</th><th>配信対象</th><th>配信方法</th><th>状態</th><th>配信期間</th><th className="right">既読率</th><th className="right">操作</th></tr>
          </thead>
          <tbody>
            {list?.map((n) => (
              <tr key={n.id} onClick={() => navigate(`/admin/notices/${n.id}/edit`)}>
                <td>
                  <div className="row gap-sm">
                    {n.priority === 'important' && <StatusBadge map={NOTICE_PRIORITY} value="important" />}
                    <strong>{n.title}</strong>
                  </div>
                  <span className="muted small block">作成：{n.createdBy}</span>
                </td>
                <td>{visibilityLabel(n.target)}</td>
                <td className="nowrap">
                  {n.channels.includes('in_app') && <span title="画面内" className="channel"><MonitorSmartphone size={14} /></span>}
                  {n.channels.includes('email') && <span title="メール" className="channel"><Mail size={14} /></span>}
                </td>
                <td><StatusBadge map={NOTICE_STATUS} value={n.status} /></td>
                <td className="muted small">
                  {n.publishAt ? formatDateTime(n.publishAt) : '未設定'}
                  <br />〜 {n.expireAt ? formatDateTime(n.expireAt) : '無期限'}
                </td>
                <td className="right">{n.status === 'published' || n.status === 'expired' ? formatPercent(n.readCount / n.targetCount) : '—'}</td>
                <td className="right nowrap" onClick={(e) => e.stopPropagation()}>
                  <button className="icon-btn" title="編集" onClick={() => navigate(`/admin/notices/${n.id}/edit`)}><Pencil size={15} /></button>
                  <button className="icon-btn danger" title="削除" onClick={() => setTarget(n)}><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <Spinner />}
      </div>

      <ConfirmDialog
        open={!!target}
        title="お知らせを削除しますか？"
        message={`「${target?.title}」を削除します。配信中の場合は従業員の画面からも削除されます。`}
        confirmLabel="削除する"
        danger
        onConfirm={remove}
        onCancel={() => setTarget(null)}
      />
    </div>
  );
}
