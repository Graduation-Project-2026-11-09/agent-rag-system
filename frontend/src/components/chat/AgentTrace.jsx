import { useEffect, useState } from 'react';
import { ChevronDown, Brain, Route, Search, ClipboardCheck, PenLine, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';

const ICONS = { analyze: Brain, plan: Route, search: Search, evaluate: ClipboardCheck, generate: PenLine };

function StepBody({ step }) {
  return (
    <div className="trace-body">
      {step.detail && <p>{step.detail}</p>}
      {step.items && (
        <div className="chip-row">
          {step.items.map((v) => <span key={v} className="chip chip-static">{v}</span>)}
        </div>
      )}
      {step.queries && (
        <div className="chip-row">
          {step.queries.map((q) => <span key={q} className="chip chip-query"><Search size={11} /> {q}</span>)}
        </div>
      )}
      {step.results && (
        <ul className="trace-results">
          {step.results.length === 0 && <li className="muted">該当する資料はありませんでした</li>}
          {step.results.map((r, i) => (
            <li key={i}>
              <span className="truncate">{r.title} <span className="muted">／ {r.section}</span></span>
              <span className="score">{r.score.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Agent が「何を・どう検索したか」を表示する（Agentic RAG の処理過程） */
export default function AgentTrace({ steps, running, searchCount, durationMs }) {
  const [open, setOpen] = useState(running);
  useEffect(() => setOpen(running), [running]);

  const summary = running
    ? steps.at(-1)?.title ?? '質問内容を分析しています'
    : `${searchCount}回検索・${steps.length}ステップで回答（${(durationMs / 1000).toFixed(1)}秒）`;

  return (
    <div className={`agent-trace ${running ? 'running' : ''}`}>
      <button className="trace-toggle" onClick={() => setOpen((v) => !v)}>
        {running ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} className="ok" />}
        <span>{running ? `${summary}…` : `検索プロセス：${summary}`}</span>
        <ChevronDown size={14} className={`chev ${open ? 'up' : ''}`} />
      </button>
      {open && (
        <ol className="trace-steps">
          {steps.map((step) => {
            const Icon = step.type === 'evaluate' && step.sufficient === false ? AlertTriangle : ICONS[step.type];
            return (
              <li key={step.id} className={`trace-step t-${step.type} ${step.sufficient === false ? 'warn' : ''}`}>
                <span className="trace-icon"><Icon size={13} /></span>
                <div>
                  <p className="trace-title">{step.title}</p>
                  <StepBody step={step} />
                </div>
              </li>
            );
          })}
          {running && (
            <li className="trace-step pending">
              <span className="trace-icon"><Loader2 size={13} className="spin" /></span>
              <p className="trace-title muted">処理中…</p>
            </li>
          )}
        </ol>
      )}
    </div>
  );
}
