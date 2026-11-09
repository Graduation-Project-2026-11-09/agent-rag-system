import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp } from 'lucide-react';
import { userApi } from '../../api';
import { useDepartments } from '../../hooks/useMasters';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Field from '../../components/common/Field';
import { ROLES } from '../../constants';

const EMPTY = { employeeId: '', name: '', email: '', department: '', role: 'user', handlesDepartment: '', passwordMode: 'invite', password: '' };

function SingleForm() {
  const navigate = useNavigate();
  const toast = useToast();
  const departments = useDepartments();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const validate = () => {
    const e = {};
    if (!/^E\d{5}$/.test(form.employeeId)) e.employeeId = '「E」＋数字5桁で入力してください（例：E10234）';
    if (!form.name.trim()) e.name = '氏名を入力してください';
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) e.email = 'メールアドレスの形式が正しくありません';
    if (!form.department) e.department = '所属部署を選択してください';
    if (form.passwordMode === 'password' && form.password.length < 12) e.password = '12文字以上で入力してください';
    setErrors(e);
    return !Object.keys(e).length;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      await userApi.create(form);
      toast(form.passwordMode === 'invite' ? `${form.name} さんに招待メールを送信しました` : 'アカウントを作成しました');
      navigate('/admin/accounts');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card form-card stack" onSubmit={submit}>
      <h3>基本情報</h3>
      <div className="grid-2">
        <Field label="社員番号" required error={errors.employeeId}>
          <input className="input" value={form.employeeId} onChange={set('employeeId')} placeholder="E10234" />
        </Field>
        <Field label="氏名" required error={errors.name}>
          <input className="input" value={form.name} onChange={set('name')} placeholder="山田 花子" />
        </Field>
      </div>
      <div className="grid-2">
        <Field label="メールアドレス" required error={errors.email}>
          <input className="input" value={form.email} onChange={set('email')} placeholder="name@example.co.jp" />
        </Field>
        <Field label="所属部署" required error={errors.department} hint="閲覧できる資料の範囲に影響します">
          <select className="input" value={form.department} onChange={set('department')}>
            <option value="">選択してください</option>
            {departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
      </div>

      <h3>権限</h3>
      <div className="role-options">
        {Object.entries(ROLES).map(([k, v]) => (
          <label key={k} className={`role-option ${form.role === k ? 'selected' : ''}`}>
            <input type="radio" name="role" value={k} checked={form.role === k} onChange={set('role')} />
            <span>
              <strong>{v.label}</strong>
              <span className="muted small block">{v.description}</span>
            </span>
          </label>
        ))}
      </div>
      {form.role !== 'user' && (
        <Field label="対応する問い合わせの部署" hint="未選択の場合は所属部署になります">
          <select className="input" value={form.handlesDepartment} onChange={set('handlesDepartment')}>
            <option value="">所属部署と同じ</option>
            {departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
      )}

      <h3>初回ログイン</h3>
      <div className="radio-row">
        <label className="radio"><input type="radio" value="invite" checked={form.passwordMode === 'invite'} onChange={set('passwordMode')} /> 招待メールを送信（本人がパスワードを設定）</label>
        <label className="radio"><input type="radio" value="password" checked={form.passwordMode === 'password'} onChange={set('passwordMode')} /> 初期パスワードを設定</label>
      </div>
      {form.passwordMode === 'password' && (
        <Field label="初期パスワード" error={errors.password} hint="12文字以上。初回ログイン時に変更を求めます">
          <input className="input" type="password" value={form.password} onChange={set('password')} />
        </Field>
      )}

      <div className="form-actions">
        <button type="button" className="btn" onClick={() => navigate('/admin/accounts')}>キャンセル</button>
        <button className="btn btn-primary" disabled={saving}>{saving ? '作成中…' : 'アカウントを作成'}</button>
      </div>
    </form>
  );
}

const SAMPLE_CSV = `社員番号,氏名,メールアドレス,所属部署,権限
E10701,森 陽菜,mori@example.co.jp,営業部,user
E10702,池田 湊,ikeda@example.co.jp,開発部,user
E10703,橋本 葵,hashimoto@example.co.jp,人事部,staff`;

function parseCsv(text) {
  const [, ...lines] = text.trim().split(/\r?\n/);
  return lines.filter(Boolean).map((line) => {
    const [employeeId, name, email, department, role] = line.split(',').map((s) => s.trim());
    return { employeeId, name, email, department, role: role || 'user' };
  });
}

function BulkForm() {
  const navigate = useNavigate();
  const toast = useToast();
  const [rows, setRows] = useState([]);
  const [fileName, setFileName] = useState('');
  const [result, setResult] = useState(null);

  const onFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    setRows(parseCsv(await file.text()));
    setResult(null);
  };

  const submit = async () => {
    const res = await userApi.bulkCreate(rows);
    setResult(res);
    if (res.created) toast(`${res.created} 件のアカウントを作成し、招待メールを送信しました`);
  };

  return (
    <div className="card form-card stack">
      <p className="muted">CSVファイルで複数のアカウントを一括登録します。登録したアカウントには招待メールが送信されます。</p>
      <pre className="code-box">{SAMPLE_CSV}</pre>
      <div className="row gap-sm">
        <label className="btn">
          <FileUp size={16} /> CSVファイルを選択
          <input type="file" accept=".csv" hidden onChange={(e) => onFile(e.target.files[0])} />
        </label>
        <button className="btn" onClick={() => { setFileName('サンプルデータ'); setRows(parseCsv(SAMPLE_CSV)); setResult(null); }}>サンプルを読み込む</button>
        {fileName && <span className="muted small">{fileName}（{rows.length} 件）</span>}
      </div>

      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>#</th><th>社員番号</th><th>氏名</th><th>メールアドレス</th><th>所属部署</th><th>権限</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={result?.errors.some((e) => e.row === i + 1) ? 'row-error' : ''}>
                  <td>{i + 1}</td><td>{r.employeeId}</td><td>{r.name}</td><td>{r.email}</td><td>{r.department}</td><td>{ROLES[r.role]?.label ?? r.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {result?.errors.length > 0 && (
        <div className="warn-box block">
          {result.errors.map((e) => <p key={e.row}>{e.row}行目：{e.message}</p>)}
        </div>
      )}
      <div className="form-actions">
        <button className="btn" onClick={() => navigate('/admin/accounts')}>一覧へ戻る</button>
        <button className="btn btn-primary" disabled={!rows.length || !!result} onClick={submit}>{rows.length} 件を登録</button>
      </div>
    </div>
  );
}

export default function AccountCreatePage() {
  const [tab, setTab] = useState('single');
  return (
    <div className="admin-page narrow">
      <PageHeader title="アカウント作成" description="新しい従業員のアカウントを作成します" />
      <div className="tabs">
        <button className={tab === 'single' ? 'active' : ''} onClick={() => setTab('single')}>個別に作成</button>
        <button className={tab === 'bulk' ? 'active' : ''} onClick={() => setTab('bulk')}>CSVで一括登録</button>
      </div>
      {tab === 'single' ? <SingleForm /> : <BulkForm />}
    </div>
  );
}
