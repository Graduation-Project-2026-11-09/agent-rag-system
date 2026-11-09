import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { UploadCloud, X, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { documentApi } from '../../api';
import { useCategories, useDepartments } from '../../hooks/useMasters';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Field from '../../components/common/Field';
import FileIcon from '../../components/common/FileIcon';
import VisibilityEditor from '../../components/common/VisibilityEditor';
import { formatFileSize } from '../../utils/format';

const ACCEPT = ['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'md'];
const MAX_SIZE = 50 * 1024 * 1024;

// 取り込みの進行段階（Flask 側の processingStage と対応）
const STAGES = [
  { key: 'uploaded', label: 'アップロード' },
  { key: 'extracting', label: 'テキスト抽出' },
  { key: 'chunking', label: 'チャンク分割' },
  { key: 'embedding', label: 'ベクトル化' },
  { key: 'done', label: '完了' },
];

function Progress({ stage }) {
  const idx = STAGES.findIndex((s) => s.key === stage);
  return (
    <div className="progress-stages">
      {STAGES.map((s, i) => (
        <span key={s.key} className={i < idx || stage === 'done' ? 'done' : i === idx ? 'current' : ''}>{s.label}</span>
      ))}
    </div>
  );
}

export default function DocumentUploadPage() {
  const { user } = useAuth();
  const toast = useToast();
  const departments = useDepartments();
  const categories = useCategories();
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [items, setItems] = useState([]); // { key, file, error, stage, docId }
  const [meta, setMeta] = useState({
    category: '',
    department: user.handlesDepartment ?? user.department,
    visibility: { type: 'all' },
    tags: '',
    effectiveDate: new Date().toISOString().slice(0, 10),
  });
  const [uploading, setUploading] = useState(false);
  const timersRef = useRef([]);
  const setM = (k) => (e) => setMeta({ ...meta, [k]: e.target.value });

  useEffect(() => () => timersRef.current.forEach(clearInterval), []);

  const addFiles = (fileList) => {
    const next = [...fileList].map((file) => {
      const ext = file.name.split('.').pop().toLowerCase();
      let error = null;
      if (!ACCEPT.includes(ext)) error = '対応していないファイル形式です';
      else if (file.size > MAX_SIZE) error = 'ファイルサイズが50MBを超えています';
      return { key: `${file.name}-${file.size}-${Math.random()}`, file, ext, error, stage: null };
    });
    setItems((cur) => [...cur, ...next]);
  };

  const updateItem = (key, patch) => setItems((cur) => cur.map((i) => (i.key === key ? { ...i, ...patch } : i)));

  // 取り込み完了までドキュメントの状態をポーリングする
  const watch = (key, docId) => {
    const t = setInterval(async () => {
      const d = await documentApi.get(docId);
      if (d.status === 'indexed') {
        clearInterval(t);
        updateItem(key, { stage: 'done' });
      } else if (d.status === 'error') {
        clearInterval(t);
        updateItem(key, { stage: null, error: d.errorMessage });
      } else {
        updateItem(key, { stage: d.processingStage ?? 'extracting' });
      }
    }, 700);
    timersRef.current.push(t);
  };

  const valid = items.some((i) => !i.error && !i.stage) && meta.category && meta.department && (meta.visibility.type === 'all' || meta.visibility.departments.length);

  const upload = async () => {
    setUploading(true);
    const payload = { ...meta, tags: meta.tags.split(',').map((t) => t.trim()).filter(Boolean) };
    for (const item of items.filter((i) => !i.error && !i.stage)) {
      updateItem(item.key, { stage: 'uploaded' });
      try {
        const doc = await documentApi.upload(item.file, payload);
        watch(item.key, doc.id);
      } catch (e) {
        updateItem(item.key, { stage: null, error: e.message });
      }
    }
    setUploading(false);
    toast('アップロードしました。取り込みが完了すると検索対象になります');
  };

  const allDone = items.length > 0 && items.every((i) => i.error || i.stage === 'done');

  return (
    <div className="admin-page narrow">
      <PageHeader title="資料アップロード" description="アップロードした資料はテキスト抽出・分割・ベクトル化され、AIの検索対象になります" />

      <div className="card form-card stack">
        <div
          className={`dropzone ${drag ? 'drag' : ''}`}
          onClick={() => inputRef.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}
        >
          <UploadCloud size={32} strokeWidth={1.5} />
          <p><strong>ファイルをドラッグ＆ドロップ</strong> またはクリックして選択</p>
          <p className="muted small">PDF / Word / Excel / PowerPoint / テキスト（1ファイル50MBまで・複数選択可）</p>
          <input ref={inputRef} type="file" multiple hidden accept={ACCEPT.map((e) => `.${e}`).join(',')} onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        </div>

        {items.length > 0 && (
          <ul className="upload-list">
            {items.map((i) => (
              <li key={i.key} className={i.error ? 'has-error' : ''}>
                <FileIcon type={i.ext} />
                <div className="grow">
                  <div className="row gap-sm">
                    <strong className="truncate">{i.file.name}</strong>
                    <span className="muted small">{formatFileSize(i.file.size)}</span>
                  </div>
                  {i.error && <span className="field-error"><AlertCircle size={12} /> {i.error}</span>}
                  {i.stage && <Progress stage={i.stage} />}
                </div>
                {i.stage === 'done' ? (
                  <CheckCircle2 size={18} className="text-green" />
                ) : i.stage ? (
                  <Loader2 size={18} className="spin" />
                ) : (
                  <button className="icon-btn" onClick={() => setItems(items.filter((x) => x.key !== i.key))} aria-label="取り除く"><X size={16} /></button>
                )}
              </li>
            ))}
          </ul>
        )}

        <h3>資料の情報</h3>
        <p className="muted small">選択したすべてのファイルに同じ情報が設定されます。資料名はファイル名から自動で設定されます（あとから変更可能）。</p>
        <div className="grid-2">
          <Field label="カテゴリ" required>
            <select className="input" value={meta.category} onChange={setM('category')}>
              <option value="">選択してください</option>
              {categories.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="管理部署" required hint="資料の内容に責任を持つ部署（問い合わせ先の候補になります）">
            <select className="input" value={meta.department} onChange={setM('department')}>
              {departments.map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
        </div>
        <div className="grid-2">
          <Field label="施行日・適用開始日">
            <input className="input" type="date" value={meta.effectiveDate} onChange={setM('effectiveDate')} />
          </Field>
          <Field label="タグ" hint="カンマ区切り（例：結婚, 扶養, 慶弔）">
            <input className="input" value={meta.tags} onChange={setM('tags')} />
          </Field>
        </div>
        <div className="field">
          <span className="field-label">公開範囲<span className="required">必須</span></span>
          <VisibilityEditor value={meta.visibility} onChange={(v) => setMeta({ ...meta, visibility: v })} departments={departments} />
          <span className="field-hint">部署を指定した場合、その部署の従業員の質問にのみ使用されます</span>
        </div>

        <div className="form-actions">
          {allDone ? (
            <Link to="/admin/documents" className="btn btn-primary">資料一覧へ</Link>
          ) : (
            <>
              <Link to="/admin/documents" className="btn">キャンセル</Link>
              <button className="btn btn-primary" disabled={!valid || uploading} onClick={upload}>{uploading ? 'アップロード中…' : 'アップロードして取り込む'}</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
