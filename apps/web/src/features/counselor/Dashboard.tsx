import { Link } from 'react-router';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { useCases, useCounselorDashboard } from './queries';
import styles from './counselor.module.css';

function greeting(now: Date): string {
  const hour = now.getHours();
  if (hour < 6) return '夜深了';
  if (hour < 12) return '早上好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

const dateLabel = (now: Date) =>
  new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }).format(now);

export function Dashboard() {
  const dashboard = useCounselorDashboard();
  const cases = useCases();

  if (dashboard.isPending || cases.isPending) return <LoadingState />;
  if (dashboard.isError)
    return <ErrorPanel message="工作台暂不可用" retry={() => void dashboard.refetch()} />;
  if (cases.isError)
    return <ErrorPanel message="个案列表暂不可用" retry={() => void cases.refetch()} />;
  if (!dashboard.data || !cases.data) return null;

  const d = dashboard.data;
  const items = cases.data.items;
  // 今日任务列表的三条来自派生状态分组；「反馈核验」计数来自 Dashboard.pending_feedback。
  const byStatus = (status: (typeof items)[number]['display_status']) =>
    items.filter(c => c.display_status === status).length;

  const now = new Date();
  return (
    <div className={styles.dashboard}>
      <header className={styles.greeting}>
        <h2>{greeting(now)}</h2>
        <p className={styles.date}>{dateLabel(now)}</p>
        <Link to="/preferences">低刺激模式设置</Link>
      </header>

      <section aria-labelledby="progress-title" className={styles.card}>
        <h3 id="progress-title">今日待完成支持</h3>
        <p className={styles.bigCount}>
          {d.pending_tasks}
          <span className={styles.countUnit}> 项待完成</span>
        </p>
        {/* 已完成 x/总数 y 的进度条待后端补计数字段（Issue #2），此处只呈现待完成数量。 */}
      </section>

      <section aria-labelledby="tasks-title" className={styles.card}>
        <h3 id="tasks-title">今日任务</h3>
        <ul className={styles.taskList}>
          <li>
            <Link to="/counselor?tab=cases">整理待匹配个案 · {byStatus('pending_match')}</Link>
          </li>
          <li>
            <Link to="/counselor?tab=cases">制定 SOP · {byStatus('sop_pending')}</Link>
          </li>
          <li>
            <Link to="/counselor?tab=cases">反馈核验 · {d.pending_feedback}</Link>
          </li>
        </ul>
      </section>
    </div>
  );
}
