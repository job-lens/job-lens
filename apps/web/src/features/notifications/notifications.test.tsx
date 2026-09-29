import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { CounselorNotificationsPage } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CounselorNotificationsPage />
    </QueryClientProvider>,
  );
}

const unread = {
  id: 'n-1',
  seq: '1',
  type: '学员已提交训练成果',
  resource_type: 'submission',
  resource_id: 'sub-1',
  created_at: '2026-09-20T09:00:00Z',
  read_at: null,
};

it('lists notifications and marks one as read', async () => {
  let readCalled = false;
  server.use(
    http.get('*/api/v1/notifications', () =>
      HttpResponse.json({ items: [unread], next_seq: '1', has_more: false }),
    ),
    http.post('*/api/v1/notifications/n-1/read', () => {
      readCalled = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();

  expect(await screen.findByRole('heading', { name: '通知' })).toBeInTheDocument();
  expect(screen.getByText('学员已提交训练成果')).toBeInTheDocument();
  expect(screen.getByText('提交')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '标为已读' }));
  await waitFor(() => expect(readCalled).toBe(true));
});
