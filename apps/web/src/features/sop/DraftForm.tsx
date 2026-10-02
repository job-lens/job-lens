import { useEffect, useRef, useState } from 'react';
import { ApiError } from '@/shared/api/client';
import type { components } from '@/shared/api/schema';
import { usePublishRevision, useSaveRevision } from './queries';
import { StepList } from './StepList';
import styles from './sop.module.css';

type SopRevision = components['schemas']['SopRevision'];
type Reminder = components['schemas']['Reminder'];
type SopStep = components['schemas']['SopStep'];

export function DraftForm({
  revision,
  caseId,
  onReload,
}: {
  revision: SopRevision;
  caseId: string;
  onReload?: () => Promise<SopRevision>;
}) {
  const save = useSaveRevision(revision.id);
  const publish = usePublishRevision(revision.id, caseId);

  const [goal, setGoal] = useState(revision.goal);
  const [steps, setSteps] = useState<SopStep[]>(revision.steps);
  const [reminder, setReminder] = useState<Reminder>(revision.reminder);
  const [dueOn, setDueOn] = useState('');
  const [base, setBase] = useState(revision);
  const edited = useRef(false);
  const [status, setStatus] = useState('');
  const [reloading, setReloading] = useState(false);
  function accept(value: SopRevision) {
    edited.current = false;
    setBase(value);
    setGoal(value.goal);
    setSteps(value.steps);
    setReminder(value.reminder);
  }

  // 保存/发布后经 invalidate 拉到最新值（含 version 递增）再同步回表单。
  useEffect(() => {
    if (edited.current) return;
    setBase(revision);
    setGoal(revision.goal);
    setSteps(revision.steps);
    setReminder(revision.reminder);
  }, [revision]);

  const busy = save.isPending || publish.isPending || reloading;
  const body = { goal, steps, reminder };
  const dirty =
    JSON.stringify(body) !==
    JSON.stringify({ goal: base.goal, steps: base.steps, reminder: base.reminder });
  async function saveDraft() {
    const value = await save.mutateAsync({ version: base.version, body });
    accept(value);
    return value;
  }
  async function publishSaved() {
    setStatus('');
    try {
      const latest = dirty ? await saveDraft() : base;
      await publish.mutateAsync({ version: latest.version, dueOn: dueOn || null });
      setStatus('SOP 已发布。');
    } catch {
      /* The visible mutation error keeps the edits available. */
    }
  }
  async function reload() {
    if (!onReload) return;
    setReloading(true);
    try {
      accept(await onReload());
      save.reset();
      publish.reset();
      setStatus('已读取最新草稿。');
    } catch {
      setStatus('重新读取失败，修改仍保留。');
    } finally {
      setReloading(false);
    }
  }
  const complete =
    goal.trim() !== '' && steps.length > 0 && steps.every(s => s.instruction.trim() !== '');

  return (
    <section aria-labelledby="sop-draft-title" className={styles.card}>
      <h3 id="sop-draft-title">草稿 · 第 {revision.revision_no} 版</h3>

      <fieldset
        className={styles.fields}
        disabled={busy}
        onChange={() => {
          edited.current = true;
        }}
      >
        <div className={styles.field}>
          <label htmlFor="sop-goal">总目标</label>
          <textarea
            id="sop-goal"
            value={goal}
            maxLength={1000}
            rows={3}
            placeholder="这份 SOP 要帮学员达到的最终目标"
            onChange={e => setGoal(e.target.value)}
          />
        </div>

        <h4>训练步骤</h4>
        <StepList
          steps={steps}
          disabled={busy}
          onChange={value => {
            edited.current = true;
            setSteps(value);
          }}
        />
        {steps.length === 0 && (
          <p className={styles.note}>至少添加一步，并填写总目标后才能发布。</p>
        )}

        <h4>提醒设置</h4>
        <div className={styles.fieldRow}>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={reminder.speech_enabled}
              onChange={e => setReminder({ ...reminder, speech_enabled: e.target.checked })}
            />
            语音播报
          </label>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={reminder.vibration_enabled}
              onChange={e => setReminder({ ...reminder, vibration_enabled: e.target.checked })}
            />
            震动提示
          </label>
        </div>
        <div className={styles.field}>
          <label htmlFor="sop-prompt-level">提示强度（1–3）</label>
          <input
            id="sop-prompt-level"
            type="number"
            min={1}
            max={3}
            step={1}
            value={reminder.prompt_level}
            onChange={e => setReminder({ ...reminder, prompt_level: Number(e.target.value) })}
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="sop-due">训练截止日期（可选）</label>
          <input id="sop-due" type="date" value={dueOn} onChange={e => setDueOn(e.target.value)} />
        </div>
      </fieldset>
      <div className={styles.actions}>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setStatus('');
            void saveDraft()
              .then(() => setStatus('草稿已保存。'))
              .catch(() => {});
          }}
        >
          保存草稿
        </button>
        <button
          type="button"
          disabled={busy || !complete}
          className="qx-btn qx-btn--primary"
          onClick={() => void publishSaved()}
        >
          发布 SOP
        </button>
      </div>

      {status && <p role="status">{status}</p>}
      {(save.error || publish.error) && onReload && (
        <button className="qx-btn qx-btn--text" disabled={busy} onClick={() => void reload()}>
          重新读取草稿
        </button>
      )}
      {save.error && (
        <p role="alert" className={styles.error}>
          {save.error instanceof ApiError && save.error.status === 412
            ? '内容已被他人修改，请刷新后重试'
            : '保存失败，请重试'}
        </p>
      )}
      {publish.error && (
        <p role="alert" className={styles.error}>
          {publish.error instanceof ApiError && publish.error.status === 412
            ? '内容已被他人修改，请刷新后重试'
            : publish.error instanceof ApiError && publish.error.status === 409
              ? '已存在进行中的训练任务，无法重复发布'
              : '发布失败，请重试'}
        </p>
      )}
    </section>
  );
}
