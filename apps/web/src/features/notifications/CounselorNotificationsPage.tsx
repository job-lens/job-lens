import { ApiError } from '@/shared/api/client';
import { ErrorPanel, LoadingState } from '@/shared/ui/AsyncState';
import { RESOURCE_TYPE_LABELS } from './labels';
import { useMarkRead, useNotifications } from './queries';
import styles from './notifications.module.css';

/** 辅导员通知列表：本人持久化通知，逐条标记已读。 */
export function CounselorNotificationsPage() {
  const notifications = useNotifications();
  const markRead = useMarkRead();

  if (notifications.isPending) return <LoadingState />;
  if (notifications.isError) {
    if (notifications.error instanceof ApiError && notifications.error.status === 410)
      return (
        <ErrorPanel message="通知记录已过期，请刷新" retry={() => void notifications.refetch()} />
      );
    return <ErrorPanel message="通知暂不可用" retry={() => void notifications.refetch()} />;
  }
  const items = notifications.data?.items ?? [];

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h2>通知</h2>
        {items.some(n => n.read_at === null) && <span className={styles.badge}>有未读</span>}
      </header>

      {items.length === 0 ? (
        <p className={styles.empty}>暂无通知</p>
      ) : (
        <ul className={styles.list}>
          {items.map(n => (
            <li key={n.id} className={styles.item}>
              <p className={styles.type}>
                {(
                  {
                    'training.created': '有新的训练任务',
                    'training.submitted': '学员已提交训练成果',
                    'training.feedback': '辅导员已给出反馈',
                    'training.cancelled': '训练任务已结束',
                    'support.requested': '学员发来了求助',
                    'support.accept': '辅导员已接到求助',
                    'support.resolve': '求助已解决',
                    'support.cancel': '求助已取消',
                    'support.message': '有新的沟通消息',
                    'support.annotation_published': '有新的图片标注',
                    'files.ready': '文件已通过检测',
                    'files.rejected': '文件未通过检测',
                  } as Record<string, string>
                )[n.type] ?? n.type}
              </p>
              <p className={styles.meta}>
                <span className={styles.resource}>{RESOURCE_TYPE_LABELS[n.resource_type]}</span>
                <span>{new Date(n.created_at).toLocaleString('zh-CN')}</span>
                {n.read_at !== null && <span className={styles.read}>已读</span>}
              </p>
              {n.read_at === null && (
                <button
                  type="button"
                  disabled={markRead.isPending}
                  onClick={() => markRead.mutate(n.id)}
                >
                  标为已读
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {markRead.isError && (
        <p role="alert" className={styles.error}>
          操作失败，请重试
        </p>
      )}
    </section>
  );
}
