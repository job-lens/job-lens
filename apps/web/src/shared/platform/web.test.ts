import { expect, it, vi } from 'vitest';
import { webPlatform } from './web';
const preferences = { quiet_mode: true, speech_enabled: true, vibration_enabled: true, volume: 1 };
it('quiet mode never calls device APIs', () => {
  const vibrate = vi.fn();
  vi.stubGlobal('navigator', { vibrate });
  expect(webPlatform.vibrate(preferences).ok).toBe(true);
  expect(webPlatform.speak('提示', preferences).ok).toBe(true);
  expect(vibrate).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});
it('reports unsupported vibration without breaking training', () => {
  vi.stubGlobal('navigator', {});
  expect(webPlatform.vibrate({ ...preferences, quiet_mode: false })).toEqual({
    ok: false,
    reason: 'unsupported',
  });
  vi.unstubAllGlobals();
});
it('supports cancelling image selection', async () => {
  const abort = new AbortController();
  abort.abort();
  expect(await webPlatform.pickImage(false, abort.signal)).toEqual({
    ok: false,
    reason: 'cancelled',
  });
});
