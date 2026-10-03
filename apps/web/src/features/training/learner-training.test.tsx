import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { PlatformContext } from '@/shared/platform/context';
import { webPlatform } from '@/shared/platform/web';
import type { components } from '@/shared/api/schema';
import { TrainingPage } from './public';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
const step = {
  id: 'step-1',
  position: 1,
  instruction: '核对文件名',
  media_ids: [],
  estimated_seconds: 60,
  evidence_required: false,
};
const initial: components['schemas']['Task'] = {
  id: 'task-1',
  case_id: 'case-1',
  learner_id: 'learner-1',
  title: '整理文件',
  revision: {
    id: 'revision-1',
    plan_id: 'plan-1',
    revision_no: 1,
    state: 'published',
    version: 3,
    published_at: '2026-10-03T00:00:00Z',
    goal: '按步骤整理文件',
    steps: [step],
    reminder: { speech_enabled: false, vibration_enabled: false, prompt_level: 2 },
  },
  status: 'not_started',
  current_step_id: 'step-1',
  progress: [{ step_id: 'step-1', status: 'pending', attachment_ids: [] }],
  due_on: null,
  prompt_override: null,
  version: 1,
};
function show() {
  const router = createMemoryRouter([{ path: '/learner/tasks/:id', element: <TrainingPage /> }], {
    initialEntries: ['/learner/tasks/task-1'],
  });
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      <PlatformContext.Provider value={webPlatform}>
        <RouterProvider router={router} />
      </PlatformContext.Provider>
    </QueryClientProvider>,
  );
}
it('starts, saves a step with its latest version and submits through actual command boundaries', async () => {
  let task = initial;
  const versions: string[] = [];
  server.use(
    http.get('*/api/v1/tasks/task-1', () => HttpResponse.json(task)),
    http.get('*/api/v1/tasks/task-1/submissions', () =>
      HttpResponse.json({ items: [], next_cursor: null, has_more: false }),
    ),
    http.post('*/api/v1/tasks/task-1/actions', ({ request }) => {
      versions.push(request.headers.get('If-Match')!);
      task = { ...task, status: 'in_progress', version: 2 };
      return HttpResponse.json(task);
    }),
    http.put('*/api/v1/tasks/task-1/steps/step-1', ({ request }) => {
      versions.push(request.headers.get('If-Match')!);
      task = {
        ...task,
        current_step_id: null,
        progress: [{ ...task.progress[0], status: 'completed' }],
        version: 3,
      };
      return HttpResponse.json(task);
    }),
    http.post('*/api/v1/tasks/task-1/submissions', ({ request }) => {
      versions.push(request.headers.get('If-Match')!);
      task = { ...task, status: 'submitted', version: 4 };
      const submission: components['schemas']['Submission'] = {
        id: 'submission-1',
        task_id: task.id,
        revision_id: task.revision.id,
        attempt_no: 1,
        note: '',
        submitted_at: '2026-10-03T00:00:00Z',
        task_version: task.version,
        task_status: task.status,
        snapshot: { schema_version: 1, revision_id: task.revision.id, progress: task.progress },
        feedback: null,
      };
      return HttpResponse.json(submission, { status: 201 });
    }),
  );
  show();
  fireEvent.click(await screen.findByRole('button', { name: '开始训练' }));
  fireEvent.click(await screen.findByRole('button', { name: '这一步完成了' }));
  fireEvent.click(await screen.findByRole('button', { name: '提交结果' }));
  expect(await screen.findByRole('heading', { name: '结果已提交。' })).toBeInTheDocument();
  expect(versions).toEqual(['"1"', '"2"', '"3"']);
});
it('keeps a failed completion editable and never submits after a version conflict', async () => {
  let submitted = false;
  server.use(
    http.get('*/api/v1/tasks/task-1', () =>
      HttpResponse.json({ ...initial, status: 'in_progress', version: 2 }),
    ),
    http.get('*/api/v1/tasks/task-1/submissions', () =>
      HttpResponse.json({ items: [], next_cursor: null, has_more: false }),
    ),
    http.put('*/api/v1/tasks/task-1/steps/step-1', () =>
      HttpResponse.json(
        { status: 412, code: 'VERSION_CONFLICT', title: '内容已更新', trace_id: 'trace-1' },
        { status: 412 },
      ),
    ),
    http.post('*/api/v1/tasks/task-1/submissions', () => {
      submitted = true;
      return HttpResponse.json({});
    }),
  );
  show();
  fireEvent.click(await screen.findByRole('button', { name: '这一步完成了' }));
  expect(await screen.findByText('进度已更新，请重新读取后继续。')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '提交结果' })).not.toBeInTheDocument();
  expect(submitted).toBe(false);
});
