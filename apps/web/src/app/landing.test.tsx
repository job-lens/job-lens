import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

it('keeps the homepage public while showing the training path and real login entry', async () => {
  window.history.replaceState(null, '', '/');
  const requests = vi.spyOn(globalThis, 'fetch');
  render(<App />);
  expect(await screen.findByRole('heading', { name: '慢慢来，一起完成。' })).toBeVisible();
  expect(screen.getByRole('link', { name: '登录并开始' })).toHaveAttribute('href', '/login');
  expect(screen.getByRole('region', { name: '训练流程' })).toBeVisible();
  expect(screen.getByRole('img', { name: '三个安静相伴的小机器人' })).toBeVisible();
  expect(requests).not.toHaveBeenCalled();
});

it('gives anonymous login its own immersive page outside the workspace navigation', async () => {
  window.history.replaceState(null, '', '/login');
  const requests = vi.spyOn(globalThis, 'fetch');
  render(<App />);
  expect(await screen.findByRole('heading', { name: '登录' })).toBeVisible();
  expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('账号')).toHaveAttribute('autocomplete', 'username');
  expect(screen.getByLabelText('密码')).toHaveAttribute('autocomplete', 'current-password');
  expect(requests).not.toHaveBeenCalled();
});
