import { useState, useSyncExternalStore } from 'react';
import styles from './Companions.module.css';
import type { CSSProperties } from 'react';

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

// Original Job Lens pebble spirits. Reference character artwork is not used.
const bodies = [
  'M15 67C7 52 14 24 31 17C47 10 74 17 82 35C90 54 82 78 63 83C43 89 24 83 15 67Z',
  'M12 62C9 46 23 16 41 12C62 8 83 33 85 53C88 73 72 87 52 87C32 87 16 80 12 62Z',
  'M13 52C14 33 33 17 52 17C72 17 88 39 84 60C80 79 62 88 43 84C24 81 12 71 13 52Z',
];
export function Spirit({ variant = 0 }: { variant?: number }) {
  return (
    <svg
      className={styles.spirit}
      data-variant={variant}
      viewBox="0 0 100 100"
      aria-hidden="true"
      style={{ '--spirit-delay': `${variant * -1.7}s` } as CSSProperties}
    >
      <g className={styles.body}>
        <path d={bodies[variant % bodies.length]} className={styles.fill} />
        <g className={styles.face}>
          <g className={styles.eyes}>
            <path d="M37 47v5M59 47v5" />
          </g>
          <path className={styles.smile} d="M44 62q5 4 10 0" />
        </g>
      </g>
    </svg>
  );
}

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
      <div className={styles.crowd} role="img" aria-label="三个相伴的小精灵">
        {[0, 1, 2].map(variant => (
          <Spirit key={variant} variant={variant} />
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
