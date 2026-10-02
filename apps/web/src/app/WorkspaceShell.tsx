import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router';
import { SessionControls, useSession } from '@/features/auth/public';
import { Icon, type IconName } from '@/shared/ui/Icon';
import styles from './App.module.css';

type Destination = { href: string; label: string; icon: IconName; active: boolean };
export function WorkspaceShell() {
  const location = useLocation();
  const session = useSession();
  const [collapsed, setCollapsed] = useState(false);
  const [narrow, setNarrow] = useState(() => window.innerWidth <= 760);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const main = useRef<HTMLElement>(null);
  const pathname = location.pathname;
  const counselor = session.data?.roles.includes('counselor');
  const learner = session.data?.roles.includes('learner');
  const casesTab = new URLSearchParams(location.search).get('tab') === 'cases';
  const roleLabel =
    counselor && learner ? '学员与辅导员' : counselor ? '辅导员工作区' : '学员工作区';
  const name = session.data?.display_name || '我的账户';
  const destinations: Destination[] = [
    ...(counselor
      ? [
          {
            href: '/counselor',
            label: '工作台',
            icon: 'home' as const,
            active: pathname === '/counselor' && !casesTab,
          },
          {
            href: '/counselor?tab=cases',
            label: '个案管理',
            icon: 'users' as const,
            active:
              (pathname === '/counselor' && casesTab) ||
              pathname.startsWith('/counselor/cases') ||
              pathname.startsWith('/counselor/sop') ||
              pathname.startsWith('/counselor/tasks') ||
              pathname.startsWith('/counselor/submissions'),
          },
          {
            href: '/counselor/support',
            label: '辅导与求助',
            icon: 'chat' as const,
            active: pathname.startsWith('/counselor/support'),
          },
        ]
      : []),
    ...(learner
      ? [
          {
            href: '/learner',
            label: '我的任务',
            icon: 'tasks' as const,
            active: pathname === '/learner' || pathname.startsWith('/learner/tasks'),
          },
          {
            href: '/learner/records',
            label: '训练记录',
            icon: 'records' as const,
            active: pathname === '/learner/records',
          },
        ]
      : []),
    {
      href: '/notifications',
      label: '通知中心',
      icon: 'bell',
      active: pathname === '/notifications' || pathname === '/counselor/notifications',
    },
  ];
  const settingsActive = ['/settings', '/profile', '/preferences'].includes(pathname);
  const current = settingsActive
    ? '设置'
    : destinations.find(item => item.active)?.label ||
      (pathname.startsWith('/learner/support') ? '联系辅导员' : '工作区');

  useEffect(() => {
    const resize = () => {
      const isNarrow = window.innerWidth <= 760;
      setNarrow(isNarrow);
      if (!isNarrow) setDrawerOpen(false);
    };
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  useEffect(() => {
    setDrawerOpen(false);
    main.current?.scrollTo?.({ top: 0 });
  }, [location.key]);
  useEffect(() => {
    if (!narrow || !drawerOpen) return;
    const trigger = menu.current;
    sidebar.current?.querySelector<HTMLButtonElement>('button')?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setDrawerOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const nodes = Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          'a[href],button:not(:disabled),[tabindex="0"]',
        ) ?? [],
      );
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (!first || !last) return;
      if (
        event.shiftKey &&
        (document.activeElement === first || !sidebar.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || !sidebar.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      trigger?.focus();
    };
  }, [narrow, drawerOpen]);

  return (
    <div className={styles.shell} data-collapsed={collapsed} data-drawer={drawerOpen}>
      <a href="#main" className={`skip-link ${styles.skip}`}>
        跳到主要内容
      </a>
      {narrow && drawerOpen && (
        <button
          className={styles.scrim}
          aria-label="关闭导航菜单"
          tabIndex={-1}
          onClick={() => setDrawerOpen(false)}
        />
      )}
      <aside
        ref={sidebar}
        id="workspace-navigation"
        className={styles.sidebar}
        aria-label="融职境导航"
        role={narrow ? 'dialog' : undefined}
        aria-modal={(narrow && drawerOpen) || undefined}
        aria-hidden={(narrow && !drawerOpen) || undefined}
        inert={narrow && !drawerOpen}
      >
        <div className={styles.brandRow}>
          <Link
            to={counselor ? '/counselor' : '/learner'}
            className={styles.brand}
            aria-label="融职境工作台"
          >
            <span className={styles.brandMark} aria-hidden="true">
              融
            </span>
            <span className={styles.wordmark}>
              融职境<small>Job Lens</small>
            </span>
          </Link>
          <button
            type="button"
            className="qx-btn qx-btn--ghost qx-btn--icon"
            aria-label={narrow ? '关闭菜单' : collapsed ? '展开侧栏' : '收起侧栏'}
            onClick={() => (narrow ? setDrawerOpen(false) : setCollapsed(value => !value))}
          >
            <Icon name={narrow ? 'close' : 'sidebar'} />
          </button>
        </div>
        <div className={styles.railContent}>
          <p className={styles.groupLabel}>{roleLabel}</p>
          <nav className={styles.navigation} aria-label="主导航">
            {destinations.map(item => (
              <Link
                key={item.href}
                to={item.href}
                className={styles.navItem}
                aria-current={item.active ? 'page' : undefined}
                title={item.label}
              >
                <Icon name={item.icon} />
                <span className={styles.navLabel}>{item.label}</span>
              </Link>
            ))}
          </nav>
          <div className={styles.railNote}>
            <span className={styles.statusDot} />
            一步一步，按自己的节奏。
          </div>
        </div>
        <div className={styles.account}>
          <Link
            className={styles.navItem}
            to="/settings"
            aria-current={settingsActive ? 'page' : undefined}
            title="设置"
          >
            <Icon name="settings" />
            <span className={styles.navLabel}>设置</span>
          </Link>
          <Link to="/settings?tab=profile" className={styles.identity} title={`${name} · 个人资料`}>
            <span className={styles.avatar} aria-hidden="true">
              {Array.from(name)[0]}
            </span>
            <span className={styles.identityText}>
              <strong>{name}</strong>
              <small>{roleLabel}</small>
            </span>
          </Link>
          <div className={styles.sessionControls}>
            <SessionControls compact />
          </div>
        </div>
      </aside>
      <div className={styles.body} inert={narrow && drawerOpen}>
        <header className={styles.header}>
          <button
            ref={menu}
            type="button"
            className={`qx-btn qx-btn--ghost qx-btn--icon ${styles.mobileMenu}`}
            aria-label="打开菜单"
            aria-expanded={drawerOpen}
            aria-controls="workspace-navigation"
            onClick={() => setDrawerOpen(true)}
          >
            <Icon name="menu" />
          </button>
          <div className={styles.breadcrumb}>
            <span>融职境</span>
            <span aria-hidden="true">/</span>
            <strong>{current}</strong>
          </div>
          <Link
            to="/notifications"
            className="qx-btn qx-btn--secondary qx-btn--icon"
            aria-label="打开通知中心"
          >
            <Icon name="bell" />
          </Link>
        </header>
        <main ref={main} id="main" className={styles.main} tabIndex={-1}>
          <div className={styles.content}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
