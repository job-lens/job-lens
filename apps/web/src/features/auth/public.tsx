import { useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router';
import { api, ApiError, setCsrfToken, unwrap, unwrapVoid } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { PreferencesProvider } from '@/shared/preferences/public';
import { Companions } from '@/shared/ui/Companions';
import styles from './Auth.module.css';

async function prepareCsrf() {
  const result = unwrap(await api.GET('/auth/csrf'));
  setCsrfToken(result.csrf_token);
}

async function loadSession({ signal }: { signal: AbortSignal }) {
  const current = unwrap(await api.GET('/me', { signal }));
  await prepareCsrf();
  return current;
}

export function SessionGate({ role }: { role?: 'learner' | 'counselor' }) {
  const location = useLocation();
  const user = useQuery({
    queryKey: ['session'],
    queryFn: loadSession,
  });
  if (user.isPending) return <LoadingState />;
  if (user.error instanceof ApiError && user.error.status === 401)
    return (
      <Navigate
        to="/login"
        replace
        state={{ returnTo: location.pathname + location.search + location.hash, expired: true }}
      />
    );
  if (user.isError)
    return <ErrorPanel message="身份服务暂不可用" retry={() => void user.refetch()} />;
  if (role && !user.data.roles.includes(role)) return <ErrorPanel message="无权访问此区域" />;
  return (
    <PreferencesProvider>
      <Outlet />
    </PreferencesProvider>
  );
}
export function LoginPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { returnTo?: unknown; expired?: boolean } | null;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      await prepareCsrf();
      const result = unwrap(
        await api.POST('/auth/login', {
          body: {
            login_name: String(data.get('account')).trim(),
            password: String(data.get('password')),
          },
          params: { header: { 'X-CSRF-Token': '' } },
        }),
      );
      await client.cancelQueries();
      client.clear();
      client.setQueryData(['session'], result.user);
      setCsrfToken(result.csrf_token);
      const target = state?.returnTo;
      const fallback = result.user.roles.includes('counselor') ? '/counselor' : '/learner';
      navigate(
        typeof target === 'string' &&
          /^\/(?!\/)/.test(target) &&
          !target.includes('\\') &&
          !target.startsWith('/login')
          ? target
          : fallback,
        { replace: true },
      );
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : '连接未完成，请稍后重试。');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#login-main">
        跳到主要内容
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          融职境
        </Link>
        <Link to="/" className="qx-btn qx-btn--ghost">
          返回首页
        </Link>
      </header>
      <main id="login-main" className={styles.content} tabIndex={-1}>
        <Companions />
        <h1 className="qx-display">登录</h1>
        {state?.expired && (
          <p className="qx-meta" role="status">
            会话已结束。登录后，继续刚才的任务。
          </p>
        )}
        <form className={styles.form} onSubmit={event => void submit(event)} aria-busy={busy}>
          <label className="sr-only" htmlFor="account">
            账号
          </label>
          <input
            className="qx-input"
            id="account"
            name="account"
            placeholder="账号"
            autoComplete="username"
            required
            maxLength={80}
            autoCapitalize="none"
            spellCheck={false}
          />
          <label className="sr-only" htmlFor="password">
            密码
          </label>
          <input
            className="qx-input"
            id="password"
            name="password"
            placeholder="密码"
            type="password"
            autoComplete="current-password"
            required
            maxLength={256}
          />
          {error && (
            <p className={`${styles.error} qx-notice qx-notice--danger`} role="alert">
              {error}
            </p>
          )}
          <button
            className="qx-btn qx-btn--primary qx-btn--lg qx-btn--block"
            disabled={busy}
            type="submit"
          >
            {busy ? '正在登录…' : '登录'}
          </button>
        </form>
      </main>
    </div>
  );
}

export function SessionControls() {
  const client = useQueryClient();
  const user = useQuery({ queryKey: ['session'], queryFn: loadSession, enabled: false });
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function logout() {
    setBusy(true);
    setError('');
    try {
      await prepareCsrf();
      unwrapVoid(await api.POST('/auth/logout', { params: { header: { 'X-CSRF-Token': '' } } }));
      await client.cancelQueries();
      client.clear();
      setCsrfToken();
      navigate('/login', { replace: true });
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        await client.cancelQueries();
        client.clear();
        setCsrfToken();
        navigate('/login', { replace: true });
      } else setError('退出未完成，请重试。');
    } finally {
      setBusy(false);
    }
  }
  if (!user.data) return null;
  return (
    <div className={styles.session}>
      <Link to="/profile">我的资料</Link>
      <button
        className="qx-btn qx-btn--secondary"
        type="button"
        onClick={() => void logout()}
        disabled={busy}
      >
        {busy ? '正在退出…' : '退出登录'}
      </button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}
