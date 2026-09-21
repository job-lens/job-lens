import type { components } from '@/shared/api/schema';
import { OUTCOME_LABELS, TAG_LABELS } from './labels';
import styles from './training.module.css';

type Submission = components['schemas']['Submission'];

export function FeedbackView({ submission }: { submission: Submission }) {
  const fb = submission.feedback;
  if (!fb) return null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2>训练反馈</h2>
        <span className={styles.badge}>{OUTCOME_LABELS[fb.outcome]}</span>
      </header>

      <section className={styles.card}>
        <h3>审核结论（已提交）</h3>
        <p className={styles.readonly}>{fb.message}</p>
        {fb.tags.length > 0 && (
          <p className={styles.note}>标签：{fb.tags.map(t => TAG_LABELS[t]).join('、')}</p>
        )}
        {fb.redo_step_ids.length > 0 && (
          <p className={styles.note}>已要求重做 {fb.redo_step_ids.length} 步。</p>
        )}
        <p className={styles.note}>审核时间：{new Date(fb.created_at).toLocaleString('zh-CN')}</p>
      </section>
    </div>
  );
}
