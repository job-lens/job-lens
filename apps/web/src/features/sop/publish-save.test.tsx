import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { DraftForm } from './DraftForm';
import type { components } from '@/shared/api/schema';
const initial: components['schemas']['SopRevision'] = {
  id: '11111111-1111-4111-8111-111111111111',
  plan_id: '22222222-2222-4222-8222-222222222222',
  revision_no: 1,
  state: 'draft',
  version: 1,
  published_at: null,
  goal: '整理文件',
  steps: [
    {
      id: '33333333-3333-4333-8333-333333333333',
      position: 1,
      instruction: '核对名称',
      media_ids: [],
      estimated_seconds: 60,
      evidence_required: false,
    },
  ],
  reminder: { speech_enabled: false, vibration_enabled: false, prompt_level: 1 },
};
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DraftForm revision={initial} caseId="case" />
    </QueryClientProvider>,
  );
}
it('saves edited steps before publishing the returned version', async () => {
  const calls: string[] = [];
  server.use(
    http.put('*/api/v1/sop-revisions/:id', async ({ request }) => {
      calls.push('save');
      expect(request.headers.get('If-Match')).toBe('"1"');
      const body = (await request.json()) as components['schemas']['RevisionWrite'];
      expect(body.steps[0].instruction).toBe('核对名称与日期');
      return HttpResponse.json({ ...initial, ...body, version: 2 });
    }),
    http.post('*/api/v1/sop-revisions/:id/publish', ({ request }) => {
      calls.push('publish');
      expect(request.headers.get('If-Match')).toBe('"2"');
      return HttpResponse.json({
        revision_id: initial.id,
        task_id: 'task',
        published_at: new Date().toISOString(),
      });
    }),
  );
  mount();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('步骤说明'), '与日期');
  await user.click(screen.getByRole('button', { name: '发布 SOP' }));
  await screen.findByText('SOP 已发布。');
  expect(calls).toEqual(['save', 'publish']);
});
it('retains edits and never publishes after a failed save', async () => {
  let published = false;
  server.use(
    http.put('*/api/v1/sop-revisions/:id', () =>
      HttpResponse.json({ code: 'VERSION_CONFLICT' }, { status: 412 }),
    ),
    http.post('*/api/v1/sop-revisions/:id/publish', () => {
      published = true;
      return HttpResponse.json({});
    }),
  );
  mount();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('总目标'), '修改');
  await user.click(screen.getByRole('button', { name: '发布 SOP' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('内容已被他人修改');
  expect(published).toBe(false);
  expect(screen.getByLabelText('总目标')).toHaveValue('整理文件修改');
});
