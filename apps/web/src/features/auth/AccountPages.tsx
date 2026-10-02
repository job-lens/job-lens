import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';
import { api, ApiError, setCsrfToken, unwrap, unwrapVoid } from '@/shared/api/client';
import { prepareCsrf } from './authApi';
import { AccountFrame } from './AccountFrame';
import styles from './Auth.module.css';
const csrfHeader = { 'X-CSRF-Token': '' };
const message = (error: unknown) =>
  error instanceof ApiError ? error.message : '连接未完成，请稍后重试。';
function FormError({ text }: { text: string }) {
  return text ? (
    <p className={`${styles.error} qx-notice qx-notice--danger`} role="alert">
      {text}
    </p>
  ) : null;
}

export function RegisterPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');
  const [email, setEmail] = useState('');
  const [remaining, setRemaining] = useState(0);
  const [privateEntry, setPrivateEntry] = useState(false);
  const emailField = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => {
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setRemaining(remaining - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining]);
  async function sendCode() {
    if (busy || !emailField.current?.reportValidity()) return;
    setBusy(true);
    setError('');
    setSent('');
    try {
      await prepareCsrf();
      unwrap(
        await api.POST('/auth/registration-code', {
          body: { email: email.trim() },
          params: { header: csrfHeader },
        }),
      );
      setSent(email.trim().toLowerCase());
      setRemaining(60);
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      await prepareCsrf();
      const result = unwrap(
        await api.POST('/auth/register', {
          body: {
            email: email.trim(),
            display_name: String(fields.get('display_name')).trim(),
            code: String(fields.get('code')),
            password: String(fields.get('password')),
          },
          params: { header: csrfHeader },
        }),
      );
      await client.cancelQueries();
      client.clear();
      client.setQueryData(['session'], result.user);
      setCsrfToken(result.csrf_token);
      navigate('/learner', { replace: true });
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AccountFrame title="注册" privateEntry={privateEntry}>
      <p className="qx-meta">注册后，进入你的学员工作台。</p>
      <form className={styles.form} onSubmit={event => void submit(event)} aria-busy={busy}>
        <label className="sr-only" htmlFor="display-name">
          称呼
        </label>
        <input
          id="display-name"
          name="display_name"
          className="qx-input"
          placeholder="怎么称呼你"
          autoComplete="nickname"
          required
          maxLength={80}
        />
        <label className="sr-only" htmlFor="email">
          邮箱
        </label>
        <input
          ref={emailField}
          id="email"
          name="email"
          className="qx-input"
          placeholder="邮箱"
          type="email"
          autoComplete="email"
          required
          maxLength={80}
          value={email}
          onChange={event => setEmail(event.target.value)}
          autoCapitalize="none"
          spellCheck={false}
        />
        <div className={styles.codeRow}>
          <label className="sr-only" htmlFor="code">
            验证码
          </label>
          <input
            id="code"
            name="code"
            className="qx-input"
            placeholder="6 位验证码"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            minLength={6}
            maxLength={6}
            required
          />
          <button
            type="button"
            className="qx-btn qx-btn--secondary"
            disabled={busy || remaining > 0}
            onClick={() => void sendCode()}
          >
            {remaining > 0 ? `${remaining} 秒后重发` : '获取验证码'}
          </button>
        </div>
        {sent === email.trim().toLowerCase() && sent && (
          <p className="qx-meta" role="status">
            验证码已发送，请查看邮箱。
          </p>
        )}
        <label className="sr-only" htmlFor="new-password">
          密码
        </label>
        <input
          id="new-password"
          name="password"
          className="qx-input"
          placeholder="设置密码"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={256}
          aria-describedby="password-help"
          onFocus={() => setPrivateEntry(true)}
          onBlur={() => setPrivateEntry(false)}
        />
        <p id="password-help" className={`qx-meta ${styles.hint}`}>
          至少 12 个字符。
        </p>
        <FormError text={error} />
        <button
          className="qx-btn qx-btn--primary qx-btn--lg qx-btn--block"
          type="submit"
          disabled={busy}
        >
          {busy ? '正在处理…' : '注册'}
        </button>
      </form>
      <p className={styles.accountLink}>
        已有账号？ <Link to="/login">登录</Link>
      </p>
    </AccountFrame>
  );
}
export function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    setSent('');
    try {
      await prepareCsrf();
      const result = unwrap(
        await api.POST('/auth/password-reset-requests', {
          body: { email: String(fields.get('email')).trim() },
          params: { header: csrfHeader },
        }),
      );
      setSent(result.message);
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AccountFrame title="找回密码">
      <p className="qx-meta">通过注册邮箱，重新设置密码。</p>
      <form className={styles.form} onSubmit={event => void submit(event)} aria-busy={busy}>
        <label className="sr-only" htmlFor="reset-email">
          邮箱
        </label>
        <input
          id="reset-email"
          name="email"
          className="qx-input"
          placeholder="注册邮箱"
          type="email"
          autoComplete="email"
          required
          maxLength={80}
          autoCapitalize="none"
          spellCheck={false}
        />
        <FormError text={error} />
        {sent && <p role="status">{sent}</p>}
        <button
          className="qx-btn qx-btn--primary qx-btn--lg qx-btn--block"
          type="submit"
          disabled={busy}
        >
          {busy ? '正在发送…' : '发送找回链接'}
        </button>
      </form>
      <p className={styles.accountLink}>
        <Link to="/login">返回登录</Link>
      </p>
    </AccountFrame>
  );
}
export function ResetPasswordPage() {
  const location = useLocation();
  const [token, setToken] = useState(
    () => new URLSearchParams(location.hash.slice(1)).get('token') ?? '',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [privateEntry, setPrivateEntry] = useState(false);
  const client = useQueryClient();
  useEffect(() => {
    window.history.replaceState(
      window.history.state,
      '',
      window.location.pathname + window.location.search,
    );
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      await prepareCsrf();
      unwrapVoid(
        await api.POST('/auth/password-resets', {
          body: { token, password: String(fields.get('password')) },
          params: { header: csrfHeader },
        }),
      );
      await client.cancelQueries();
      client.clear();
      setCsrfToken();
      setToken('');
      setDone(true);
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AccountFrame title="设置新密码" privateEntry={privateEntry}>
      {done ? (
        <>
          <p role="status">密码已更新。请用新密码登录。</p>
          <Link className="qx-btn qx-btn--primary" to="/login">
            登录
          </Link>
        </>
      ) : /^[A-Za-z0-9_-]{43}$/.test(token) ? (
        <>
          <form className={styles.form} onSubmit={event => void submit(event)} aria-busy={busy}>
            <label className="sr-only" htmlFor="reset-password">
              新密码
            </label>
            <input
              id="reset-password"
              name="password"
              className="qx-input"
              placeholder="新密码"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={256}
              aria-describedby="reset-help"
              onFocus={() => setPrivateEntry(true)}
              onBlur={() => setPrivateEntry(false)}
            />
            <p id="reset-help" className={`qx-meta ${styles.hint}`}>
              至少 12 个字符。保存后，所有设备需要重新登录。
            </p>
            <FormError text={error} />
            <button
              type="submit"
              className="qx-btn qx-btn--primary qx-btn--lg qx-btn--block"
              disabled={busy}
            >
              {busy ? '正在保存…' : '保存新密码'}
            </button>
          </form>
          <p className={styles.accountLink}>
            <Link to="/forgot-password">重新获取链接</Link>
          </p>
        </>
      ) : (
        <>
          <p role="alert">找回链接不完整，请重新获取。</p>
          <Link className="qx-btn qx-btn--primary" to="/forgot-password">
            重新获取链接
          </Link>
        </>
      )}
    </AccountFrame>
  );
}
