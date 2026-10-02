import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, beforeAll, expect, it } from 'vitest';
import { SettingsPage } from './SettingsPage';
const server = setupServer(
  http.get('*/api/v1/me/profile', () =>
    HttpResponse.json({
      user_id: 'user',
      display_name: '原称呼',
      sensory_preferences: [],
      communication_preference: '',
      work_notes: '',
      version: 1,
    }),
  ),
  http.get('*/api/v1/me/preferences', () =>
    HttpResponse.json({
      font_scale: 1,
      volume: 0.5,
      quiet_mode: true,
      speech_enabled: false,
      vibration_enabled: false,
      version: 1,
    }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
function mount() {
  const router = createMemoryRouter([{ path: '/settings', element: <SettingsPage /> }], {
    initialEntries: ['/settings?tab=profile'],
  });
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}
it('keeps unsaved profile edits when switching sections and using browser history', async () => {
  const router = mount();
  const user = userEvent.setup();
  const name = await screen.findByLabelText('怎么称呼你');
  await user.clear(name);
  await user.type(name, '未保存的称呼');
  await user.click(screen.getByRole('button', { name: /阅读与提醒/ }));
  expect(await screen.findByLabelText('文字大小')).toBeVisible();
  expect(router.state.location.search).toBe('?tab=preferences');
  await act(() => router.navigate(-1));
  await waitFor(() => expect(screen.getByLabelText('怎么称呼你')).toBeVisible());
  expect(screen.getByLabelText('怎么称呼你')).toHaveValue('未保存的称呼');
});
it('offers the real password reset route with the session consequences visible', async () => {
  mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /账户与安全/ }));
  expect(screen.getByRole('link', { name: '通过邮箱重设' })).toHaveAttribute(
    'href',
    '/forgot-password',
  );
  expect(screen.getByText(/所有旧登录会话都会退出/)).toBeVisible();
});
