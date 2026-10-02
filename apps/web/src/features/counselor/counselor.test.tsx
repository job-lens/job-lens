import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { CounselorPage } from './public';
import { RecordsView } from './RecordsView';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const casesPayload = {
  items: [
    {
      id: '11111111-1111-1111-1111-111111111111',
      learner_id: 'l-1',
      counselor_id: null,
      lifecycle: 'pending_match',
      display_status: 'pending_match',
      current_task_id: null,
      version: 1,
    },
    {
      id: '22222222-2222-2222-2222-222222222222',
      learner_id: 'l-2',
      counselor_id: 'c-1',
      lifecycle: 'active',
      display_status: 'training',
      current_task_id: 't-1',
      version: 1,
    },
  ],
  next_cursor: null,
  has_more: false,
};

function renderPage(path = '/counselor') {
  const router = createMemoryRouter([{ path: '/counselor', element: <CounselorPage /> }], {
    initialEntries: [path],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function mockEndpoints() {
  server.use(
    http.get('*/api/v1/cases', () => HttpResponse.json(casesPayload)),
    http.get('*/api/v1/dashboard', () =>
      HttpResponse.json({
        view: 'counselor',
        pending_tasks: 3,
        pending_feedback: 1,
        pending_assistance: 0,
        as_of: '2026-09-20T00:00:00Z',
      }),
    ),
  );
}

it('shows pending support count on the home tab', async () => {
  mockEndpoints();
  renderPage();
  expect(await screen.findByRole('region', { name: '待办概览' })).toBeVisible();
  expect(
    within(screen.getByRole('region', { name: '待办概览' })).getByText('3'),
  ).toBeInTheDocument();
  expect(screen.getByText(/项待完成/)).toBeInTheDocument();
});

it('filters cases by display status on the cases tab', async () => {
  mockEndpoints();
  renderPage('/counselor?tab=cases');

  // 列表加载后，两个个案卡片都在
  expect(await screen.findByRole('link', { name: /个案 #11111111/ })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /个案 #22222222/ })).toBeInTheDocument();

  // 点击「训练中」筛选后，只剩训练中的个案
  await userEvent.click(screen.getByRole('button', { name: '训练中' }));
  expect(screen.getByRole('link', { name: /个案 #22222222/ })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /个案 #11111111/ })).not.toBeInTheDocument();
});

function renderRecords() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RecordsView caseId="case-1" />
    </QueryClientProvider>,
  );
}

it('shows descriptive training records in the ability report', async () => {
  server.use(
    http.get('*/api/v1/cases/case-1/records', () =>
      HttpResponse.json({
        items: [
          {
            task_id: 'task-1',
            title: '收银流程训练',
            status: 'completed',
            attempts: 3,
            hint_requests: 2,
            assistance_requests: 1,
            observed_elapsed_ms: 150000,
            measurement_note: '完成度良好',
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    ),
  );
  renderRecords();
  expect(await screen.findByRole('heading', { name: '能力报告' })).toBeInTheDocument();
  expect(screen.getByText('收银流程训练')).toBeInTheDocument();
  expect(screen.getByText('已完成')).toBeInTheDocument();
  expect(screen.getByText(/尝试 3 次/)).toBeInTheDocument();
  expect(screen.getByText('完成度良好')).toBeInTheDocument();
});

it('loads the next authorized page and filters all loaded cases without losing earlier results', async () => {
  let nextRequests = 0;
  server.use(
    http.get('*/api/v1/cases', ({ request }) => {
      const cursor = new URL(request.url).searchParams.get('cursor');
      if (cursor) {
        nextRequests += 1;
        expect(cursor).toBe('page-two');
        return HttpResponse.json({ ...casesPayload, items: [casesPayload.items[1]] });
      }
      return HttpResponse.json({
        items: [casesPayload.items[0]],
        has_more: true,
        next_cursor: 'page-two',
      });
    }),
  );
  renderPage('/counselor?tab=cases');
  expect(await screen.findByRole('link', { name: /个案 #11111111/ })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '训练中' }));
  expect(screen.getByText('没有符合条件的个案')).toBeVisible();
  expect(screen.getByText(/可以继续加载下一页/)).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '加载更多个案' }));
  expect(await screen.findByRole('link', { name: /个案 #22222222/ })).toBeVisible();
  expect(nextRequests).toBe(1);
  expect(screen.getByText('已加载 2 个个案')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '全部' }));
  expect(screen.getByRole('link', { name: /个案 #11111111/ })).toBeVisible();
});
it('preserves loaded cases and offers retry after a next-page error', async () => {
  let fail = true;
  server.use(
    http.get('*/api/v1/cases', ({ request }) => {
      if (new URL(request.url).searchParams.has('cursor'))
        return fail
          ? HttpResponse.json({ title: '服务暂不可用' }, { status: 503 })
          : HttpResponse.json({ ...casesPayload, items: [casesPayload.items[1]] });
      return HttpResponse.json({
        items: [casesPayload.items[0]],
        has_more: true,
        next_cursor: 'next',
      });
    }),
  );
  renderPage('/counselor?tab=cases');
  await userEvent.click(await screen.findByRole('button', { name: '加载更多个案' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('下一页未能加载');
  expect(screen.getByRole('link', { name: /个案 #11111111/ })).toBeVisible();
  fail = false;
  await userEvent.click(screen.getByRole('button', { name: '重试' }));
  expect(await screen.findByRole('link', { name: /个案 #22222222/ })).toBeVisible();
});
