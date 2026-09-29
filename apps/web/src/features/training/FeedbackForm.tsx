import { useState } from 'react';
import { ApiError } from '@/shared/api/client';
import { LoadingState } from '@/shared/ui/AsyncState';
import type { components } from '@/shared/api/schema';
import { AnnotationEditor } from './AnnotationEditor';
import { OUTCOME_OPTIONS, TASK_STATUS_LABELS, TAG_OPTIONS } from './labels';
import type { FeedbackTag } from './labels';
import { useFeedback, useSnapshotRevision } from './queries';
import styles from './training.module.css';

type Submission = components['schemas']['Submission'];

const STEP_STATUS_LABELS = {
  pending: '未开始',
  in_progress: '进行中',
  completed: '已完成',
} as const;

export function FeedbackForm({ submission }: { submission: Submission }) {
  const revision = useSnapshotRevision(submission.snapshot.revision_id);
  const feedback = useFeedback(submission.id);

  const [outcome, setOutcome] = useState<'passed' | 'changes_requested'>('passed');
  const [message, setMessage] = useState('');
  const [tags, setTags] = useState<FeedbackTag[]>([]);
  const [redo, setRedo] = useState<Set<string>>(new Set());
  const [annotationIds, setAnnotationIds] = useState<string[]>([]);

  const busy = feedback.isPending;

  // 契约约束：通过 → redo_step_ids 必须为空；需修改 → 至少勾选一步。
  const redoIds = outcome === 'changes_requested' ? [...redo] : [];
  const valid = message.trim() !== '' && (outcome === 'passed' || redoIds.length > 0);

  function toggleTag(tag: FeedbackTag) {
    setTags(prev => (prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]));
  }
  function toggleRedo(stepId: string) {
    setRedo(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      return next;
    });
  }

  const progressById = new Map(submission.snapshot.progress.map(p => [p.step_id, p.status]));
  const evidenceIds = [...new Set(submission.snapshot.progress.flatMap(p => p.attachment_ids))];

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2>训练反馈</h2>
        <span className={styles.badge}>{TASK_STATUS_LABELS[submission.task_status]}</span>
      </header>

      <dl className={styles.metaList}>
        <div className={styles.metaRow}>
          <dt>提交次数</dt>
          <dd>第 {submission.attempt_no} 次</dd>
        </div>
        <div className={styles.metaRow}>
          <dt>提交时间</dt>
          <dd>{new Date(submission.submitted_at).toLocaleString('zh-CN')}</dd>
        </div>
      </dl>
      {submission.note && <p className={styles.note}>学员说明：{submission.note}</p>}

      <section className={styles.card} aria-label="步骤完成情况">
        <h3>步骤完成情况</h3>
        {revision.isPending ? (
          <LoadingState />
        ) : revision.data ? (
          <ul className={styles.stepReviewList}>
            {revision.data.steps.map(step => {
              const status = progressById.get(step.id) ?? 'pending';
              return (
                <li key={step.id} className={styles.stepReviewRow}>
                  <span className={styles.stepNo}>{step.position}</span>
                  <span className={styles.stepText}>{step.instruction || '（未填写说明）'}</span>
                  <span className={styles.status}>{STEP_STATUS_LABELS[status]}</span>
                  {outcome === 'changes_requested' && (
                    <label className={styles.check}>
                      <input
                        type="checkbox"
                        checked={redo.has(step.id)}
                        onChange={() => toggleRedo(step.id)}
                      />
                      需重做
                    </label>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className={styles.note}>步骤内容暂不可用</p>
        )}
      </section>

      {evidenceIds.length > 0 && (
        <section className={styles.card} aria-label="指引标注">
          <h3>指引标注</h3>
          <p className={styles.note}>
            点击证据图片放置标注点，填写说明后保存；保存的标注会随本次审核反馈给学员。
          </p>
          {evidenceIds.map(id => (
            <AnnotationEditor
              key={id}
              taskId={submission.task_id}
              submissionId={submission.id}
              assetId={id}
              onCreated={aid => setAnnotationIds(prev => [...prev, aid])}
            />
          ))}
        </section>
      )}

      <section className={styles.card} aria-labelledby="feedback-decision">
        <h3 id="feedback-decision">审核结论</h3>

        <fieldset className={styles.fieldset}>
          <legend>结论</legend>
          {OUTCOME_OPTIONS.map(opt => (
            <label key={opt.value} className={styles.radio}>
              <input
                type="radio"
                name="outcome"
                value={opt.value}
                checked={outcome === opt.value}
                onChange={() => setOutcome(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </fieldset>

        <fieldset className={styles.fieldset}>
          <legend>标签（可多选）</legend>
          {TAG_OPTIONS.map(tag => (
            <label key={tag.value} className={styles.check}>
              <input
                type="checkbox"
                checked={tags.includes(tag.value)}
                onChange={() => toggleTag(tag.value)}
              />
              {tag.label}
            </label>
          ))}
        </fieldset>

        <div className={styles.field}>
          <label htmlFor="feedback-message">反馈说明</label>
          <textarea
            id="feedback-message"
            value={message}
            maxLength={500}
            rows={3}
            placeholder="对本次提交的总体评价与修改意见"
            onChange={e => setMessage(e.target.value)}
          />
        </div>

        {outcome === 'changes_requested' && redoIds.length === 0 && (
          <p className={styles.note}>选择了「需修改」，请至少勾选一个需要重做的步骤。</p>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            disabled={busy || !valid}
            onClick={() =>
              feedback.mutate({
                version: submission.task_version,
                body: {
                  outcome,
                  message: message.trim(),
                  tags,
                  redo_step_ids: redoIds,
                  annotation_ids: annotationIds,
                },
              })
            }
          >
            提交审核
          </button>
        </div>

        {feedback.error && (
          <p role="alert" className={styles.error}>
            {feedback.error instanceof ApiError && feedback.error.status === 412
              ? '该提交已被他人审核，请刷新查看最新状态'
              : feedback.error instanceof ApiError && feedback.error.status === 409
                ? '该提交已有审核结论，请刷新'
                : '提交失败，请重试'}
          </p>
        )}
      </section>
    </div>
  );
}
