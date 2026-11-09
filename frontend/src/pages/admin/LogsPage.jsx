import { useState } from 'react';
import { Search, ThumbsUp, ThumbsDown } from 'lucide-react';
import { logApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useDepartments } from '../../hooks/useMasters';
import PageHeader from '../../components/common/PageHeader';
import Modal from '../../components/common/Modal';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import EmptyState from '../../components/common/EmptyState';
import AgentTrace from '../../components/chat/AgentTrace';
import { LOG_RESULT } from '../../constants';
import { formatDateTime, formatPercent } from '../../utils/format';

function Feedback({ value }) {
  if (value === 'good') return <ThumbsUp size={14} className="text-green" />;
  if (value === 'bad') return <ThumbsDown size={14} className="text-red" />;
  return <span className="muted">—</span>;
}

export default function LogsPage() {
  const departments = useDepartments();
  const [filters, setFilters] = useState({ days: '30', result: '', department: '', q: '' });
  const { data: logs, loading } = useFetch(() => logApi.list(filters), [JSON.stringify(filters)]);
  const { data: summary } = useFetch(() => logApi.summary({ days: filters.days }), [filters.days]);
  const [detail, setDetail] = useState(null);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="admin-page">
      <PageHeader title="利用履歴" description="従業員の質問内容とAgentの検索結果を確認できます。回答精度の検証や資料改善に活用します" />

      {summary && (
        <div className="stat-row">
          <div className="stat"><span className="stat-label">質問数</span><span className="stat-value">{summary.total}</span></div>
          <div className="stat"><span className="stat-label">自己解決率</span><span className="stat-value">{formatPercent(summary.resolvedRate)}</span></div>
          <div className="stat"><span className="stat-label">平均検索回数</span><span className="stat-value">{summary.avgSearchCount.toFixed(1)}回</span></div>
          <div className="stat"><span className="stat-label">平均応答時間</span><span className="stat-value">{(summary.avgDurationMs / 1000).toFixed(1)}秒</span></div>
          <div className="stat"><span className="stat-label">高評価率</span><span className="stat-value">{formatPercent(summary.goodRate)}</span></div>
          <div className="stat" title="自己解決1件あたり20分の対応時間を削減したと仮定"><span className="stat-label">削減時間（試算）</span><span className="stat-value">{(summary.savedMinutes / 60).toFixed(1)}h</span></div>
        </div>
      )}

      <div className="toolbar">
        <div className="search-input">
          <Search size={15} />
          <input placeholder="質問内容・氏名で検索" value={filters.q} onChange={setF('q')} />
        </div>
        <select className="input" value={filters.days} onChange={setF('days')}>
          <option value="7">過去7日間</option>
          <option value="30">過去30日間</option>
          <option value="">すべての期間</option>
        </select>
        <select className="input" value={filters.result} onChange={setF('result')}>
          <option value="">すべての結果</option>
          {Object.entries(LOG_RESULT).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="input" value={filters.department} onChange={setF('department')}>
          <option value="">すべての部署</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table className="table clickable">
          <thead>
            <tr><th>日時</th><th>利用者</th><th>質問内容</th><th className="right">検索回数</th><th className="right">根拠資料</th><th>結果</th><th className="center">評価</th></tr>
          </thead>
          <tbody>
            {logs?.map((l) => (
              <tr key={l.id} onClick={() => setDetail(l)}>
                <td className="muted nowrap">{formatDateTime(l.at)}</td>
                <td className="nowrap">{l.userName}<span className="muted small block">{l.department}</span></td>
                <td className="cell-question">{l.question}</td>
                <td className="right">{l.searchCount}</td>
                <td className="right">{l.sourceCount}</td>
                <td><StatusBadge map={LOG_RESULT} value={l.result} /></td>
                <td className="center"><Feedback value={l.feedback} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !logs && <Spinner />}
        {logs && !logs.length && <EmptyState title="該当する履歴はありません" />}
      </div>
      {logs && <p className="muted small">{logs.length} 件</p>}

      {detail && (
        <Modal open size="lg" title="利用履歴の詳細" onClose={() => setDetail(null)}>
          <dl className="meta-grid">
            <dt>日時</dt><dd>{formatDateTime(detail.at)}</dd>
            <dt>利用者</dt><dd>{detail.userName}（{detail.department}）</dd>
            <dt>結果</dt><dd><StatusBadge map={LOG_RESULT} value={detail.result} /></dd>
            <dt>応答時間</dt><dd>{(detail.durationMs / 1000).toFixed(1)}秒</dd>
          </dl>
          <p className="section-label">質問</p>
          <p className="question-box">{detail.question}</p>
          <p className="section-label">Agentの処理過程</p>
          <AgentTrace steps={detail.steps} searchCount={detail.searchCount} durationMs={detail.durationMs} running={false} />
          <p className="section-label">引用された資料</p>
          {detail.sources.length ? (
            <ul className="plain-list">{detail.sources.map((s) => <li key={s}>{s}</li>)}</ul>
          ) : (
            <p className="muted small">なし（資料不足の可能性があります）</p>
          )}
        </Modal>
      )}
    </div>
  );
}
