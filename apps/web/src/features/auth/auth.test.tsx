import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { LoginPage, SessionControls, SessionGate } from './public';
const server = setupServer(
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
  http.get('*/api/v1/auth/csrf', () =>
    HttpResponse.json({ csrf_token: 'initial-csrf-token-1234' }),
  ),
);
configure({ asyncUtilTimeout: 5000 });
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function renderGate() {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      {
        element: <SessionGate role="counselor" />,
        children: [{ path: '/protected', element: <h1>受保护内容</h1> }],
      },
    ],
    { initialEntries: ['/protected'] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
it('does not expose counselor content to learners', async () => {
  server.use(
    http.get('*/api/v1/me', () =>
      HttpResponse.json({ id: 'x', display_name: '测试', roles: ['learner'] }),
    ),
  );
  renderGate();
  expect(await screen.findByRole('alert')).toHaveTextContent('无权访问');
  expect(screen.queryByText('受保护内容')).not.toBeInTheDocument();
});
it('redirects expired sessions to login', async () => {
  server.use(
    http.get('*/api/v1/me', () =>
      HttpResponse.json({ code: 'SESSION_EXPIRED', title: '会话失效' }, { status: 401 }),
    ),
  );
  renderGate();
  expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument();
});

it('renders content only for a confirmed matching role', async () => {
  server.use(
    http.get('*/api/v1/me', () =>
      HttpResponse.json({ id: 'x', display_name: '测试', roles: ['counselor'] }),
    ),
  );
  renderGate();
  expect(await screen.findByRole('heading', { name: '受保护内容' })).toBeVisible();
});
it('keeps protected content hidden when identity is unavailable', async () => {
  server.use(
    http.get('*/api/v1/me', () => HttpResponse.json({ code: 'UNAVAILABLE' }, { status: 503 })),
  );
  renderGate();
  expect(await screen.findByRole('alert')).toHaveTextContent('身份服务暂不可用');
  expect(screen.queryByText('受保护内容')).not.toBeInTheDocument();
});

it('logs in through csrf and password APIs and returns to the interrupted page', async () => {
  const { default: userEvent } = await import('@testing-library/user-event');
  const user = userEvent.setup();
  server.use(
    http.get('*/api/v1/auth/csrf', () =>
      HttpResponse.json({ csrf_token: 'initial-csrf-token-1234' }),
    ),
    http.post('*/api/v1/auth/login', async ({ request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('initial-csrf-token-1234');
      expect(await request.json()).toEqual({
        login_name: 'learner',
        password: 'training-password',
      });
      return HttpResponse.json({
        user: { id: 'x', display_name: '测试', roles: ['learner'] },
        csrf_token: 'rotated-csrf-token-1234',
      });
    }),
  );
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/learner/tasks/example', element: <h1>继续原任务</h1> },
    ],
    { initialEntries: [{ pathname: '/login', state: { returnTo: '/learner/tasks/example' } }] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await user.type(screen.getByLabelText('账号'), 'learner');
  await user.type(screen.getByLabelText('密码'), 'training-password');
  await user.click(screen.getByRole('button', { name: '登录' }));
  expect(await screen.findByRole('heading', { name: '继续原任务' })).toBeVisible();
});

it('keeps a failed login on the form without exposing protected content', async () => {
  const { default: userEvent } = await import('@testing-library/user-event');
  const user = userEvent.setup();
  server.use(
    http.post('*/api/v1/auth/login', () =>
      HttpResponse.json(
        { code: 'INVALID_CREDENTIALS', title: '账号或密码不正确' },
        { status: 401 },
      ),
    ),
  );
  const client = new QueryClient();
  const router = createMemoryRouter([{ path: '/login', element: <LoginPage /> }], {
    initialEntries: ['/login'],
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await user.type(screen.getByLabelText('账号'), 'learner');
  await user.type(screen.getByLabelText('密码'), 'wrong');
  await user.click(screen.getByRole('button', { name: '登录' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('账号或密码不正确');
  expect(router.state.location.pathname).toBe('/login');
  expect(client.getQueryData(['session'])).toBeUndefined();
});

it('revokes the session before clearing private cached data on logout', async () => {
  const { default: userEvent } = await import('@testing-library/user-event');
  const user = userEvent.setup();
  let revoked = false;
  server.use(
    http.post('*/api/v1/auth/logout', ({ request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('initial-csrf-token-1234');
      revoked = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const client = new QueryClient();
  client.setQueryData(['session'], { id: 'learner', roles: ['learner'] });
  client.setQueryData(['private-task'], { answer: 'private data' });
  const router = createMemoryRouter(
    [
      { path: '/protected', element: <SessionControls /> },
      { path: '/login', element: <LoginPage /> },
    ],
    { initialEntries: ['/protected'] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await user.click(screen.getByRole('button', { name: '退出登录' }));
  expect(await screen.findByRole('heading', { name: '登录' })).toBeVisible();
  expect(revoked).toBe(true);
  expect(client.getQueryData(['private-task'])).toBeUndefined();
  expect(client.getQueryData(['session'])).toBeUndefined();
});
