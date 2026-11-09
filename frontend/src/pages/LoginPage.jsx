import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

/**
 * ログイン画面。社員のメールアドレスとパスワードでログインする（機能要件 No.1）。
 * ログイン後は権限に応じて、一般利用者はチャット、部署担当者・管理者は管理画面へ移動する。
 */
export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={user.role === 'user' ? '/chat' : '/admin'} replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const u = await login(email, password);
      navigate(u.role === 'user' ? '/chat' : '/admin', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="brand-mark"><Sparkles size={20} /></span>
          <div>
            <h1>社内ナビAI</h1>
            <p className="muted">社内の制度・手続きをAIに質問できます</p>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="stack">
          <label className="field">
            <span className="field-label">メールアドレス</span>
            <input
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.co.jp"
              required
            />
          </label>
          <label className="field">
            <span className="field-label">パスワード</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? 'ログイン中…' : 'ログイン'}
          </button>
          <button type="button" className="link-btn">パスワードをお忘れの方</button>
        </form>
      </div>
    </div>
  );
}
