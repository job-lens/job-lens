import { Link } from 'react-router';
import { Buddy } from '@/shared/ui/Buddy';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import {
  useLearnerCases,
  useLearnerDashboard,
  useLearnerRecords,
  useLearnerTasks,
} from './queries';
import styles from './learner.module.css';

const statuses = {
  not_started: '准备开始',
  in_progress: '正在进行',
  paused: '已暂停',
  submitted: '等待反馈',
  changes_requested: '有新的反馈',
  completed: '已完成',
  cancelled: '已取消',
};
export function LearnerPage() {
  const dashboard = useLearnerDashboard();
  const tasks = useLearnerTasks();
  const cases = useLearnerCases();
  if (dashboard.isPending || tasks.isPending || cases.isPending) return <LoadingState />;
  if (!dashboard.data || !tasks.data || !cases.data)
    return (
      <ErrorPanel
        message="工作台暂时未能加载"
        retry={() => {
          void dashboard.refetch();
          void tasks.refetch();
          void cases.refetch();
        }}
      />
    );
  const items = tasks.data.pages.flatMap(page => page.items);
  const active = items.filter(task => !['completed', 'cancelled'].includes(task.status));
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>今天，从一步开始。</h1>
          <p className={styles.muted}>按自己的节奏完成。有需要时，随时停一停。</p>
        </div>
        <Link to="/learner/records" className="qx-btn qx-btn--secondary">
          训练记录
        </Link>
      </header>
      <div className={styles.summary} aria-label="训练概览">
        <div className={styles.metric}>
          <strong>{dashboard.data.pending_tasks}</strong>待完成
        </div>
        <div className={styles.metric}>
          <strong>{dashboard.data.pending_feedback}</strong>等待反馈
        </div>
        <div className={styles.metric}>
          <strong>{dashboard.data.pending_assistance}</strong>正在求助
        </div>
      </div>
      <ul className={styles.list}>
        {active.map(task => {
          const completed = task.progress.filter(step => step.status === 'completed').length;
          return (
            <li key={task.id} className={styles.card}>
              <div className={styles.row}>
                <h2>{task.title}</h2>
                <span className={styles.badge}>{statuses[task.status]}</span>
              </div>
              <p className={styles.muted}>{task.revision.goal}</p>
              <progress
                className={styles.progress}
                value={completed}
                max={Math.max(1, task.revision.steps.length)}
                aria-label={`${task.title}：完成 ${completed} 步，共 ${task.revision.steps.length} 步`}
              />
              <div className={styles.row}>
                <span className={styles.muted}>
                  {completed} / {task.revision.steps.length} 步
                  {task.due_on ? ` · ${task.due_on} 前完成` : ''}
                </span>
                <Link to={`/learner/tasks/${task.id}`} className="qx-btn qx-btn--primary">
                  {task.status === 'submitted'
                    ? '查看提交'
                    : task.status === 'changes_requested'
                      ? '查看反馈'
                      : task.status === 'not_started'
                        ? '查看任务'
                        : '继续任务'}
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      {active.length === 0 && (
        <div className={styles.empty}>
          <Buddy size={80} />
          <div>
            <h2>暂时没有待完成的任务</h2>
            <p className={styles.muted}>
              {cases.data.pages.some(page => page.items.length)
                ? '辅导员准备好下一次训练后，它会出现在这里。你也可以回看已完成的训练。'
                : '先填写个人资料，让接下来的支持更适合你。个案分配完成后，你会在这里看到任务。'}
            </p>
            <Link to="/profile" className="qx-btn qx-btn--secondary">
              完善个人资料
            </Link>
          </div>
        </div>
      )}
      {tasks.hasNextPage && (
        <button
          className="qx-btn qx-btn--secondary"
          disabled={tasks.isFetchingNextPage}
          onClick={() => void tasks.fetchNextPage()}
        >
          查看更多任务
        </button>
      )}
      {tasks.isError && (
        <ErrorPanel message="后续任务未能加载" retry={() => void tasks.fetchNextPage()} />
      )}
      <div className={styles.actions}>
        <Link to="/preferences">调整阅读与提醒</Link>
        {cases.data.pages
          .flatMap(page => page.items)
          .map(kase => (
            <Link key={kase.id} to={`/learner/support/${kase.id}`}>
              联系辅导员
            </Link>
          ))}
      </div>
    </section>
  );
}
export function RecordsPage() {
  const cases = useLearnerCases();
  if (cases.isPending) return <LoadingState />;
  if (!cases.data)
    return <ErrorPanel message="训练记录暂不可用" retry={() => void cases.refetch()} />;
  const items = cases.data.pages.flatMap(page => page.items);
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h1>训练记录</h1>
        <Link to="/learner" className="qx-btn qx-btn--secondary">
          返回工作台
        </Link>
      </header>
      <p className={styles.muted}>记录完成的过程，方便回看和沟通。</p>
      {!items.length && (
        <div className={styles.empty}>
          <Buddy size={80} />
          <p>开始第一次训练后，你的记录会出现在这里。</p>
        </div>
      )}
      {items.map(kase => (
        <CaseRecords key={kase.id} caseId={kase.id} />
      ))}
      {cases.hasNextPage && (
        <button
          className="qx-btn qx-btn--secondary"
          onClick={() => void cases.fetchNextPage()}
          disabled={cases.isFetchingNextPage}
        >
          查看更多个案
        </button>
      )}
    </section>
  );
}
function CaseRecords({ caseId }: { caseId: string }) {
  const records = useLearnerRecords(caseId);
  if (records.isPending) return <LoadingState />;
  if (!records.data)
    return <ErrorPanel message="这组记录未能加载" retry={() => void records.refetch()} />;
  const items = records.data.pages.flatMap(page => page.items);
  return (
    <div className={styles.page}>
      <ul className={styles.list}>
        {items.map(record => (
          <li className={styles.card} key={record.task_id}>
            <div className={styles.row}>
              <h2>{record.title}</h2>
              <span className={styles.badge}>{statuses[record.status]}</span>
            </div>
            <p className={styles.muted}>
              提交 {record.attempts} 次 · 查看提示 {record.hint_requests} 次 · 求助{' '}
              {record.assistance_requests} 次
              {record.observed_elapsed_ms !== null
                ? ` · 观测时长 ${Math.round(record.observed_elapsed_ms / 60000)} 分钟`
                : ''}
            </p>
            <Link to={`/learner/tasks/${record.task_id}`}>查看步骤与反馈</Link>
          </li>
        ))}
      </ul>
      {!items.length && <p className={styles.muted}>还没有训练记录。</p>}
      {records.hasNextPage && (
        <button
          className="qx-btn qx-btn--secondary"
          disabled={records.isFetchingNextPage}
          onClick={() => void records.fetchNextPage()}
        >
          查看更多记录
        </button>
      )}
      {records.isError && (
        <ErrorPanel message="后续记录未能加载" retry={() => void records.fetchNextPage()} />
      )}
    </div>
  );
}
