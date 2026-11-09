import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react';
import Modal from '../common/Modal';
import Field from '../common/Field';
import { inquiryApi } from '../../api';
import { useDepartments } from '../../hooks/useMasters';
import { useToast } from '../../contexts/ToastContext';

const stripMarkdown = (s) => s.replace(/\[(\d+)\]/g, '').replace(/[#*>`-]/g, '').replace(/\s+/g, ' ').trim();

/**
 * 問い合わせ文の作成 → 利用者による確認・承認 → 送信 の3ステップ。
 * AIが自動送信することはなく、必ず「承認して送信」を押したときだけ送信される。
 */
export default function InquiryModal({ message, question, onClose, onSent }) {
  const navigate = useNavigate();
  const toast = useToast();
  const departments = useDepartments();
  const s = message.inquirySuggestion;
  const [step, setStep] = useState('edit');
  const [form, setForm] = useState({ department: s.department, subject: s.subject, body: s.body, attachAnswer: true, attachSources: true });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  const valid = form.subject.trim() && form.body.trim();

  const send = async () => {
    setSending(true);
    try {
      const inquiry = await inquiryApi.create({
        messageId: message.id,
        department: form.department,
        subject: form.subject,
        body: form.body,
        context: {
          question,
          sources: form.attachSources ? message.sources.map((x) => `${x.title} ${x.section}`) : [],
          aiAnswerSummary: form.attachAnswer ? stripMarkdown(message.content).slice(0, 140) : '',
        },
      });
      setResult(inquiry);
      setStep('done');
      onSent(inquiry);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSending(false);
    }
  };

  const footers = {
    edit: (
      <>
        <button className="btn" onClick={onClose}>キャンセル</button>
        <button className="btn btn-primary" disabled={!valid} onClick={() => setStep('confirm')}>内容を確認する</button>
      </>
    ),
    confirm: (
      <>
        <button className="btn" onClick={() => setStep('edit')} disabled={sending}>戻って修正</button>
        <button className="btn btn-primary" onClick={send} disabled={sending}>{sending ? '送信中…' : '承認して送信'}</button>
      </>
    ),
    done: (
      <>
        <button className="btn" onClick={onClose}>閉じる</button>
        <button className="btn btn-primary" onClick={() => navigate('/inquiries')}>問い合わせ履歴を見る</button>
      </>
    ),
  };

  return (
    <Modal open size="lg" title="担当部署への問い合わせ" onClose={onClose} footer={footers[step]}>
      <ol className="stepper">
        {['下書きの編集', '内容の確認', '送信完了'].map((label, i) => (
          <li key={label} className={['edit', 'confirm', 'done'].indexOf(step) >= i ? 'active' : ''}>
            <span>{i + 1}</span>{label}
          </li>
        ))}
      </ol>

      {step === 'edit' && (
        <div className="stack">
          <p className="info-box"><Sparkles size={14} /> AIが作成した下書きです。内容を確認・修正してください。</p>
          <div className="grid-2">
            <Field label="宛先部署" required>
              <select className="input" value={form.department} onChange={set('department')}>
                {departments.map((d) => <option key={d}>{d}</option>)}
              </select>
            </Field>
            <Field label="件名" required>
              <input className="input" value={form.subject} onChange={set('subject')} />
            </Field>
          </div>
          <Field label="本文" required>
            <textarea className="input" rows={13} value={form.body} onChange={set('body')} />
          </Field>
          <div className="stack-sm">
            <span className="field-label">担当者に共有する情報</span>
            <label className="check"><input type="checkbox" checked={form.attachAnswer} onChange={set('attachAnswer')} /> 質問内容とAIの回答</label>
            <label className="check"><input type="checkbox" checked={form.attachSources} onChange={set('attachSources')} /> AIが確認した根拠資料（{message.sources.length}件）</label>
          </div>
        </div>
      )}

      {step === 'confirm' && (
        <div className="stack">
          <p className="warn-box"><AlertTriangle size={14} /> 以下の内容で{form.department}へ送信します。送信後は取り消せません。</p>
          <dl className="meta-grid">
            <dt>宛先</dt><dd>{form.department}</dd>
            <dt>件名</dt><dd>{form.subject}</dd>
          </dl>
          <pre className="preview-body">{form.body}</pre>
          <div className="muted small">
            共有する情報：{[form.attachAnswer && '質問内容とAIの回答', form.attachSources && `根拠資料 ${message.sources.length}件`].filter(Boolean).join('、') || 'なし'}
          </div>
        </div>
      )}

      {step === 'done' && result && (
        <div className="done-box">
          <CheckCircle2 size={40} />
          <p className="done-title">問い合わせを送信しました</p>
          <p>受付番号：<strong>{result.number}</strong></p>
          <p className="muted">{result.department}の担当者から回答があると、お知らせとメールで通知されます。</p>
        </div>
      )}
    </Modal>
  );
}
