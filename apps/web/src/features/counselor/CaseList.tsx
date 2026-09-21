import { useState } from 'react';
import { Link } from 'react-router';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { useCases } from './queries';
import { CASE_FILTERS, DISPLAY_STATUS_LABELS, type CaseFilter } from './status';
import styles from './counselor.module.css';

export function CaseList() {
  const [filter, setFilter] = useState<CaseFilter>('all');
  const cases = useCases();

  if (cases.isPending) return <LoadingState />;
  if (cases.isError)
    return <ErrorPanel message="个案列表暂不可用" retry={() => void cases.refetch()} />;
  if (!cases.data) return null;

  const items = cases.data.items;
  const visible = filter === 'all' ? items : items.filter(c => c.display_status === filter);
  const emptyHint = filter === 'all' ? '' : DISPLAY_STATUS_LABELS[filter];

  return (
    <section aria-label="个案列表">
      <div role="group" aria-label="按状态筛选" className={styles.filters}>
        {CASE_FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            aria-pressed={filter === value}
            className={styles.filter}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className={styles.empty}>暂无{emptyHint}个案</p>
      ) : (
        <ul className={styles.caseList}>
          {visible.map(c => (
            <li key={c.id}>
              <Link to={`/counselor/cases/${c.id}`} className={styles.caseCard}>
                <span className={styles.badge}>{DISPLAY_STATUS_LABELS[c.display_status]}</span>
                {/* 契约 Case 未内嵌学员姓名/编号/标签，需后端补字段；先以短编号占位。 */}
                <span className={styles.caseId}>个案 #{c.id.slice(0, 8)}</span>
                <span className={styles.caseLink} aria-hidden="true">
                  查看画像 →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
