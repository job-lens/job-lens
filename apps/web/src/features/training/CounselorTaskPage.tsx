import { useState, type FormEvent } from 'react';
import { useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { PROMPT_LEVEL_OPTIONS, STEP_STATUS_LABELS, TASK_STATUS_LABELS } from './labels';
import { useCancelTask, usePromptOverride, useTask } from './queries';
import styles from './training.module.css';

/** 辅导员任务详情：查看训练进度、调整提示等级，必要时取消任务。 */
export function CounselorTaskPage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少任务编号" />;
  return <TaskDetail taskId={id} />;
}

function TaskDetail({ taskId }: { taskId: string }) {
  const task = useTask(taskId);
  if (task.isPending) return <LoadingState />;
  if (task.isError) {
    if (task.error instanceof ApiError && task.error.status === 404)
      return <ErrorPanel message="此任务不存在或您无权访问" />;
    return <ErrorPanel message="任务信息暂不可用" retry={() => void task.refetch()} />;
  }
  const t = task.data;
  if (!t) return null;

  const final = t.status === 'completed' || t.status === 'cancelled';
  const progressByStep = new Map(t.progress.map(p => [p.step_id, p.status]));

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h2>任务详情</h2>
        <span className={styles.badge}>{TASK_STATUS_LABELS[t.status]}</span>
      </header>

      <div className={styles.card}>
        <h3>任务信息</h3>
        <dl className={styles.metaList}>
          <div className={styles.metaRow}>
            <dt>标题</dt>
            <dd>{t.title}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>目标</dt>
            <dd>{t.revision.goal}</dd>
          </div>
          {t.due_on && (
            <div className={styles.metaRow}>
              <dt>截止日期</dt>
              <dd>{t.due_on}</dd>
            </div>
          )}
          {t.prompt_override && (
            <div className={styles.metaRow}>
              <dt>当前提示等级</dt>
              <dd>
                {PROMPT_LEVEL_OPTIONS.find(o => o.value === t.prompt_override!.prompt_level)
                  ?.label ?? t.prompt_override!.prompt_level}
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className={styles.card}>
        <h3>步骤进度</h3>
        <ul className={styles.stepReviewList}>
          {t.revision.steps.map(s => (
            <li key={s.id} className={styles.stepReviewRow}>
              <span className={styles.stepNo}>{s.position}</span>
              <span className={styles.stepText}>{s.instruction}</span>
              <span className={styles.status}>
                {STEP_STATUS_LABELS[progressByStep.get(s.id) ?? 'pending']}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {!final && (
        <PromptOverrideCard taskId={taskId} version={t.version} current={t.prompt_override} />
      )}
      {!final && <CancelCard taskId={taskId} version={t.version} />}
    </section>
  );
}

function PromptOverrideCard({
  taskId,
  version,
  current,
}: {
  taskId: string;
  version: number;
  current: { prompt_level: number; reason: string } | null;
}) {
  const override = usePromptOverride(taskId);
  const [level, setLevel] = useState(current?.prompt_level ?? 2);
  const [reason, setReason] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    override.mutate(
      { version, body: { prompt_level: level, reason: reason.trim() } },
      { onSuccess: () => setReason('') },
    );
  };

  return (
    <div className={styles.card}>
      <h3>调整提示等级</h3>
      <form onSubmit={submit}>
        <fieldset className={styles.fieldset}>
          <legend>提示等级</legend>
          {PROMPT_LEVEL_OPTIONS.map(o => (
            <label key={o.value} className={styles.radio}>
              <input
                type="radio"
                name="prompt_level"
                value={o.value}
                checked={level === o.value}
                onChange={() => setLevel(o.value)}
              />
              {o.label}
            </label>
          ))}
        </fieldset>
        <div className={styles.field}>
          <label htmlFor="prompt-reason">调整说明</label>
          <textarea
            id="prompt-reason"
            value={reason}
            maxLength={500}
            rows={2}
            placeholder="说明调整原因（必填，1–500 字）"
            onChange={e => setReason(e.target.value)}
          />
        </div>
        <button type="submit" disabled={override.isPending || !reason.trim()}>
          保存提示等级
        </button>
        {override.isError && (
          <p role="alert" className={styles.error}>
            {override.error instanceof ApiError && override.error.status === 412
              ? '内容已被他人修改，请刷新后重试'
              : '保存失败，请重试'}
          </p>
        )}
      </form>
    </div>
  );
}

function CancelCard({ taskId, version }: { taskId: string; version: number }) {
  const cancel = useCancelTask(taskId);
  const [reason, setReason] = useState('');
  const [confirming, setConfirming] = useState(false);

  if (!confirming) {
    return (
      <div className={styles.card}>
        <h3>取消任务</h3>
        <button type="button" onClick={() => setConfirming(true)}>
          取消任务
        </button>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <h3>取消任务</h3>
      <form
        onSubmit={e => {
          e.preventDefault();
          if (reason.trim()) cancel.mutate({ version, reason: reason.trim() });
        }}
      >
        <p className={styles.note}>取消后任务即结束，学员无法继续训练。请填写原因：</p>
        <div className={styles.field}>
          <textarea
            aria-label="取消原因"
            value={reason}
            maxLength={500}
            rows={2}
            onChange={e => setReason(e.target.value)}
          />
        </div>
        <div className={styles.actions}>
          <button type="submit" disabled={cancel.isPending || !reason.trim()}>
            确认取消
          </button>
          <button type="button" onClick={() => setConfirming(false)} disabled={cancel.isPending}>
            返回
          </button>
        </div>
        {cancel.isError && (
          <p role="alert" className={styles.error}>
            {cancel.error instanceof ApiError && cancel.error.status === 412
              ? '内容已被他人修改，请刷新后重试'
              : '取消失败，请重试'}
          </p>
        )}
      </form>
    </div>
  );
}
