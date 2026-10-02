import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import { usePrompt } from '@/shared/platform/context';
import { usePreferences } from '@/shared/preferences/public';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { AnnotationView } from '@/shared/ui/AnnotationView';
import { AssetInput } from '@/shared/ui/AssetInput';
import { Companions } from '@/shared/ui/Companions';
import { WorkIllustration } from '@/shared/ui/WorkIllustration';
import { TASK_STATUS_LABELS } from './labels';
import {
  useRecordHint,
  useSaveProgress,
  useSubmitTask,
  useSubmissions,
  useTask,
  useTaskAction,
} from './queries';
import styles from './learner-training.module.css';
type Task = components['schemas']['Task'];
export function TrainingPage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少任务编号" />;
  return <TaskDetail key={id} taskId={id} />;
}
function TaskDetail({ taskId }: { taskId: string }) {
  const task = useTask(taskId);
  if (task.isPending) return <LoadingState />;
  if (!task.data)
    return (
      <ErrorPanel
        message={
          task.error instanceof ApiError && task.error.status === 404
            ? '此任务不存在或您无权访问'
            : '任务暂不可用'
        }
        retry={() => void task.refetch()}
      />
    );
  return (
    <TaskWorkspace
      task={task.data}
      reload={async () => {
        const result = await task.refetch();
        if (result.error) throw result.error;
        return result.data;
      }}
    />
  );
}
function TaskWorkspace({ task, reload }: { task: Task; reload: () => Promise<Task | undefined> }) {
  const action = useTaskAction(task.id),
    save = useSaveProgress(task.id),
    submit = useSubmitTask(task.id),
    hint = useRecordHint(task.id);
  const submissions = useSubmissions(task.id);
  const [note, setNote] = useState('');
  const [evidence, setEvidence] = useState<Record<string, string[]>>({});
  const [showHint, setShowHint] = useState(false);
  const [notice, setNotice] = useState('');
  const prompt = usePrompt(),
    preferences = usePreferences();
  const progress = new Map(task.progress.map(p => [p.step_id, p]));
  const step = task.revision.steps.find(s => s.id === task.current_step_id);
  const completed = task.progress.filter(p => p.status === 'completed').length;
  const busy = action.isPending || save.isPending || submit.isPending;
  const error = action.error ?? save.error ?? submit.error;
  const latest = submissions.data?.items[0];
  useEffect(() => {
    setShowHint(false);
    return () => prompt.cancelSpeech();
  }, [step?.id, prompt]);
  async function refresh() {
    try {
      await reload();
      action.reset();
      save.reset();
      submit.reset();
      setNotice('已读取最新进度。');
    } catch {
      setNotice('重新读取失败，请稍后重试。');
    }
  }
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <Link to="/learner">返回任务</Link>
        <span className="qx-meta">{TASK_STATUS_LABELS[task.status]}</span>
      </header>
      <div className={styles.workspace}>
        <nav className={styles.steps} aria-label="训练步骤">
          <h2>{task.title}</h2>
          <ol>
            {task.revision.steps.map(s => (
              <li key={s.id} aria-current={s.id === step?.id ? 'step' : undefined}>
                <span>{progress.get(s.id)?.status === 'completed' ? '✓' : s.position}</span>
                <p>{s.instruction}</p>
              </li>
            ))}
          </ol>
          <span className="qx-meta">
            已完成 {completed} / {task.revision.steps.length} 步
          </span>
        </nav>
        <div className={styles.focus}>
          {task.status === 'not_started' ? (
            <>
              <Companions />
              <h1>{task.revision.goal}</h1>
              <p>按自己的节奏，一次完成一步。</p>
              {task.due_on && <p className="qx-meta">截止日期 · {task.due_on}</p>}
              <button
                className="qx-btn qx-btn--primary"
                disabled={busy}
                onClick={() => action.mutate({ version: task.version, action: 'start' })}
              >
                开始训练
              </button>
            </>
          ) : task.status === 'paused' ? (
            <>
              <Companions />
              <h1>休息一下，也没关系。</h1>
              <p>进度已经保存，准备好后继续。</p>
              <button
                className="qx-btn qx-btn--primary"
                disabled={busy}
                onClick={() => action.mutate({ version: task.version, action: 'resume' })}
              >
                继续训练
              </button>
            </>
          ) : task.status === 'changes_requested' ? (
            <>
              <Companions />
              <h1>一起调整这几步。</h1>
              <p>{latest?.feedback?.message ?? '辅导员建议已收到，请查看下方反馈。'}</p>
              <button
                className="qx-btn qx-btn--primary"
                disabled={busy}
                onClick={() => action.mutate({ version: task.version, action: 'resume' })}
              >
                继续修改
              </button>
            </>
          ) : task.status === 'submitted' ? (
            <>
              <WorkIllustration step={2} />
              <h1>结果已提交。</h1>
              <p>辅导员审核后，反馈会出现在这里。</p>
              <button className="qx-btn qx-btn--ghost" onClick={() => void refresh()}>
                查看最新反馈
              </button>
            </>
          ) : task.status === 'completed' ? (
            <>
              <Companions />
              <h1>这次训练完成了。</h1>
              <p>{latest?.feedback?.message ?? '你可以在记录中回顾这次练习。'}</p>
              <Link className="qx-btn qx-btn--primary" to="/learner/records">
                查看训练记录
              </Link>
            </>
          ) : task.status === 'cancelled' ? (
            <>
              <h1>这项训练已结束。</h1>
              <p>如有疑问，可以联系辅导员。</p>
              <Link className="qx-btn qx-btn--ghost" to="/learner">
                返回任务
              </Link>
            </>
          ) : step ? (
            <>
              <WorkIllustration step={Math.min(step.position - 1, 2)} />
              <span className="qx-meta">第 {step.position} 步</span>
              <h1>{step.instruction}</h1>
              {step.media_ids.length > 0 && (
                <ul className={styles.media}>
                  {step.media_ids.map(id => (
                    <li key={id}>
                      <a href={`/api/v1/files/${id}/content`} target="_blank" rel="noreferrer">
                        查看步骤材料
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              <details open={step.evidence_required}>
                <summary>
                  {step.evidence_required ? '提交这一步的附件' : '添加附件（可选）'}
                </summary>
                <AssetInput
                  key={step.id}
                  caseId={task.case_id}
                  taskId={task.id}
                  purpose="task_evidence"
                  value={evidence[step.id] ?? progress.get(step.id)?.attachment_ids ?? []}
                  onChange={ids => setEvidence(current => ({ ...current, [step.id]: ids }))}
                  disabled={busy}
                />
              </details>
              {step.evidence_required && (
                <p className="qx-meta">这一步需要附件，通过安全检查后可以完成。</p>
              )}
              <button
                className="qx-btn qx-btn--primary"
                disabled={
                  busy ||
                  (step.evidence_required &&
                    !(evidence[step.id] ?? progress.get(step.id)?.attachment_ids ?? []).length)
                }
                onClick={() =>
                  save.mutate({
                    version: task.version,
                    stepId: step.id,
                    attachmentIds: evidence[step.id] ?? progress.get(step.id)?.attachment_ids ?? [],
                  })
                }
              >
                这一步完成了
              </button>
              <div className={styles.secondary}>
                <button
                  className="qx-btn qx-btn--text"
                  disabled={busy}
                  onClick={() => action.mutate({ version: task.version, action: 'pause' })}
                >
                  暂停一下
                </button>
                <button
                  className="qx-btn qx-btn--text"
                  onClick={() => {
                    setShowHint(!showHint);
                    if (!showHint) hint.mutate(step.id);
                  }}
                >
                  看提示
                </button>
                {!preferences.quiet_mode &&
                  preferences.speech_enabled &&
                  task.revision.reminder.speech_enabled && (
                    <button
                      className="qx-btn qx-btn--text"
                      onClick={() => {
                        const result = prompt.speak(step.instruction);
                        if (!result.ok) setNotice('此设备暂不支持语音，文字指引仍可使用。');
                      }}
                    >
                      听一下
                    </button>
                  )}
                <Link
                  className="qx-btn qx-btn--text"
                  to={`/learner/support/${task.case_id}?task=${task.id}&step=${step.id}`}
                >
                  联系辅导员
                </Link>
              </div>
              {showHint && (
                <p className={styles.hint}>
                  训练目标：{task.revision.goal}。需要帮助时，可以把问题发给辅导员。
                </p>
              )}
              {hint.error && <p role="status">提示次数暂未记录，操作指引仍可使用。</p>}
            </>
          ) : (
            <>
              <WorkIllustration step={2} />
              <h1>步骤都完成了。</h1>
              <label className={styles.note}>
                给辅导员的说明（可选）
                <textarea
                  className="qx-textarea"
                  maxLength={500}
                  value={note}
                  disabled={busy}
                  onChange={e => setNote(e.target.value)}
                />
              </label>
              <button
                className="qx-btn qx-btn--primary"
                disabled={busy}
                onClick={() =>
                  submit.mutate({ version: task.version, note }, { onSuccess: () => setNote('') })
                }
              >
                提交结果
              </button>
            </>
          )}
          {busy && <p role="status">正在保存…</p>}
          {error && (
            <div role="alert">
              <p>
                {error instanceof ApiError && [412, 428].includes(error.status)
                  ? '进度已更新，请重新读取后继续。'
                  : error instanceof ApiError
                    ? error.message
                    : '保存未完成，请重试。'}
              </p>
              <button className="qx-btn qx-btn--text" onClick={() => void refresh()}>
                重新读取进度
              </button>
            </div>
          )}
          {notice && <p role="status">{notice}</p>}
        </div>
      </div>
      <section className={styles.history} aria-label="提交与反馈">
        <h2>提交与反馈</h2>
        {submissions.isPending ? (
          <LoadingState />
        ) : submissions.isError ? (
          <ErrorPanel message="提交记录暂不可用" retry={() => void submissions.refetch()} />
        ) : !submissions.data?.items.length ? (
          <p className="qx-meta">完成步骤后，在这里查看提交结果。</p>
        ) : (
          submissions.data.items.map(s => (
            <article key={s.id}>
              <header>
                <span>第 {s.attempt_no} 次提交</span>
                <time dateTime={s.submitted_at}>
                  {new Date(s.submitted_at).toLocaleString('zh-CN')}
                </time>
              </header>
              {s.note && <p>{s.note}</p>}
              {s.feedback ? (
                <>
                  <strong>{s.feedback.outcome === 'passed' ? '通过' : '需要调整'}</strong>
                  <p>{s.feedback.message}</p>
                  {s.feedback.annotation_ids.map(id => (
                    <AnnotationView key={id} id={id} />
                  ))}
                  {s.feedback.redo_step_ids.length > 0 && (
                    <ul>
                      {task.revision.steps
                        .filter(step => s.feedback!.redo_step_ids.includes(step.id))
                        .map(step => (
                          <li key={step.id}>
                            第 {step.position} 步 · {step.instruction}
                          </li>
                        ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="qx-meta">等待审核</p>
              )}
            </article>
          ))
        )}
        {submissions.hasNextPage && (
          <button
            className="qx-btn qx-btn--secondary"
            disabled={submissions.isFetchingNextPage}
            onClick={() => void submissions.fetchNextPage()}
          >
            查看更多提交
          </button>
        )}
      </section>
    </section>
  );
}
