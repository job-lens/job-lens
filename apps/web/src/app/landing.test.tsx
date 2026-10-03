import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';

beforeEach(() =>
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false })),
  ),
);
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

it('lets an anonymous visitor understand the training flow and reach login', async () => {
  window.history.replaceState(null, '', '/');
  const requests = vi.spyOn(globalThis, 'fetch');
  render(<App />);
  expect(
    await screen.findByRole('heading', { name: '把工作任务，变成能完成的每一步。' }),
  ).toBeVisible();
  expect(screen.getByRole('link', { name: '登录并开始' })).toHaveAttribute('href', '/login');
  expect(screen.getByRole('heading', { name: '从了解自己，到完成任务' })).toBeVisible();
  expect(screen.queryByText('融职境工程入口')).not.toBeInTheDocument();
  expect(requests).not.toHaveBeenCalled();
});

it('pairs the training story with an independent robot illustration and optional motion', async () => {
  const { default: userEvent } = await import('@testing-library/user-event');
  const user = userEvent.setup();
  render(<App />);
  expect(screen.getByRole('img', { name: '机器人陪你把任务拆成清楚的步骤' })).toBeVisible();
  const motion = screen.getByRole('button', { name: '关闭角色动效' });
  expect(motion).toHaveAttribute('aria-pressed', 'true');
  await user.click(motion);
  expect(screen.getByRole('button', { name: '开启角色动效' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
});
