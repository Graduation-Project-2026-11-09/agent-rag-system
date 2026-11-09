import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Upload, Search, RefreshCw, Trash2, AlertCircle, Lock, Globe } from 'lucide-react';
import { documentApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useCategories, useDepartments } from '../../hooks/useMasters';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Modal from '../../components/common/Modal';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import FileIcon from '../../components/common/FileIcon';
import VisibilityEditor from '../../components/common/VisibilityEditor';
import Field from '../../components/common/Field';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import EmptyState from '../../components/common/EmptyState';
import { DOC_STATUS } from '../../constants';
import { formatDate, formatDateTime, formatFileSize, visibilityLabel } from '../../utils/format';

function VisibilityCell({ v }) {
  return v.type === 'all' ? (
    <span className="row gap-xs muted"><Globe size={13} /> 全社公開</span>
  ) : (
    <span className="row gap-xs"><Lock size={13} /> {v.departments.join('・')}</span>
  );
}

function DocumentDetailModal({ id, onClose, onChanged }) {
  const toast = useToast();
  const departments = useDepartments();
  const categories = useCategories();
  const { data: doc, reload } = useFetch(() => documentApi.get(id), [id]);
  const [form, setForm] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (doc) setForm({ title: doc.title, category: doc.category, department: doc.department, visibility: doc.visibility, tags: doc.tags.join(', ') });
  }, [doc]);

  if (!doc || !form) return null;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async () => {
    if (form.visibility.type === 'departments' && !form.visibility.departments.length) return toast('公開する部署を1つ以上選択してください', 'error');
    await documentApi.update(id, { ...form, tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean) });
    toast('資料情報を更新しました');
    onChanged();
    reload();
  };
  const reindex = async () => {
    await documentApi.reindex(id);
    toast('再インデックスを開始しました');
    onChanged();
    onClose();
  };
  const remove = async () => {
    await documentApi.remove(id);
    toast('資料を削除しました。今後の回答には使用されません');
    onChanged();
    onClose();
  };

  return (
    <Modal
      open
      size="lg"
      title={<span className="row gap-sm"><FileIcon type={doc.fileType} /> {doc.title}</span>}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-danger-ghost" onClick={() => setConfirmDelete(true)}><Trash2 size={14} /> 削除</button>
          <span className="grow" />
          <button className="btn" onClick={reindex}><RefreshCw size={14} /> 再インデックス</button>
          <button className="btn btn-primary" onClick={save}>変更を保存</button>
        </>
      }
    >
      {doc.status === 'error' && <p className="warn-box error"><AlertCircle size={14} /> {doc.errorMessage}</p>}
      <dl className="meta-grid">
        <dt>ファイル名</dt><dd>{doc.fileName}（{formatFileSize(doc.size)}・{doc.pages}ページ）</dd>
        <dt>状態</dt><dd><StatusBadge map={DOC_STATUS} value={doc.status} /> {doc.status === 'indexed' && <span className="muted small">チャンク数 {doc.chunks}</span>}</dd>
        <dt>施行日</dt><dd>{formatDate(doc.effectiveDate)}</dd>
        <dt>登録者</dt><dd>{doc.uploadedBy}（{formatDateTime(doc.updatedAt)}）</dd>
      </dl>

      <div className="stack">
        <Field label="資料名"><input className="input" value={form.title} onChange={set('title')} /></Field>
        <div className="grid-2">
          <Field label="カテゴリ">
            <select className="input" value={form.category} onChange={set('category')}>{categories.map((c) => <option key={c}>{c}</option>)}</select>
          </Field>
          <Field label="管理部署">
            <select className="input" value={form.department} onChange={set('department')}>{departments.map((d) => <option key={d}>{d}</option>)}</select>
          </Field>
        </div>
        <Field label="タグ" hint="カンマ区切り。検索Agentが検索語を広げる際の手がかりになります"><input className="input" value={form.tags} onChange={set('tags')} /></Field>
        <div className="field">
          <span className="field-label">公開範囲</span>
          <VisibilityEditor value={form.visibility} onChange={(v) => setForm({ ...form, visibility: v })} departments={departments} />
          <span className="field-hint">公開範囲外の従業員の質問には、この資料は検索・引用されません</span>
        </div>
      </div>

      <p className="section-label">バージョン履歴</p>
      <ul className="version-list">
        {doc.versions.map((v) => (
          <li key={v.version}>
            <span className="badge badge-gray">第{v.version}版</span>
            <span className="grow">{v.note}</span>
            <span className="muted small">{v.by}・{formatDate(v.updatedAt)}</span>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={confirmDelete}
        title="資料を削除しますか？"
        message={`「${doc.title}」を削除します。\n検索対象から外れ、今後のAIの回答に使用されなくなります。`}
        confirmLabel="削除する"
        danger
        onConfirm={remove}
        onCancel={() => setConfirmDelete(false)}
      />
    </Modal>
  );
}

export default function DocumentsPage() {
  const categories = useCategories();
  const departments = useDepartments();
  const [filters, setFilters] = useState({ q: '', category: '', department: '', status: '' });
  const { data: docs, loading, reload } = useFetch(() => documentApi.list(filters), [JSON.stringify(filters)]);
  const { data: all, reload: reloadAll } = useFetch(() => documentApi.list(), []);
  const [detailId, setDetailId] = useState(null);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  const refresh = () => {
    reload();
    reloadAll();
  };

  // 取り込み中の資料があれば状態を定期的に更新する
  const processing = all?.some((d) => d.status === 'processing');
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processing]);

  const count = (s) => all?.filter((d) => !s || d.status === s).length ?? 0;

  return (
    <div className="admin-page">
      <PageHeader
        title="資料一覧"
        description="AIが検索・回答に使用する社内資料を管理します"
        actions={<Link to="/admin/documents/upload" className="btn btn-primary"><Upload size={16} /> 資料をアップロード</Link>}
      />

      <div className="stat-row">
        <div className="stat"><span className="stat-label">登録資料</span><span className="stat-value">{count()}</span></div>
        <div className="stat"><span className="stat-label">検索可能</span><span className="stat-value">{count('indexed')}</span></div>
        <div className="stat"><span className="stat-label">処理中</span><span className="stat-value">{count('processing')}</span></div>
        <div className="stat"><span className="stat-label">エラー</span><span className={`stat-value ${count('error') ? 'text-red' : ''}`}>{count('error')}</span></div>
      </div>

      <div className="toolbar">
        <div className="search-input">
          <Search size={15} />
          <input placeholder="資料名・ファイル名・タグで検索" value={filters.q} onChange={setF('q')} />
        </div>
        <select className="input" value={filters.category} onChange={setF('category')}>
          <option value="">すべてのカテゴリ</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className="input" value={filters.department} onChange={setF('department')}>
          <option value="">すべての管理部署</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select className="input" value={filters.status} onChange={setF('status')}>
          <option value="">すべての状態</option>
          {Object.entries(DOC_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table className="table clickable">
          <thead>
            <tr><th>資料名</th><th>カテゴリ</th><th>管理部署</th><th>公開範囲</th><th>状態</th><th className="right">チャンク</th><th>更新日</th></tr>
          </thead>
          <tbody>
            {docs?.map((d) => (
              <tr key={d.id} onClick={() => setDetailId(d.id)}>
                <td>
                  <div className="cell-doc">
                    <FileIcon type={d.fileType} />
                    <div>
                      <strong>{d.title}</strong>
                      <span className="muted small block">{d.fileName}・第{d.version}版</span>
                    </div>
                  </div>
                </td>
                <td>{d.category}</td>
                <td>{d.department}</td>
                <td title={visibilityLabel(d.visibility)}><VisibilityCell v={d.visibility} /></td>
                <td><StatusBadge map={DOC_STATUS} value={d.status} /></td>
                <td className="right">{d.chunks || '—'}</td>
                <td className="muted">{formatDate(d.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !docs && <Spinner />}
        {docs && !docs.length && <EmptyState title="該当する資料はありません" />}
      </div>

      {detailId && <DocumentDetailModal id={detailId} onClose={() => setDetailId(null)} onChanged={refresh} />}
    </div>
  );
}
