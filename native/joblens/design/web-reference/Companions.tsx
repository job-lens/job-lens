import { Buddy } from './Buddy';
import { useCompanionMotion } from './companionMotion';
import styles from './Companions.module.css';

export function Companions({ privateEntry = false }: { privateEntry?: boolean }) {
  const { active, reduced, toggle } = useCompanionMotion();
  return (
    <div className={styles.group} data-motion={active ? 'on' : 'off'} data-private={privateEntry}>
      {/* 圆形头像框：人物下半截被框裁掉，头发、耳机和小芽从框顶冒出来 */}
      <div className={styles.frame} role="img" aria-label="陪你做事的小伙伴">
        <div className={styles.stage}>
          <Buddy size={156} playing={active} closed={privateEntry} />
        </div>
      </div>
      <button
        type="button"
        className={`${styles.control} qx-btn qx-btn--ghost qx-btn--icon`}
        aria-label={reduced ? '已按系统设置关闭动效' : active ? '暂停伙伴动效' : '开启伙伴动效'}
        title={reduced ? '已按系统设置关闭动效' : active ? '暂停伙伴动效' : '开启伙伴动效'}
        disabled={reduced}
        onClick={toggle}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          {active ? (
            <path
              d="M5 4v8m6-8v8"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          ) : (
            <path
              d="m6 4 6 4-6 4Z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </button>
    </div>
  );
}
