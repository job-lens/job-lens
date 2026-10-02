import { useSearchParams, Link } from 'react-router';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { Icon } from '@/shared/ui/Icon';
import { useCases } from './queries';
import { CASE_FILTERS, DISPLAY_STATUS_LABELS, type CaseFilter } from './status';
import styles from './counselor.module.css';

export function CaseList() {
  const [params, setParams] = useSearchParams();
  const rawFilter = params.get('status');
  const filter: CaseFilter = CASE_FILTERS.some(item => item.value === rawFilter)
    ? (rawFilter as CaseFilter)
    : 'all';
  const query = params.get('q') || '';
  const cases = useCases();
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set('tab', 'cases');
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key === 'q' });
  }
  if (cases.isPending) return <LoadingState />;
  if (!cases.data)
    return <ErrorPanel message="个案列表暂不可用" retry={() => void cases.refetch()} />;
  const items = cases.data.pages.flatMap(page => page.items);
  const visible = items.filter(
    kase =>
      (filter === 'all' || kase.display_status === filter) &&
      kase.id.toLowerCase().includes(query.trim().toLowerCase()),
  );
  return (
    <section className={styles.page} aria-label="个案列表">
      <header className={styles.pageHeading}>
        <div>
          <h1>个案管理</h1>
          <p className={styles.lede}>查看学员的支持进度，安排下一步训练。</p>
        </div>
        <button
          type="button"
          className="qx-btn qx-btn--secondary"
          disabled={cases.isFetching}
          onClick={() => void cases.refetch()}
        >
          <Icon name="refresh" />
          {cases.isRefetching ? '正在刷新…' : '刷新列表'}
        </button>
      </header>
      <div className={styles.listPanel}>
        <div className={styles.listToolbar}>
          <label className={styles.search}>
            <Icon name="search" />
            <span className="sr-only">按个案编号搜索</span>
            <input
              type="search"
              value={query}
              placeholder="搜索已加载的个案编号"
              onChange={event => update('q', event.target.value)}
            />
          </label>
          <span className={styles.loadedCount}>已加载 {items.length} 个个案</span>
        </div>
        <div role="group" aria-label="按状态筛选已加载个案" className={styles.filters}>
          {CASE_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              className={styles.filter}
              onClick={() => update('status', value === 'all' ? '' : value)}
            >
              {label}
            </button>
          ))}
        </div>
        {visible.length === 0 ? (
          <div className={styles.empty}>
            <Icon name={items.length ? 'search' : 'users'} />
            <h2>{items.length ? '没有符合条件的个案' : '还没有分配的个案'}</h2>
            <p>
              {cases.hasNextPage
                ? '筛选只作用于已加载的个案，可以继续加载下一页。'
                : items.length
                  ? '试着清除搜索或切换状态。'
                  : '分配完成后，你可以在这里查看资料、安排训练并跟进反馈。'}
            </p>
            {(query || filter !== 'all') && (
              <button
                className="qx-btn qx-btn--secondary"
                type="button"
                onClick={() => setParams({ tab: 'cases' })}
              >
                清除筛选
              </button>
            )}
          </div>
        ) : (
          <ul className={styles.caseList}>
            {visible.map(kase => (
              <li key={kase.id}>
                <Link to={`/counselor/cases/${kase.id}`} className={styles.caseCard}>
                  <span className={styles.caseAvatar} aria-hidden="true">
                    <Icon name="user" />
                  </span>
                  <span className={styles.caseId}>
                    <strong>个案 #{kase.id.slice(0, 8)}</strong>
                    <small>
                      {kase.current_task_id
                        ? '已有训练任务，可查看进度与提交'
                        : '阅读资料，继续准备下一步'}
                    </small>
                  </span>
                  <span className={styles.badge}>{DISPLAY_STATUS_LABELS[kase.display_status]}</span>
                  <span
                    className={`qx-btn qx-btn--secondary ${styles.caseLink}`}
                    aria-hidden="true"
                  >
                    查看个案
                    <Icon name="arrow" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {cases.isError && (
          <ErrorPanel
            message={
              cases.isFetchNextPageError
                ? '下一页未能加载，已有个案仍保留。'
                : '刷新未完成，当前显示上次读取的数据。'
            }
            retry={() =>
              void (cases.isFetchNextPageError ? cases.fetchNextPage() : cases.refetch())
            }
          />
        )}
        <footer className={styles.listFooter}>
          <span>当前显示 {visible.length} 个 · 筛选范围为已加载数据</span>
          {cases.hasNextPage ? (
            <button
              type="button"
              className="qx-btn qx-btn--secondary"
              disabled={cases.isFetching}
              onClick={() => void cases.fetchNextPage()}
            >
              {cases.isFetchingNextPage ? '正在加载…' : '加载更多个案'}
            </button>
          ) : (
            <span>已加载全部</span>
          )}
        </footer>
      </div>
    </section>
  );
}
