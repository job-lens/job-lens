import type { components } from '@/shared/api/schema';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { useRecords } from './queries';
import { TASK_STATUS_LABELS } from './status';
import styles from './counselor.module.css';

type TrainingRecord = components['schemas']['TrainingRecord'];

function fmtElapsed(ms: number | null): string {
  if (ms == null) return '未观测';
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec} 秒`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟`;
  return `${Math.floor(min / 60)} 小时 ${min % 60} 分`;
}

/** 能力报告（M4）：只呈现描述性训练记录，契约刻意不提供能力评分。 */
export function RecordsView({ caseId }: { caseId: string }) {
  const records = useRecords(caseId);

  if (records.isPending) return <LoadingState />;
  if (records.isError)
    return <ErrorPanel message="训练记录暂不可用" retry={() => void records.refetch()} />;

  const items = records.data?.items ?? [];
  return (
    <section aria-label="能力报告" className={styles.card}>
      <h3>能力报告</h3>
      {items.length === 0 ? (
        <p className={styles.empty}>暂无训练记录</p>
      ) : (
        <ul className={styles.recordList}>
          {items.map((r: TrainingRecord) => (
            <li key={r.task_id} className={styles.recordRow}>
              <div className={styles.recordHead}>
                <span className={styles.recordTitle}>{r.title}</span>
                <span className={styles.badge}>{TASK_STATUS_LABELS[r.status]}</span>
              </div>
              <p className={styles.recordStats}>
                尝试 {r.attempts} 次 · 提示请求 {r.hint_requests} 次 · 求助 {r.assistance_requests}{' '}
                次 · 观察时长 {fmtElapsed(r.observed_elapsed_ms)}
              </p>
              {r.measurement_note && <p className={styles.note}>{r.measurement_note}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
