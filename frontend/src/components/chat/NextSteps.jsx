import { useState } from 'react';
import { ListChecks } from 'lucide-react';

export default function NextSteps({ steps }) {
  const [done, setDone] = useState({});
  if (!steps.length) return null;
  return (
    <div className="next-steps">
      <p className="section-label"><ListChecks size={14} /> 次に行う手続き</p>
      <ul>
        {steps.map((s) => (
          <li key={s.id} className={done[s.id] ? 'done' : ''}>
            <label>
              <input type="checkbox" checked={!!done[s.id]} onChange={(e) => setDone({ ...done, [s.id]: e.target.checked })} />
              <span className="ns-main">
                <span className="ns-title">{s.title}</span>
                <span className="muted small">{s.description}</span>
              </span>
              <span className="ns-meta">
                <span className="badge badge-gray">{s.department}</span>
                <span className="deadline">{s.deadline}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="muted small">※ 申請はAIが代行しません。各システムからご自身で手続きしてください。</p>
    </div>
  );
}
