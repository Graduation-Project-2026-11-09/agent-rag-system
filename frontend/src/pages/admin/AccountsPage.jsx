import { useState } from 'react';
import { Link } from 'react-router-dom';
import { UserPlus, Search, Pencil, KeyRound, Ban, RotateCcw, Trash2 } from 'lucide-react';
import { userApi } from '../../api';
import { useFetch } from '../../hooks/useFetch';
import { useDepartments } from '../../hooks/useMasters';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Modal from '../../components/common/Modal';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import Field from '../../components/common/Field';
import { StatusBadge } from '../../components/common/Badge';
import Spinner from '../../components/common/Spinner';
import EmptyState from '../../components/common/EmptyState';
import { ROLES, USER_STATUS } from '../../constants';
import { formatDateTime } from '../../utils/format';

function EditUserModal({ user, departments, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({ name: user.name, email: user.email, department: user.department, role: user.role, handlesDepartment: user.handlesDepartment ?? user.department });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const save = async () => {
    try {
      await userApi.update(user.id, form);
      toast('アカウント情報を更新しました');
      onSaved();
    } catch (e) {
      toast(e.message, 'error');
    }
  };
  return (
    <Modal
      open
      title="アカウントの編集"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>キャンセル</button>
          <button className="btn btn-primary" onClick={save}>保存する</button>
        </>
      }
    >
      <div className="stack">
        <div className="grid-2">
          <Field label="社員番号"><input className="input" value={user.employeeId} disabled /></Field>
          <Field label="氏名" required><input className="input" value={form.name} onChange={set('name')} /></Field>
        </div>
        <Field label="メールアドレス" required><input className="input" value={form.email} onChange={set('email')} /></Field>
        <div className="grid-2">
          <Field label="所属部署">
            <select className="input" value={form.department} onChange={set('department')}>{departments.map((d) => <option key={d}>{d}</option>)}</select>
          </Field>
          <Field label="権限">
            <select className="input" value={form.role} onChange={set('role')}>
              {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </Field>
        </div>
        {form.role !== 'user' && (
          <Field label="対応する問い合わせの部署" hint="この部署あての問い合わせに対応できます">
            <select className="input" value={form.handlesDepartment} onChange={set('handlesDepartment')}>{departments.map((d) => <option key={d}>{d}</option>)}</select>
          </Field>
        )}
      </div>
    </Modal>
  );
}

/** 管理者が新しいパスワードを決めて設定する（メールは送らない） */
function ResetPasswordModal({ user, onClose }) {
  const toast = useToast();
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const tooShort = password.length < 12;
  const save = async () => {
    setSaving(true);
    try {
      await userApi.update(user.id, { password });
      toast(`${user.name} さんのパスワードを再設定しました`);
      onClose();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal
      open
      title="パスワード再設定"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>キャンセル</button>
          <button className="btn btn-primary" disabled={tooShort || saving} onClick={save}>{saving ? '設定中…' : '再設定する'}</button>
        </>
      }
    >
      <div className="stack">
        <p className="muted">{user.name}（{user.email}）の新しいパスワードを設定します。</p>
        <Field
          label="新しいパスワード"
          required
          error={password && tooShort ? '12文字以上で入力してください' : undefined}
          hint="12文字以上。本人には安全な方法で伝えてください"
        >
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
        </Field>
      </div>
    </Modal>
  );
}

export default function AccountsPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const departments = useDepartments();
  const [filters, setFilters] = useState({ q: '', department: '', role: '', status: '' });
  const { data: users, loading, reload } = useFetch(() => userApi.list(filters), [JSON.stringify(filters)]);
  const [editing, setEditing] = useState(null);
  const [resetting, setResetting] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const setF = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });

  const run = async (fn, message) => {
    try {
      await fn();
      toast(message);
      reload();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setConfirm(null);
    }
  };

  const askSuspend = (u) =>
    setConfirm({
      title: u.status === 'suspended' ? '利用を再開しますか？' : '利用を停止しますか？',
      message: u.status === 'suspended' ? `${u.name} さんのアカウントを再開します。` : `${u.name} さんはログインできなくなります。会話履歴などのデータは保持されます。`,
      confirmLabel: u.status === 'suspended' ? '再開する' : '停止する',
      danger: u.status !== 'suspended',
      onConfirm: () => run(() => userApi.update(u.id, { status: u.status === 'suspended' ? 'active' : 'suspended' }), '利用状態を変更しました'),
    });

  const askDelete = (u) =>
    setConfirm({
      title: 'アカウントを削除しますか？',
      message: `${u.name}（${u.email}）を削除します。\nこの操作は取り消せません。会話履歴も削除されます。`,
      confirmLabel: '削除する',
      danger: true,
      onConfirm: () => run(() => userApi.remove(u.id), 'アカウントを削除しました'),
    });

  return (
    <div className="admin-page">
      <PageHeader
        title="アカウント管理"
        description="システムを利用する従業員のアカウントと権限を管理します"
        actions={<Link to="/admin/accounts/new" className="btn btn-primary"><UserPlus size={16} /> アカウント作成</Link>}
      />

      <div className="toolbar">
        <div className="search-input">
          <Search size={15} />
          <input placeholder="氏名・メール・社員番号で検索" value={filters.q} onChange={setF('q')} />
        </div>
        <select className="input" value={filters.department} onChange={setF('department')}>
          <option value="">すべての部署</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select className="input" value={filters.role} onChange={setF('role')}>
          <option value="">すべての権限</option>
          {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className="input" value={filters.status} onChange={setF('status')}>
          <option value="">すべての状態</option>
          {Object.entries(USER_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>氏名</th><th>社員番号</th><th>所属部署</th><th>権限</th><th>状態</th><th>最終ログイン</th><th className="right">操作</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="cell-user">
                    <span className="avatar sm">{u.name[0]}</span>
                    <div>
                      <strong>{u.name}</strong>
                      <span className="muted small block">{u.email}</span>
                    </div>
                  </div>
                </td>
                <td>{u.employeeId}</td>
                <td>{u.department}</td>
                <td>
                  {ROLES[u.role].label}
                  {u.role !== 'user' && u.handlesDepartment && <span className="muted small block">担当：{u.handlesDepartment}</span>}
                </td>
                <td><StatusBadge map={USER_STATUS} value={u.status} /></td>
                <td className="muted">{formatDateTime(u.lastLoginAt)}</td>
                <td className="right nowrap">
                  <button className="icon-btn" title="編集" onClick={() => setEditing(u)}><Pencil size={15} /></button>
                  <button className="icon-btn" title="パスワード再設定" onClick={() => setResetting(u)}><KeyRound size={15} /></button>
                  <button className="icon-btn" title={u.status === 'suspended' ? '利用再開' : '利用停止'} onClick={() => askSuspend(u)} disabled={u.id === me.id}>
                    {u.status === 'suspended' ? <RotateCcw size={15} /> : <Ban size={15} />}
                  </button>
                  <button className="icon-btn danger" title="削除" onClick={() => askDelete(u)} disabled={u.id === me.id}><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <Spinner />}
        {users && !users.length && <EmptyState title="該当するアカウントはありません" />}
      </div>
      {users && <p className="muted small">{users.length} 件</p>}

      {editing && <EditUserModal user={editing} departments={departments} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
      {resetting && <ResetPasswordModal user={resetting} onClose={() => setResetting(null)} />}
      <ConfirmDialog open={!!confirm} {...confirm} onCancel={() => setConfirm(null)} />
    </div>
  );
}
