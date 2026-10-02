import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { ProfilePage, PreferencesPage } from './public';
const profile = {
  user_id: '2a7549a0-451d-4bb3-9eb7-21baedb1a894',
  display_name: '学员',
  sensory_preferences: ['避免大音量'],
  communication_preference: '文字',
  work_notes: '',
  version: 1,
};
const preferences = {
  font_scale: 1,
  volume: 0.5,
  quiet_mode: true,
  speech_enabled: false,
  vibration_enabled: false,
  version: 1,
};
const server = setupServer(
  http.get('*/api/v1/me/profile', () => HttpResponse.json(profile)),
  http.get('*/api/v1/me/preferences', () => HttpResponse.json(preferences)),
);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
  return client;
}
it('saves personal profile through the real contract and updates the confirmed cache only', async () => {
  server.use(
    http.put('*/api/v1/me/profile', async ({ request }) => {
      expect(request.headers.get('If-Match')).toBe('"1"');
      const body = await request.json();
      expect(body).toEqual({
        display_name: '新的称呼',
        sensory_preferences: ['避免大音量'],
        communication_preference: '文字',
        work_notes: '',
      });
      return HttpResponse.json({ ...profile, ...(body as object), version: 2 });
    }),
  );
  const client = mount(<ProfilePage />);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('怎么称呼你');
  await user.clear(name);
  await user.type(name, '新的称呼');
  await user.click(screen.getByRole('button', { name: '保存资料' }));
  expect(await screen.findByRole('status')).toHaveTextContent('资料已保存');
  expect(client.getQueryData(['profile'])).toMatchObject({ version: 2, display_name: '新的称呼' });
});
it('preserves edits on version conflict and only discards them after explicit successful reload', async () => {
  server.use(
    http.put('*/api/v1/me/profile', () =>
      HttpResponse.json({ code: 'VERSION_CONFLICT', title: '内容已变化' }, { status: 412 }),
    ),
  );
  mount(<ProfilePage />);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('怎么称呼你');
  await user.clear(name);
  await user.type(name, '尚未保存');
  await user.click(screen.getByRole('button', { name: '保存资料' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('你的修改仍在这里');
  expect(name).toHaveValue('尚未保存');
  server.use(
    http.get('*/api/v1/me/profile', () =>
      HttpResponse.json({ ...profile, display_name: '服务端最新', version: 2 }),
    ),
  );
  await user.click(screen.getByRole('button', { name: '重新读取最新资料' }));
  expect(await screen.findByDisplayValue('服务端最新')).toBeVisible();
});
it('never discards profile edits when refreshing fails', async () => {
  server.use(
    http.put('*/api/v1/me/profile', () =>
      HttpResponse.json({ code: 'VERSION_CONFLICT', title: '内容已变化' }, { status: 412 }),
    ),
  );
  mount(<ProfilePage />);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('怎么称呼你');
  await user.clear(name);
  await user.type(name, '我的修改');
  await user.click(screen.getByRole('button', { name: '保存资料' }));
  await screen.findByRole('alert');
  server.use(
    http.get('*/api/v1/me/profile', () =>
      HttpResponse.json({ code: 'UNAVAILABLE' }, { status: 503 }),
    ),
  );
  await user.click(screen.getByRole('button', { name: '重新读取最新资料' }));
  expect(await screen.findByRole('status')).toHaveTextContent('重新读取失败');
  expect(name).toHaveValue('我的修改');
});
it('persists quiet preferences with the current resource version', async () => {
  server.use(
    http.put('*/api/v1/me/preferences', async ({ request }) => {
      expect(request.headers.get('If-Match')).toBe('"1"');
      const body = await request.json();
      expect(body).toMatchObject({ quiet_mode: true, font_scale: 1.25 });
      return HttpResponse.json({ ...preferences, ...(body as object), version: 2 });
    }),
  );
  const client = mount(<PreferencesPage />);
  const user = userEvent.setup();
  await user.selectOptions(await screen.findByLabelText('文字大小'), '1.25');
  await user.click(screen.getByRole('button', { name: '保存设置' }));
  expect(await screen.findByRole('status')).toHaveTextContent('设置已保存');
  expect(client.getQueryData(['preferences'])).toMatchObject({
    font_scale: 1.25,
    quiet_mode: true,
    version: 2,
  });
});
