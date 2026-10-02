import { useSyncExternalStore } from 'react';

const key = 'jl.companion-motion';
const event = 'jl:companion-motion';
let fallback = true;
function saved() {
  try {
    return localStorage.getItem(key) !== 'off';
  } catch {
    return fallback;
  }
}
function reduced() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}
function subscribe(change: () => void) {
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  media?.addEventListener('change', change);
  window.addEventListener(event, change);
  window.addEventListener('storage', change);
  return () => {
    media?.removeEventListener('change', change);
    window.removeEventListener(event, change);
    window.removeEventListener('storage', change);
  };
}
export function useCompanionMotion() {
  const motion = useSyncExternalStore(subscribe, saved, () => false);
  const reduce = useSyncExternalStore(subscribe, reduced, () => true);
  return {
    active: motion && !reduce,
    reduced: reduce,
    toggle() {
      fallback = !saved();
      try {
        localStorage.setItem(key, fallback ? 'on' : 'off');
      } catch {
        // The shared in-memory preference also works without storage.
      }
      window.dispatchEvent(new Event(event));
    },
  };
}
