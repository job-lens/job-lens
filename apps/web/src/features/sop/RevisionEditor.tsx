import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { DraftForm } from './DraftForm';
import { useCreateRevision, useRevision } from './queries';
import styles from './sop.module.css';

export function RevisionEditor({
  planId,
  revisionId,
  caseId,
}: {
  planId: string;
  revisionId: string;
  caseId: string;
}) {
  const revision = useRevision(revisionId);
  const createDraft = useCreateRevision(planId, caseId);

  if (revision.isPending) return <LoadingState />;
  if (revision.isError) {
    return <ErrorPanel message="SOP 版本暂不可用" retry={() => void revision.refetch()} />;
  }
  if (!revision.data) return null;

  const rev = revision.data;
  if (rev.state === 'draft') {
    return <DraftForm revision={rev} caseId={caseId} />;
  }

  // 已发布：只读摘要 + 基于此版新建草稿。
  return (
    <section aria-labelledby="sop-published" className={styles.card}>
      <h3 id="sop-published">已发布 · 第 {rev.revision_no} 版</h3>
      <p className={styles.note}>
        发布于 {rev.published_at ? new Date(rev.published_at).toLocaleString('zh-CN') : '—'}
        ，内容已冻结。
      </p>
      <div className={styles.field}>
        <label>总目标</label>
        <p className={styles.readonly}>{rev.goal || '（未填写）'}</p>
      </div>
      <div className={styles.field}>
        <label>训练步骤（{rev.steps.length} 步）</label>
        <ol className={styles.readonlyList}>
          {rev.steps.map(s => (
            <li key={s.id}>{s.instruction || '（未填写说明）'}</li>
          ))}
        </ol>
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          disabled={createDraft.isPending}
          onClick={() => createDraft.mutate({ base_revision_id: rev.id })}
        >
          基于此版新建草稿
        </button>
      </div>
      {createDraft.error && (
        <p role="alert" className={styles.error}>
          {createDraft.error instanceof ApiError && createDraft.error.status === 409
            ? '已有一份进行中的草稿，请先完成或发布它'
            : '新建草稿失败，请重试'}
        </p>
      )}
    </section>
  );
}
