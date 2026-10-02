import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from './App';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

it('keeps the homepage public while showing the training path and real login entry', async () => {
  window.history.replaceState(null, '', '/');
  const requests = vi.spyOn(globalThis, 'fetch');
  render(<App />);
  expect(await screen.findByRole('heading', { name: '让工作，有清楚的下一步。' })).toBeVisible();
  expect(screen.getByRole('link', { name: '登录并开始' })).toHaveAttribute('href', '/login');
  expect(screen.getByRole('region', { name: '训练流程' })).toBeVisible();
  expect(screen.getByRole('img', { name: '三个相伴的小精灵' })).toBeVisible();
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

it('lets a visitor explore the three example steps without claiming a real task submission', async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(screen.getByText('把文件名和清单上的名称逐项对照。')).toBeVisible();
  await user.click(screen.getByRole('button', { name: /^检查清单$/ }));
  expect(screen.getByText('沿着清单一项项检查，标出需要补充的内容。')).toBeVisible();
  await user.click(screen.getByRole('button', { name: /^整理结果$/ }));
  expect(screen.getByText('整理检查结果，交给辅导员查看并获得反馈。')).toBeVisible();
  expect(screen.getByText('步骤示意 · 3 / 3')).toBeVisible();
  expect(screen.queryByRole('button', { name: '提交' })).not.toBeInTheDocument();
});
