import { useState } from 'react';
import { Link } from 'react-router';
import type { components } from '@/shared/api/schema';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { ASSISTANCE_STATE_LABELS, MODE_LABELS } from './labels';
import { useAssistanceRequests } from './queries';
import styles from './support.module.css';

type Assistance = components['schemas']['Assistance'];
type Filter = 'queued' | 'accepted' | 'all';

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'queued', label: '待接单' },
  { value: 'accepted', label: '已接单' },
  { value: 'all', label: '全部' },
];

/** 辅导员「交流」入口：求助工作台，默认看待接单。 */
export function CounselorSupportPage() {
  const [filter, setFilter] = useState<Filter>('queued');
  const requests = useAssistanceRequests(filter === 'all' ? undefined : filter);

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h2>求助工作台</h2>
      </header>

      <div className={styles.filters}>
        {FILTERS.map(f => (
          <button
            key={f.value}
            type="button"
            aria-pressed={filter === f.value}
            className={styles.filter}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {requests.isPending ? (
        <LoadingState />
      ) : requests.isError ? (
        <ErrorPanel message="求助列表暂不可用" retry={() => void requests.refetch()} />
      ) : (
        <RequestList items={requests.data?.items ?? []} />
      )}
    </section>
  );
}

function RequestList({ items }: { items: Assistance[] }) {
  if (items.length === 0) return <p className={styles.empty}>暂无求助</p>;
  return (
    <ul className={styles.list}>
      {items.map(r => (
        <li key={r.id}>
          <Link to={`/counselor/support/${r.id}`} className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.badge}>{ASSISTANCE_STATE_LABELS[r.state]}</span>
              <span className={styles.badge}>{MODE_LABELS[r.preferred_mode]}</span>
              <span className={styles.time}>{new Date(r.created_at).toLocaleString()}</span>
            </div>
            <p className={styles.message}>{r.message}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
