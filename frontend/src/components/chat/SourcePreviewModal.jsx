import { ExternalLink } from 'lucide-react';
import Modal from '../common/Modal';
import FileIcon from '../common/FileIcon';
import { useFetch } from '../../hooks/useFetch';
import { documentApi } from '../../api';
import { USE_MOCK } from '../../api/client';
import { useToast } from '../../contexts/ToastContext';
import { formatDate } from '../../utils/format';

export default function SourcePreviewModal({ source, onClose }) {
  const toast = useToast();
  const { data: doc } = useFetch(() => (source ? documentApi.getSource(source.documentId) : Promise.resolve(null)), [source?.documentId]);
  if (!source) return null;

  const openOriginal = () => {
    if (USE_MOCK) return toast('モックアップでは原本ファイルは表示されません', 'error');
    window.open(`/api/documents/${source.documentId}/file#page=${source.page}`, '_blank');
  };

  return (
    <Modal
      open
      size="lg"
      title={
        <span className="row gap-sm">
          <FileIcon type={source.fileType} /> {source.title}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>閉じる</button>
          <button className="btn btn-primary" onClick={openOriginal}><ExternalLink size={14} /> 原本を開く（p.{source.page}）</button>
        </>
      }
    >
      <dl className="meta-grid">
        <dt>該当箇所</dt><dd>{source.section}（p.{source.page}）</dd>
        <dt>管理部署</dt><dd>{source.department}</dd>
        <dt>施行日</dt><dd>{doc ? formatDate(doc.effectiveDate) : '—'}</dd>
        <dt>最終更新</dt><dd>{formatDate(source.updatedAt)}{doc && `（第${doc.version}版）`}</dd>
      </dl>
      <div className="doc-page">
        <p className="doc-page-head">{source.title}{'　'}— p.{source.page}</p>
        <p className="doc-ellipsis">…</p>
        <p><mark>{source.excerpt}</mark></p>
        <p className="doc-ellipsis">…</p>
      </div>
      <p className="muted small">AIが回答に使用した箇所をハイライト表示しています。正確な内容は原本で確認してください。</p>
    </Modal>
  );
}
