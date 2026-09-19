import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { LoginPage, SessionGate } from './public';
const server = setupServer();
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
