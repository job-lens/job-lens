import type { Platform, PlatformResult } from './types';

export const webPlatform: Platform = {
  pickImage(camera, signal) {
    if (typeof document === 'undefined') return Promise.resolve({ ok: false, reason: 'unsupported' });
    if (signal?.aborted) return Promise.resolve({ ok: false, reason: 'cancelled' });
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/jpeg,image/png,image/webp'; input.hidden = true;
      if (camera) input.setAttribute('capture', 'environment');
      let settled = false;
      const finish = (result: PlatformResult<File>) => {
        if (settled) return;
        settled = true; clearTimeout(timer); signal?.removeEventListener('abort', abort);
        input.remove(); resolve(result);
      };
      const abort = () => finish({ ok: false, reason: 'cancelled' });
      const timer = setTimeout(abort, 120_000);
      input.addEventListener('cancel', abort, { once: true });
      signal?.addEventListener('abort', abort, { once: true });
      input.addEventListener('change', () => {
        const file = input.files?.[0];
        finish(file ? { ok: true, value: file } : { ok: false, reason: 'cancelled' });
      }, { once: true });
      document.body.append(input);
      try { input.click(); } catch { finish({ ok: false, reason: 'failed' }); }
    });
  },
  speak(text, preferences) {
    if (preferences.quiet_mode || !preferences.speech_enabled || preferences.volume <= 0) return { ok: true, value: undefined };
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) return { ok: false, reason: 'unsupported' };
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.volume = Math.min(1, Math.max(0, preferences.volume));
      window.speechSynthesis.speak(utterance);
      return { ok: true, value: undefined };
    } catch { return { ok: false, reason: 'failed' }; }
  },
  vibrate(preferences) {
    if (preferences.quiet_mode || !preferences.vibration_enabled) return { ok: true, value: undefined };
    if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return { ok: false, reason: 'unsupported' };
    try { return navigator.vibrate(100) ? { ok: true, value: undefined } : { ok: false, reason: 'failed' }; }
    catch { return { ok: false, reason: 'failed' }; }
  },
  cancelSpeech() { if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel(); },
};
