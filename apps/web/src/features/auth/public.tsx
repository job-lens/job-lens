import { useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router';
import { api, ApiError, setCsrfToken, unwrap, unwrapVoid } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
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
  return <Outlet />;
}
function WelcomeScene() {
  return (
    <svg className={styles.scene} viewBox="0 0 460 330" aria-hidden="true">
      <ellipse cx="241" cy="285" rx="168" ry="14" fill="#e7e8e5" />
      <rect x="48" y="79" width="234" height="185" rx="28" fill="#e1ebef" />
      <rect x="66" y="101" width="198" height="140" rx="20" fill="#fff" />
      <circle cx="89" cy="126" r="6" fill="#b1c9d0" />
      <rect x="105" y="123" width="67" height="6" rx="3" fill="#c9d4d9" />
      <rect x="81" y="146" width="122" height="34" rx="17" fill="#f2f4f3" />
      <path
        d="m91 162 5 5 10-11"
        fill="none"
        stroke="#6b8983"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="116" y="160" width="66" height="6" rx="3" fill="#b5c6c2" />
      <rect x="81" y="195" width="77" height="28" rx="14" fill="#e4eee9" />
      <circle cx="350" cy="97" r="25" fill="#e9d6b0" />
      <path
        d="m335 98 10 8 18-21"
        fill="none"
        stroke="#89724e"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M316 231v34m42-34v34" stroke="#73948a" strokeWidth="12" strokeLinecap="round" />
      <rect x="282" y="147" width="108" height="94" rx="43" fill="#aec6bd" />
      <path
        d="m285 183-18 19m119-19 16 9"
        stroke="#aec6bd"
        strokeWidth="14"
        strokeLinecap="round"
      />
      <rect x="280" y="111" width="113" height="85" rx="38" fill="#bfd5cc" />
      <rect x="297" y="132" width="79" height="44" rx="22" fill="#f7faf7" />
      <path d="M318 150v6m35-6v6" stroke="#527466" strokeWidth="5" strokeLinecap="round" />
      <path
        d="M327 165q9 5 18 0"
        fill="none"
        stroke="#527466"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="336" cy="210" r="9" fill="#ecf4ef" />
    </svg>
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
      <aside className={styles.welcome}>
        <p className={styles.headline}>
          每一步，
          <br />
          都有支持。
        </p>
        <WelcomeScene />
        <p>
          按自己的节奏练习，
          <br />
          和辅导员一起找到适合的工作方式。
        </p>
      </aside>
      <section className={styles.formPanel} aria-labelledby="login-title">
        <h1 id="login-title">登录</h1>
        <p className={styles.intro}>
          {state?.expired ? '会话已结束。登录后，继续刚才的任务。' : '欢迎回来，继续你的工作练习。'}
        </p>
        <form onSubmit={event => void submit(event)} aria-busy={busy}>
          <label htmlFor="account">账号</label>
          <input
            id="account"
            name="account"
            autoComplete="username"
            required
            maxLength={80}
            autoCapitalize="none"
            spellCheck={false}
          />
          <label htmlFor="password">密码</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={256}
          />
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <button className={styles.primary} disabled={busy} type="submit">
            {busy ? '正在登录…' : '登录'}
          </button>
        </form>
        <Link className={styles.home} to="/">
          返回官网
        </Link>
      </section>
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
      <button type="button" onClick={() => void logout()} disabled={busy}>
        {busy ? '正在退出…' : '退出登录'}
      </button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}
