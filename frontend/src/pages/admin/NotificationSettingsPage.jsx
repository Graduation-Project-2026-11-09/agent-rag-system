import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { noticeApi } from '../../api';
import { useDepartments } from '../../hooks/useMasters';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Spinner from '../../components/common/Spinner';

function Toggle({ checked, onChange }) {
  return (
    <button type="button" role="switch" aria-checked={checked} className={`toggle ${checked ? 'on' : ''}`} onClick={() => onChange(!checked)}>
      <span />
    </button>
  );
}

export default function NotificationSettingsPage() {
  const toast = useToast();
  const departments = useDepartments();
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    noticeApi.getSettings().then(setSettings);
  }, []);

  if (!settings) return <Spinner />;

  const setEvent = (key, field, value) =>
    setSettings({ ...settings, events: settings.events.map((e) => (e.key === key ? { ...e, [field]: value } : e)) });
  const setContact = (i, field, value) =>
    setSettings({ ...settings, departmentContacts: settings.departmentContacts.map((c, j) => (i === j ? { ...c, [field]: value } : c)) });
  const setReport = (field, value) => setSettings({ ...settings, weeklyReport: { ...settings.weeklyReport, [field]: value } });

  const save = async () => {
    setSaving(true);
    await noticeApi.saveSettings(settings);
    setSaving(false);
    toast('通知設定を保存しました');
  };

  return (
    <div className="admin-page narrow">
      <PageHeader title="通知設定" description="システムから自動で送信される通知のルールを設定します" actions={<button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? '保存中…' : '設定を保存'}</button>} />

      <section className="card settings-section">
        <h3>イベント通知</h3>
        <table className="table plain">
          <thead><tr><th>イベント</th><th className="center">画面内</th><th className="center">メール</th></tr></thead>
          <tbody>
            {settings.events.map((e) => (
              <tr key={e.key}>
                <td>
                  <strong>{e.label}</strong>
                  <span className="muted small block">{e.description}</span>
                </td>
                <td className="center"><Toggle checked={e.inApp} onChange={(v) => setEvent(e.key, 'inApp', v)} /></td>
                <td className="center"><Toggle checked={e.email} onChange={(v) => setEvent(e.key, 'email', v)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card settings-section">
        <h3>部署の問い合わせ窓口</h3>
        <p className="muted small">問い合わせを受け付けたとき、担当者に加えて以下の共有アドレスにも通知します。AIが問い合わせ先を提案する際の候補にもなります。</p>
        <div className="stack-sm">
          {settings.departmentContacts.map((c, i) => (
            <div key={i} className="row gap-sm">
              <select className="input w-auto" value={c.department} onChange={(e) => setContact(i, 'department', e.target.value)}>
                {departments.map((d) => <option key={d}>{d}</option>)}
              </select>
              <input className="input grow" value={c.email} onChange={(e) => setContact(i, 'email', e.target.value)} placeholder="窓口のメールアドレス" />
              <button className="icon-btn danger" onClick={() => setSettings({ ...settings, departmentContacts: settings.departmentContacts.filter((_, j) => j !== i) })}><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
        <button className="btn btn-sm" onClick={() => setSettings({ ...settings, departmentContacts: [...settings.departmentContacts, { department: departments[0], email: '' }] })}>
          <Plus size={14} /> 窓口を追加
        </button>
      </section>

      <section className="card settings-section">
        <div className="row between">
          <div>
            <h3>週次レポート</h3>
            <p className="muted small">質問件数・自己解決率・未解決の質問などの集計をメールで送信します。</p>
          </div>
          <Toggle checked={settings.weeklyReport.enabled} onChange={(v) => setReport('enabled', v)} />
        </div>
        {settings.weeklyReport.enabled && (
          <div className="row gap-sm wrap">
            <select className="input w-auto" value={settings.weeklyReport.dayOfWeek} onChange={(e) => setReport('dayOfWeek', e.target.value)}>
              {[['mon', '毎週月曜日'], ['fri', '毎週金曜日']].map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input className="input grow" value={settings.weeklyReport.recipients} onChange={(e) => setReport('recipients', e.target.value)} placeholder="送信先（カンマ区切り）" />
          </div>
        )}
      </section>
    </div>
  );
}
