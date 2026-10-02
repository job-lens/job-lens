import { useState, useSyncExternalStore } from 'react';
import styles from './Companions.module.css';
import { AgentAvatar } from './companions/AgentAvatar';
import type { AgentAvatarId } from './companions/avatars';

const motionKey = 'jl.companion-motion';
function savedMotion() {
  try {
    return localStorage.getItem(motionKey) !== 'off';
  } catch {
    return true;
  }
}
function reducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}
function subscribeMotion(change: () => void) {
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  media?.addEventListener('change', change);
  return () => media?.removeEventListener('change', change);
}

/** Reference avatar implementation, copied locally; no cross-repository runtime dependency. */
export function Companions({ privateEntry = false }: { privateEntry?: boolean }) {
  const [motion, setMotion] = useState(savedMotion);
  const reduced = useSyncExternalStore(subscribeMotion, reducedMotion, () => true);
  const active = motion && !reduced;
  function toggle() {
    setMotion(!motion);
    try {
      localStorage.setItem(motionKey, motion ? 'off' : 'on');
    } catch {
      /* Storage may be unavailable; the control still works. */
    }
  }
  return (
    <div className={styles.group} data-motion={active ? 'on' : 'off'} data-private={privateEntry}>
      <div className={styles.crowd} role="img" aria-label="五个相伴的小精灵">
        {(['cheng', 'nian', 'qi', 'shi', 'you'] as AgentAvatarId[]).map((avatar, i) => (
          <AgentAvatar
            key={avatar}
            avatar={avatar}
            size={i === 2 ? 64 : 52}
            offset={i * 1.35}
            state={privateEntry ? 'think' : 'idle'}
            playing={active}
          />
        ))}
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
