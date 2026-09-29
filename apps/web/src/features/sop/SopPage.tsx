import { useState } from 'react';
import { useParams } from 'react-router';
import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { RevisionEditor } from './RevisionEditor';
import { useCreatePlan, usePlans } from './queries';
import styles from './sop.module.css';

export function SopPage() {
  const { id } = useParams();
  if (!id) return <ErrorPanel message="缺少个案编号" />;
  return <SopWorkspace caseId={id} />;
}

function SopWorkspace({ caseId }: { caseId: string }) {
  const plans = usePlans(caseId);
  const create = useCreatePlan(caseId);
  const [title, setTitle] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (plans.isPending) return <LoadingState />;
  if (plans.isError) {
    if (plans.error instanceof ApiError && plans.error.status === 404)
      return <ErrorPanel message="此个案不存在或您无权访问" />;
    return <ErrorPanel message="SOP 计划暂不可用" retry={() => void plans.refetch()} />;
  }
  if (!plans.data) return null;

  const items = plans.data.items;

  // 无计划：创建首份。
  if (items.length === 0) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <h2>SOP 规划工作台</h2>
        </header>
        <section className={styles.card}>
          <h3>创建首份 SOP 计划</h3>
          <div className={styles.field}>
            <label htmlFor="plan-title">计划标题</label>
            <input
              id="plan-title"
              value={title}
              maxLength={120}
              placeholder="例如：咖啡店收银岗位训练"
              onChange={e => setTitle(e.target.value)}
            />
          </div>
          <div className={styles.actions}>
            <button
              type="button"
              disabled={create.isPending || !title.trim()}
              onClick={() => create.mutate({ title: title.trim() })}
            >
              创建计划
            </button>
          </div>
          {create.error && (
            <p role="alert" className={styles.error}>
              {create.error instanceof ApiError && create.error.status === 409
                ? '该个案已存在 SOP 计划，请刷新'
                : '创建失败，请重试'}
            </p>
          )}
        </section>
      </div>
    );
  }

  // 有计划：默认第一份，多份时可切换。
  const current = items.find(p => p.id === selectedId) ?? items[0];
  const revisionId = current.draft_revision_id ?? current.published_revision_id;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2>SOP 规划工作台</h2>
        <span className={styles.badge}>{current.title}</span>
      </header>

      {items.length > 1 && (
        <div className={styles.field}>
          <label htmlFor="plan-select">选择计划</label>
          <select id="plan-select" value={current.id} onChange={e => setSelectedId(e.target.value)}>
            {items.map(p => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
      )}

      {revisionId ? (
        <RevisionEditor planId={current.id} revisionId={revisionId} caseId={caseId} />
      ) : (
        <section className={styles.card}>
          <h3>尚无版本</h3>
          <p className={styles.note}>这份计划还没有任何版本。</p>
        </section>
      )}
    </div>
  );
}
