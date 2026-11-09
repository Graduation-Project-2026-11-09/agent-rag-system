import FileIcon from '../common/FileIcon';

export default function SourceList({ sources, onOpen }) {
  if (!sources.length) return null;
  return (
    <div className="sources">
      <p className="section-label">根拠資料（{sources.length}件）</p>
      <div className="source-grid">
        {sources.map((s) => (
          <button key={s.index} className="source-card" onClick={() => onOpen(s)}>
            <span className="source-index">{s.index}</span>
            <FileIcon type={s.fileType} size={16} />
            <span className="source-text">
              <span className="truncate source-title">{s.title}</span>
              <span className="truncate muted small">{s.section}・p.{s.page}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
