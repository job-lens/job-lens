import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { ErrorPanel, LoadingState } from './AsyncState';
it('offers an accessible retry action', async () => {
  const retry = vi.fn();
  render(<ErrorPanel message="连接失败" retry={retry} />);
  expect(screen.getByRole('alert')).toHaveTextContent('连接失败');
  await userEvent.click(screen.getByRole('button', { name: '重试' }));
  expect(retry).toHaveBeenCalledOnce();
});
it('announces loading', () => {
  render(<LoadingState />);
  expect(screen.getByRole('status')).toHaveTextContent('正在读取');
});
