import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 回答中の [1] などの引用番号を、根拠資料を開くボタンに変換する
export default function MessageContent({ content, onCite }) {
  const md = content.replace(/\[(\d+)\]/g, '[$1](#cite-$1)');
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href?.startsWith('#cite-') ? (
              <button className="cite" onClick={() => onCite?.(Number(href.slice(6)))} title="根拠資料を表示">
                {children}
              </button>
            ) : (
              <a href={href} target="_blank" rel="noreferrer">{children}</a>
            ),
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}
