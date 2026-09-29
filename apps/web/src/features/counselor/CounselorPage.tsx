import { Link, useSearchParams } from 'react-router';
import { CaseList } from './CaseList';
import { Dashboard } from './Dashboard';
import styles from './counselor.module.css';

type Tab = 'home' | 'cases';

/** 底部一级导航：首页/个案同挂 /counselor（内部 tab 切换），交流走 /counselor/support，我的走公共 /profile。 */
export function CounselorPage() {
  const [searchParams] = useSearchParams();
  const tab: Tab = searchParams.get('tab') === 'cases' ? 'cases' : 'home';

  return (
    <section className={styles.page}>
      {tab === 'home' ? <Dashboard /> : <CaseList />}

      <nav aria-label="底部导航" className={styles.bottomNav}>
        <Link
          to="/counselor"
          aria-current={tab === 'home' ? 'page' : undefined}
          className={styles.navItem}
        >
          首页
        </Link>
        <Link
          to="/counselor?tab=cases"
          aria-current={tab === 'cases' ? 'page' : undefined}
          className={styles.navItem}
        >
          个案
        </Link>
        <Link to="/counselor/support" className={styles.navItem}>
          交流
        </Link>
        <Link to="/counselor/notifications" className={styles.navItem}>
          通知
        </Link>
        <Link to="/profile" className={styles.navItem}>
          我的
        </Link>
      </nav>
    </section>
  );
}
