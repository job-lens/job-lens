import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { MatchEditor } from './MatchEditor';
const initial = {
  id: '0f803d78-2c67-4e03-ac3c-6b4c6bcdcc20',
  case_id: '41670d86-a1dc-4d6d-8bf0-219beca701a3',
  direction: '文件整理',
  focus: '核对文件名',
  basis: '文字指引',
  cycle_weeks: 4,
  state: 'draft',
  version: 1,
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
      <MatchEditor caseId={initial.case_id} />
    </QueryClientProvider>,
  );
}
it('saves dirty match content before confirming the returned version', async () => {
  let current = { ...initial };
  const calls: string[] = [];
  server.use(
    http.get('*/api/v1/cases/:id/match', () => HttpResponse.json(current)),
    http.put('*/api/v1/cases/:id/match', async ({ request }) => {
      calls.push('save');
      expect(request.headers.get('If-Match')).toBe('"1"');
      const body = (await request.json()) as typeof current;
      expect(body.direction).toBe('新的任务方向');
      current = { ...current, ...body, version: 2 };
      return HttpResponse.json(current);
    }),
    http.post('*/api/v1/cases/:id/match/confirm', ({ request }) => {
      calls.push('confirm');
      expect(request.headers.get('If-Match')).toBe('"2"');
      current = { ...current, state: 'confirmed', version: 3 };
      return HttpResponse.json(current);
    }),
  );
  mount();
  const user = userEvent.setup();
  const direction = await screen.findByLabelText('支持方向');
  await user.clear(direction);
  await user.type(direction, '新的任务方向');
  await user.click(screen.getByRole('button', { name: '确认匹配' }));
  expect(await screen.findByText('支持匹配（已确认）')).toBeVisible();
  expect(calls).toEqual(['save', 'confirm']);
});
it('never confirms if saving dirty content fails', async () => {
  let confirmed = false;
  server.use(
    http.get('*/api/v1/cases/:id/match', () => HttpResponse.json(initial)),
    http.put('*/api/v1/cases/:id/match', () =>
      HttpResponse.json({ code: 'VERSION_CONFLICT' }, { status: 412 }),
    ),
    http.post('*/api/v1/cases/:id/match/confirm', () => {
      confirmed = true;
      return HttpResponse.json(initial);
    }),
  );
  mount();
  const user = userEvent.setup();
  const direction = await screen.findByLabelText('支持方向');
  await user.type(direction, '修改');
  await user.click(screen.getByRole('button', { name: '确认匹配' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('内容已被他人修改');
  expect(confirmed).toBe(false);
  expect(direction).toHaveValue('文件整理修改');
});
