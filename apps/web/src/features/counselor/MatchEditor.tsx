import { useEffect, useState } from 'react';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { useConfirmMatch, useMatch, useSaveMatch } from './queries';
import styles from './counselor.module.css';

export function MatchEditor({ caseId }: { caseId: string }) {
  const match = useMatch(caseId);
  const save = useSaveMatch(caseId);
  const confirm = useConfirmMatch(caseId);

  const [direction, setDirection] = useState('');
  const [focus, setFocus] = useState('');
  const [basis, setBasis] = useState('');
  const [cycleWeeks, setCycleWeeks] = useState(4);

  // 匹配草稿已存在时回填；保存/确认后经 invalidate 重新拉到最新值再同步。
  useEffect(() => {
    if (!match.data) return;
    setDirection(match.data.direction);
    setFocus(match.data.focus);
    setBasis(match.data.basis);
    setCycleWeeks(match.data.cycle_weeks);
  }, [match.data]);

  if (match.isPending) return <LoadingState />;
  if (match.isError) {
    if (match.error instanceof ApiError && match.error.status === 404)
      return <ErrorPanel message="此个案不存在或您无权访问" />;
    return <ErrorPanel message="匹配信息暂不可用" retry={() => void match.refetch()} />;
  }
  if (!match.data) return null;

  const current = match.data;
  const confirmed = current.state === 'confirmed';
  const requiredMissing = !direction.trim() || !focus.trim() || !basis.trim();
  const busy = save.isPending || confirm.isPending;
  const error = save.error ?? confirm.error;

  return (
    <section aria-labelledby="match-title" className={styles.card}>
      <h3 id="match-title">支持匹配{confirmed ? '（已确认）' : ''}</h3>
      {confirmed && <p className={styles.note}>匹配已确认，内容冻结。请前往制定 SOP。</p>}

      <div className={styles.field}>
        <label htmlFor="match-direction">支持方向</label>
        <input
          id="match-direction"
          value={direction}
          maxLength={80}
          disabled={confirmed}
          onChange={e => setDirection(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="match-focus">训练重点</label>
        <textarea
          id="match-focus"
          value={focus}
          maxLength={500}
          rows={3}
          disabled={confirmed}
          onChange={e => setFocus(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="match-cycle">支持周期（周，1–52）</label>
        <input
          id="match-cycle"
          type="number"
          min={1}
          max={52}
          value={cycleWeeks}
          disabled={confirmed}
          onChange={e => setCycleWeeks(Number(e.target.value))}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="match-basis">匹配依据</label>
        <textarea
          id="match-basis"
          value={basis}
          maxLength={1000}
          rows={3}
          disabled={confirmed}
          onChange={e => setBasis(e.target.value)}
        />
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          disabled={confirmed || busy}
          onClick={() =>
            save.mutate({
              version: current.version,
              body: { direction, focus, cycle_weeks: cycleWeeks, basis },
            })
          }
        >
          保存草稿
        </button>
        <button
          type="button"
          disabled={confirmed || requiredMissing || busy}
          onClick={() => confirm.mutate({ version: current.version })}
        >
          确认匹配
        </button>
      </div>

      {error && (
        <p role="alert" className={styles.error}>
          {error instanceof ApiError && error.status === 412
            ? '内容已被他人修改，请刷新后重试'
            : '保存失败，请重试'}
        </p>
      )}
    </section>
  );
}
