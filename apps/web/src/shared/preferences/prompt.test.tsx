import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest';
import { PlatformContext, usePrompt } from '@/shared/platform/context';
import type { Platform } from '@/shared/platform/types';
import { PreferencesProvider } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const speak = vi.fn(() => ({ ok: true as const, value: undefined }));
const platform = {
  speak,
  vibrate: () => ({ ok: true as const, value: undefined }),
  pickImage: () => Promise.resolve({ ok: false as const, reason: 'unsupported' as const }),
  cancelSpeech: () => {},
} satisfies Platform;

function Speaker() {
  const prompt = usePrompt();
  return (
    <button type="button" onClick={() => prompt.speak('下一步')}>
      朗读
    </button>
  );
}

function renderSpeaker() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PlatformContext.Provider value={platform}>
        <PreferencesProvider>
          <Speaker />
        </PreferencesProvider>
      </PlatformContext.Provider>
    </QueryClientProvider>,
  );
}

it('hands the viewer settings to the platform without the caller assembling them', async () => {
  server.use(
    http.get('*/api/v1/me/preferences', () =>
      HttpResponse.json({
        font_scale: 1,
        volume: 0.4,
        quiet_mode: true,
        speech_enabled: true,
        vibration_enabled: true,
        version: 2,
      }),
    ),
  );
  renderSpeaker();
  (await screen.findByRole('button', { name: '朗读' })).click();
  expect(speak).toHaveBeenCalledWith('下一步', expect.objectContaining({ quiet_mode: true }));
});
