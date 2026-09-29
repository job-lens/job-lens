import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { PreferencesProvider, usePreferences } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  document.documentElement.style.removeProperty('--font-scale');
});
afterAll(() => server.close());

function Probe() {
  const preferences = usePreferences();
  return (
    <p data-testid="probe">
      {preferences.font_scale} {String(preferences.quiet_mode)}
    </p>
  );
}

function renderProbe() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PreferencesProvider>
        <Probe />
      </PreferencesProvider>
    </QueryClientProvider>,
  );
}

const SAVED = {
  font_scale: 1.5,
  volume: 0.4,
  quiet_mode: false,
  speech_enabled: true,
  vibration_enabled: true,
  version: 3,
};

it('applies the saved font scale to the document', async () => {
  server.use(http.get('*/api/v1/me/preferences', () => HttpResponse.json(SAVED)));
  renderProbe();
  // The provider paints the quiet defaults first, then swaps in what was saved.
  expect(await screen.findByText('1.5 false')).toBeVisible();
  expect(document.documentElement.style.getPropertyValue('--font-scale')).toBe('1.5');
});

it('falls back to the quiet defaults when preferences cannot be read', async () => {
  server.use(
    http.get('*/api/v1/me/preferences', () =>
      HttpResponse.json({ code: 'UNAUTHENTICATED' }, { status: 401 }),
    ),
  );
  renderProbe();
  // A visitor without a session must still get a usable, low-stimulus interface.
  expect(await screen.findByText('1 true')).toBeVisible();
  expect(document.documentElement.style.getPropertyValue('--font-scale')).toBe('1');
});
