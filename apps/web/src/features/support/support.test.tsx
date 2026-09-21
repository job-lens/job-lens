import type { ReactElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { AssistancePage, CounselorSupportPage } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderAt(routePath: string, entry: string, element: ReactElement) {
  const router = createMemoryRouter([{ path: routePath, element }], {
    initialEntries: [entry],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const queuedRequest = {
  id: 'req-1',
  case_id: 'case-1',
  task_id: null,
  step_id: null,
  message: '这步我不太会，能帮我看下吗？',
  attachment_ids: [],
  preferred_mode: 'text',
  counselor_id: 'c-1',
  state: 'queued',
  version: 1,
  created_at: '2026-09-20T08:00:00Z',
};

it('lists assistance requests with state and mode', async () => {
  server.use(
    http.get('*/api/v1/assistance-requests', () =>
      HttpResponse.json({ items: [queuedRequest], next_cursor: null, has_more: false }),
    ),
  );
  renderAt('/counselor/support', '/counselor/support', <CounselorSupportPage />);
  expect(await screen.findByRole('heading', { name: '求助工作台' })).toBeInTheDocument();
  expect(await screen.findByText('这步我不太会，能帮我看下吗？')).toBeInTheDocument();
  expect(screen.getByText('文字')).toBeInTheDocument();
});

it('shows request detail, thread and accept action', async () => {
  server.use(
    http.get('*/api/v1/assistance-requests/req-1', () => HttpResponse.json(queuedRequest)),
    http.get('*/api/v1/assistance-requests/req-1/messages', () =>
      HttpResponse.json({
        items: [
          {
            id: 'm-1',
            request_id: 'req-1',
            author_id: 'l-1',
            body: '请帮我看一下这一步',
            attachment_ids: [],
            created_at: '2026-09-20T08:05:00Z',
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    ),
  );
  renderAt('/counselor/support/:id', '/counselor/support/req-1', <AssistancePage />);
  expect(await screen.findByRole('heading', { name: '求助详情' })).toBeInTheDocument();
  expect(screen.getByText('请帮我看一下这一步')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '接单' })).toBeInTheDocument();
});
