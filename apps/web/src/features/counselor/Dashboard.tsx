import { Link } from 'react-router';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { Icon } from '@/shared/ui/Icon';
import { useCases, useCounselorDashboard } from './queries';
import { DISPLAY_STATUS_LABELS } from './status';
import styles from './counselor.module.css';

export function Dashboard() {
  const dashboard = useCounselorDashboard();
  const cases = useCases();
  if (dashboard.isPending || cases.isPending) return <LoadingState />;
  if (!dashboard.data || !cases.data)
    return (
      <ErrorPanel
        message="工作台暂不可用"
        retry={() => {
          void dashboard.refetch();
          void cases.refetch();
        }}
      />
    );
  const d = dashboard.data;
  const items = cases.data.pages.flatMap(page => page.items);
  const date = new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date());
  return (
    <div className={styles.dashboard}>
      <header className={styles.pageHeading}>
        <div>
          <p className={styles.date}>{date}</p>
          <h1>工作台</h1>
          <p className={styles.lede}>把注意力留给需要支持的人。</p>
        </div>
        <button
          type="button"
          className="qx-btn qx-btn--secondary"
          disabled={dashboard.isFetching || cases.isFetching}
          onClick={() => {
            void dashboard.refetch();
            void cases.refetch();
          }}
        >
          <Icon name="refresh" />
          {dashboard.isFetching || cases.isFetching ? '正在刷新…' : '刷新工作台'}
        </button>
      </header>
      {(dashboard.isError || cases.isError) && (
        <ErrorPanel
          message="刷新未完成，当前仍显示上次读取的数据。"
          retry={() => {
            void dashboard.refetch();
            void cases.refetch();
          }}
        />
      )}
      <section className={styles.metrics} aria-label="待办概览">
        <article className={styles.metricCard}>
          <span className={styles.metricLabel}>
            <Icon name="tasks" />
            待完成训练
          </span>
          <strong>{d.pending_tasks}</strong>
          <span className={styles.metricFoot}>项待完成</span>
        </article>
        <article className={styles.metricCard}>
          <span className={styles.metricLabel}>
            <Icon name="records" />
            待审核提交
          </span>
          <strong>{d.pending_feedback}</strong>
          <Link to="/counselor?tab=cases&status=awaiting_feedback" className="qx-btn qx-btn--ghost">
            查看待审核
            <Icon name="arrow" />
          </Link>
        </article>
        <article className={styles.metricCard}>
          <span className={styles.metricLabel}>
            <Icon name="chat" />
            待处理求助
          </span>
          <strong>{d.pending_assistance}</strong>
          <Link to="/counselor/support" className="qx-btn qx-btn--ghost">
            打开辅导
            <Icon name="arrow" />
          </Link>
        </article>
      </section>
      <div className={styles.overviewGrid}>
        <section className={styles.card} aria-labelledby="cases-heading">
          <div className={styles.sectionHeading}>
            <div>
              <h2 id="cases-heading">继续跟进</h2>
              <p className={styles.lede}>从已授权的个案继续工作</p>
            </div>
            <Link to="/counselor?tab=cases" className="qx-btn qx-btn--secondary">
              全部个案
              <Icon name="arrow" />
            </Link>
          </div>
          {items.length ? (
            <ul className={styles.compactList}>
              {items.slice(0, 5).map(kase => (
                <li key={kase.id}>
                  <span className={styles.caseAvatar} aria-hidden="true">
                    <Icon name="user" />
                  </span>
                  <div className={styles.compactTitle}>
                    <strong>个案 #{kase.id.slice(0, 8)}</strong>
                    <span>{DISPLAY_STATUS_LABELS[kase.display_status]}</span>
                  </div>
                  <Link
                    to={`/counselor/cases/${kase.id}`}
                    className="qx-btn qx-btn--secondary"
                    aria-label={`查看个案 #${kase.id.slice(0, 8)}`}
                  >
                    查看
                    <Icon name="arrow" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className={styles.empty}>
              <Icon name="users" />
              <h3>还没有分配的个案</h3>
              <p>分配完成后，学员资料与训练进度会出现在这里。</p>
              <Link to="/settings?tab=profile" className="qx-btn qx-btn--secondary">
                完善个人资料
              </Link>
            </div>
          )}
        </section>
        <section className={styles.card} aria-labelledby="workflow-heading">
          <h2 id="workflow-heading">支持流程</h2>
          <p className={styles.lede}>保留清晰、可回看的每一步。</p>
          <ol className={styles.workflow}>
            <li>
              <span>1</span>
              <div>
                <strong>了解与匹配</strong>
                <p>阅读资料，确认支持方向。</p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>安排训练</strong>
                <p>把岗位任务拆成具体步骤。</p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>反馈与跟进</strong>
                <p>查看提交，给出明确的下一步。</p>
              </div>
            </li>
          </ol>
          <Link to="/counselor?tab=cases" className="qx-btn qx-btn--primary qx-btn--block">
            进入个案管理
            <Icon name="arrow" />
          </Link>
        </section>
      </div>
      <p className={styles.syncNote}>
        数据更新于{' '}
        {new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(
          new Date(d.as_of),
        )}
        。只展示你有权访问的个案与训练。
      </p>
    </div>
  );
}
