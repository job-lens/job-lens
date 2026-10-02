import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => window.history.replaceState(null, '', '/'));

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
