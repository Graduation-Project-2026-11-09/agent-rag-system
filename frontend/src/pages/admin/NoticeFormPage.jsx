import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { noticeApi } from '../../api';
import { useDepartments } from '../../hooks/useMasters';
import { useToast } from '../../contexts/ToastContext';
import PageHeader from '../../components/common/PageHeader';
import Field from '../../components/common/Field';
import Badge from '../../components/common/Badge';
import VisibilityEditor from '../../components/common/VisibilityEditor';
import Spinner from '../../components/common/Spinner';
import { toLocalInput } from '../../utils/format';

const EMPTY = { title: '', body: '', priority: 'normal', target: { type: 'all' }, channels: ['in_app'], publishMode: 'now', publishAt: '', expireAt: '' };

export default function NoticeFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const departments = useDepartments();
  const [form, setForm] = useState(id ? null : EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    noticeApi.get(id).then((n) =>
      setForm({
        ...n,
        publishMode: n.publishAt && Date.parse(n.publishAt) > Date.now() ? 'schedule' : 'now',
        publishAt: toLocalInput(n.publishAt),
        expireAt: toLocalInput(n.expireAt),
      }),
    );
  }, [id]);

  if (!form) return <Spinner />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleChannel = (c) => setForm({ ...form, channels: form.channels.includes(c) ? form.channels.filter((x) => x !== c) : [...form.channels, c] });

  const save = async (isDraft) => {
    if (!form.title.trim() || !form.body.trim()) return toast('タイトルと本文を入力してください', 'error');
    if (!form.channels.length) return toast('配信方法を1つ以上選択してください', 'error');
    if (form.target.type === 'departments' && !form.target.departments.length) return toast('配信する部署を選択してください', 'error');
    if (form.publishMode === 'schedule' && !form.publishAt) return toast('配信日時を入力してください', 'error');
    setSaving(true);
    const payload = {
      title: form.title,
      body: form.body,
      priority: form.priority,
      target: form.target,
      channels: form.channels,
      publishAt: form.publishMode === 'schedule' ? new Date(form.publishAt).toISOString() : null,
      expireAt: form.expireAt ? new Date(form.expireAt).toISOString() : null,
      isDraft,
    };
    try {
      if (id) await noticeApi.update(id, payload);
      else await noticeApi.create(payload);
      toast(isDraft ? '下書きを保存しました' : form.publishMode === 'schedule' ? '配信を予約しました' : 'お知らせを配信しました');
      navigate('/admin/notices');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-page">
      <PageHeader title={id ? 'お知らせの編集' : 'お知らせの作成'} />
      <div className="form-with-preview">
        <div className="card form-card stack">
          <Field label="タイトル" required><input className="input" value={form.title} onChange={set('title')} placeholder="例：年末調整の書類提出期限について" /></Field>
          <Field label="本文" required><textarea className="input" rows={7} value={form.body} onChange={set('body')} /></Field>
          <div className="field">
            <span className="field-label">重要度</span>
            <div className="radio-row">
              <label className="radio"><input type="radio" value="normal" checked={form.priority === 'normal'} onChange={set('priority')} /> 通常</label>
              <label className="radio"><input type="radio" value="important" checked={form.priority === 'important'} onChange={set('priority')} /> 重要（チャット画面上部にバナー表示）</label>
            </div>
          </div>
          <div className="field">
            <span className="field-label">配信対象</span>
            <VisibilityEditor value={form.target} onChange={(v) => setForm({ ...form, target: v })} departments={departments} allLabel="全従業員" />
          </div>
          <div className="field">
            <span className="field-label">配信方法</span>
            <div className="radio-row">
              <label className="check"><input type="checkbox" checked={form.channels.includes('in_app')} onChange={() => toggleChannel('in_app')} /> 画面内のお知らせ</label>
              <label className="check"><input type="checkbox" checked={form.channels.includes('email')} onChange={() => toggleChannel('email')} /> メール</label>
            </div>
          </div>
          <div className="field">
            <span className="field-label">配信日時</span>
            <div className="radio-row">
              <label className="radio"><input type="radio" value="now" checked={form.publishMode === 'now'} onChange={set('publishMode')} /> すぐに配信</label>
              <label className="radio"><input type="radio" value="schedule" checked={form.publishMode === 'schedule'} onChange={set('publishMode')} /> 日時を指定</label>
            </div>
            {form.publishMode === 'schedule' && <input className="input w-auto" type="datetime-local" value={form.publishAt} onChange={set('publishAt')} />}
          </div>
          <Field label="掲載終了日時" hint="未入力の場合は無期限で掲載します">
            <input className="input w-auto" type="datetime-local" value={form.expireAt} onChange={set('expireAt')} />
          </Field>
          <div className="form-actions">
            <button className="btn" onClick={() => navigate('/admin/notices')}>キャンセル</button>
            <button className="btn" disabled={saving} onClick={() => save(true)}>下書き保存</button>
            <button className="btn btn-primary" disabled={saving} onClick={() => save(false)}>{form.publishMode === 'schedule' ? '配信を予約' : '配信する'}</button>
          </div>
        </div>

        <aside className="preview-pane">
          <p className="section-label">従業員側の表示プレビュー</p>
          {form.priority === 'important' && (
            <div className="notice-banner static">
              <Badge tone="red">重要</Badge>
              <span className="truncate">{form.title || 'タイトル'}</span>
            </div>
          )}
          <div className="card notice-card unread">
            <div className="notice-head">
              <span className="unread-dot" />
              {form.priority === 'important' && <Badge tone="red">重要</Badge>}
              <strong className="grow">{form.title || 'タイトル'}</strong>
            </div>
            <p className="notice-body pre-wrap">{form.body || '本文がここに表示されます'}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
