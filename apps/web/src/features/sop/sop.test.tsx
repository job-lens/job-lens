import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { SopPage } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const router = createMemoryRouter([{ path: '/counselor/sop/:id', element: <SopPage /> }], {
    initialEntries: ['/counselor/sop/case-1'],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const draftRevision = {
  goal: '掌握收银流程',
  steps: [
    {
      id: '33333333-3333-3333-3333-333333333333',
      position: 1,
      instruction: '认识收银机',
      media_ids: [],
      estimated_seconds: 720,
      evidence_required: false,
    },
  ],
  reminder: { speech_enabled: true, vibration_enabled: false, prompt_level: 2 },
  id: 'draft-1',
  plan_id: 'plan-1',
  revision_no: 1,
  state: 'draft',
  version: 1,
  published_at: null,
};

it('shows the create form when the case has no plan yet', async () => {
  server.use(
    http.get('*/api/v1/cases/case-1/sop-plans', () =>
      HttpResponse.json({ items: [], next_cursor: null, has_more: false }),
    ),
  );
  renderPage();
  expect(await screen.findByLabelText('计划标题')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '创建计划' })).toBeDisabled();
});

it('opens the draft editor when the plan has a draft', async () => {
  server.use(
    http.get('*/api/v1/cases/case-1/sop-plans', () =>
      HttpResponse.json({
        items: [
          {
            id: 'plan-1',
            case_id: 'case-1',
            title: '咖啡店收银岗位训练',
            published_revision_id: null,
            draft_revision_id: 'draft-1',
            version: 1,
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    ),
    http.get('*/api/v1/sop-revisions/draft-1', () => HttpResponse.json(draftRevision)),
  );
  renderPage();
  expect(await screen.findByLabelText('总目标')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '添加步骤' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '保存草稿' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '发布 SOP' })).toBeInTheDocument();
});

it('offers to start a new draft when only a published revision exists', async () => {
  server.use(
    http.get('*/api/v1/cases/case-1/sop-plans', () =>
      HttpResponse.json({
        items: [
          {
            id: 'plan-1',
            case_id: 'case-1',
            title: '咖啡店收银岗位训练',
            published_revision_id: 'pub-1',
            draft_revision_id: null,
            version: 2,
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    ),
    http.get('*/api/v1/sop-revisions/pub-1', () =>
      HttpResponse.json({
        ...draftRevision,
        id: 'pub-1',
        state: 'published',
        published_at: '2026-09-19T10:00:00Z',
      }),
    ),
  );
  renderPage();
  expect(await screen.findByRole('button', { name: '基于此版新建草稿' })).toBeInTheDocument();
  expect(screen.getByText(/已发布 · 第 1 版/)).toBeInTheDocument();
});
