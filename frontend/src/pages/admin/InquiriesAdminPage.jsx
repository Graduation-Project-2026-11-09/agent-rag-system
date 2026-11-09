import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { inquiryApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useDepartments } from '../../hooks/useMasters';
import { useAuth } from '../../contexts/AuthContext';
import PageHeader from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import EmptyState from '../../components/common/EmptyState';
import { INQUIRY_STATUS } from '../../constants';
import { formatDateTime, formatRelative } from '../../utils/format';

export default function InquiriesAdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const departments = useDepartments();
  const [filters, setFilters] = useState({ status: '', department: '', q: '' });
  const { data, loading } = useFetch(() => inquiryApi.list(filters), [JSON.stringify(filters)]);
  const { data: all } = useFetch(() => inquiryApi.list(), []);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="admin-page">
      <PageHeader
        title="問い合わせ管理"
        description={user.role === 'staff' ? `${user.handlesDepartment}あての問い合わせを表示しています` : 'AIで解決できず、従業員が承認・送信した問い合わせを管理します'}
      />
      <div className="tabs">
        {[['', 'すべて'], ...Object.entries(INQUIRY_STATUS).map(([k, v]) => [k, v.label])].map(([k, label]) => (
          <button key={k} className={filters.status === k ? 'active' : ''} onClick={() => setFilters({ ...filters, status: k })}>
            {label}
            <span className="tab-count">{all?.filter((q) => !k || q.status === k).length ?? 0}</span>
          </button>
        ))}
      </div>
      <div className="toolbar">
        <div className="search-input">
          <Search size={15} />
          <input placeholder="件名・氏名・受付番号で検索" value={filters.q} onChange={setF('q')} />
        </div>
        {user.role === 'admin' && (
          <select className="input" value={filters.department} onChange={setF('department')}>
            <option value="">すべての宛先部署</option>
            {departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        )}
      </div>

      <div className="table-wrap">
        <table className="table clickable">
          <thead>
            <tr><th>受付番号</th><th>件名</th><th>問い合わせ者</th><th>宛先部署</th><th>担当者</th><th>状態</th><th>受付日時</th></tr>
          </thead>
          <tbody>
            {data?.map((q) => (
              <tr key={q.id} onClick={() => navigate(`/admin/inquiries/${q.id}`)}>
                <td className="mono">{q.number}</td>
                <td><strong>{q.subject}</strong></td>
                <td>{q.userName}<span className="muted small block">{q.userDepartment}</span></td>
                <td>{q.department}</td>
                <td>{q.assignee ?? <span className="muted">未割当</span>}</td>
                <td><StatusBadge map={INQUIRY_STATUS} value={q.status} /></td>
                <td className="muted" title={formatDateTime(q.createdAt)}>{formatRelative(q.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && !data && <Spinner />}
        {data && !data.length && <EmptyState title="該当する問い合わせはありません" />}
      </div>
    </div>
  );
}
