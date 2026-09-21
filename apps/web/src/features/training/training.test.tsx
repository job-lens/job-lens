import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { AnnotationEditor } from './AnnotationEditor';
import { FeedbackPage, CounselorTaskPage } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const router = createMemoryRouter(
    [{ path: '/counselor/submissions/:id', element: <FeedbackPage /> }],
    { initialEntries: ['/counselor/submissions/sub-1'] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const submission = {
  id: 'sub-1',
  task_id: 'task-1',
  attempt_no: 1,
  revision_id: 'rev-1',
  note: '已完成',
  snapshot: {
    schema_version: 1,
    revision_id: 'rev-1',
    progress: [
      { step_id: 'step-1', status: 'completed', attachment_ids: [] },
      { step_id: 'step-2', status: 'in_progress', attachment_ids: [] },
    ],
  },
  submitted_at: '2026-09-20T08:00:00Z',
  task_version: 3,
  task_status: 'submitted',
  feedback: null,
};

const revision = {
  goal: '掌握收银流程',
  steps: [
    {
      id: 'step-1',
      position: 1,
      instruction: '认识收银机',
      media_ids: [],
      estimated_seconds: 720,
      evidence_required: true,
    },
    {
      id: 'step-2',
      position: 2,
      instruction: '完成一次收款',
      media_ids: [],
      estimated_seconds: 900,
      evidence_required: true,
    },
  ],
  reminder: { speech_enabled: true, vibration_enabled: false, prompt_level: 2 },
  id: 'rev-1',
  plan_id: 'plan-1',
  revision_no: 2,
  state: 'published',
  version: 2,
  published_at: '2026-09-19T10:00:00Z',
};

it('shows the review form for an unreviewed submission', async () => {
  server.use(
    http.get('*/api/v1/submissions/sub-1', () => HttpResponse.json(submission)),
    http.get('*/api/v1/sop-revisions/rev-1', () => HttpResponse.json(revision)),
  );
  renderPage();
  expect(await screen.findByRole('heading', { name: '审核结论' })).toBeInTheDocument();
  expect(await screen.findByText('认识收银机')).toBeInTheDocument();
  // 反馈说明为空时不可提交。
  expect(screen.getByRole('button', { name: '提交审核' })).toBeDisabled();
});

it('shows the read-only result when feedback already exists', async () => {
  server.use(
    http.get('*/api/v1/submissions/sub-1', () =>
      HttpResponse.json({
        ...submission,
        feedback: {
          outcome: 'passed',
          message: '做得不错',
          tags: ['title_correct'],
          redo_step_ids: [],
          annotation_ids: [],
          id: 'fb-1',
          submission_id: 'sub-1',
          author_id: 'c-1',
          created_at: '2026-09-20T09:00:00Z',
        },
      }),
    ),
  );
  renderPage();
  expect(await screen.findByRole('heading', { name: '审核结论（已提交）' })).toBeInTheDocument();
  expect(screen.getByText('做得不错')).toBeInTheDocument();
});

const task = {
  id: 'task-1',
  case_id: 'case-1',
  learner_id: 'l-1',
  title: '收银流程训练',
  revision: {
    goal: '掌握收银流程',
    steps: [
      {
        id: 'step-1',
        position: 1,
        instruction: '认识收银机',
        media_ids: [],
        estimated_seconds: 720,
        evidence_required: true,
      },
      {
        id: 'step-2',
        position: 2,
        instruction: '完成一次收款',
        media_ids: [],
        estimated_seconds: 900,
        evidence_required: true,
      },
    ],
    reminder: { speech_enabled: true, vibration_enabled: false, prompt_level: 2 },
    id: 'rev-1',
    plan_id: 'plan-1',
    revision_no: 2,
    state: 'published',
    version: 2,
    published_at: '2026-09-19T10:00:00Z',
  },
  status: 'in_progress',
  due_on: '2026-09-25',
  current_step_id: 'step-2',
  progress: [
    { step_id: 'step-1', status: 'completed', attachment_ids: [] },
    { step_id: 'step-2', status: 'in_progress', attachment_ids: [] },
  ],
  prompt_override: null,
  version: 5,
};

function renderTask() {
  const router = createMemoryRouter(
    [{ path: '/counselor/tasks/:id', element: <CounselorTaskPage /> }],
    { initialEntries: ['/counselor/tasks/task-1'] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

it('shows task progress and prompt-override control', async () => {
  server.use(http.get('*/api/v1/tasks/task-1', () => HttpResponse.json(task)));
  renderTask();
  expect(await screen.findByRole('heading', { name: '任务详情' })).toBeInTheDocument();
  expect(screen.getByText('认识收银机')).toBeInTheDocument();
  expect(screen.getByText('完成一次收款')).toBeInTheDocument();
  // 说明为空时不可保存提示等级。
  expect(screen.getByRole('button', { name: '保存提示等级' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '取消任务' })).toBeInTheDocument();
});

it('creates a guidance annotation from placed markers', async () => {
  let posted: unknown;
  server.use(
    http.post('*/api/v1/tasks/task-1/annotations', async ({ request }) => {
      posted = await request.json();
      return HttpResponse.json(
        {
          id: 'ann-1',
          task_id: 'task-1',
          submission_id: 'sub-1',
          asset_id: 'a-1',
          author_id: 'c-1',
          kind: 'guidance',
          markers: [],
          state: 'draft',
          version: 1,
        },
        { status: 201 },
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnnotationEditor taskId="task-1" submissionId="sub-1" assetId="a-1" />
    </QueryClientProvider>,
  );

  const surface = screen.getByRole('img', { name: '证据图片标注区' });
  surface.getBoundingClientRect = () => ({
    top: 0,
    left: 0,
    right: 200,
    bottom: 100,
    width: 200,
    height: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
  fireEvent.click(surface, { clientX: 50, clientY: 25 });

  fireEvent.change(screen.getByLabelText('标注 1 说明'), {
    target: { value: '这里要注意安全' },
  });
  fireEvent.click(screen.getByRole('button', { name: '保存指引标注' }));

  await waitFor(() => expect(posted).toBeDefined());
  expect(posted).toMatchObject({
    asset_id: 'a-1',
    submission_id: 'sub-1',
    kind: 'guidance',
  });
  const markers = (posted as { markers: { x: number; y: number; text: string; shape: string }[] })
    .markers;
  expect(markers).toHaveLength(1);
  expect(markers[0]).toMatchObject({ x: 0.25, y: 0.25, text: '这里要注意安全', shape: 'point' });
});
