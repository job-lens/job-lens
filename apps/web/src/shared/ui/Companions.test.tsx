import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { Companions } from './Companions';

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('remembers an explicit pause across component remounts and lets the user resume', async () => {
  const user = userEvent.setup();
  const view = render(<Companions />);
  await user.click(screen.getByRole('button', { name: '暂停伙伴动效' }));
  expect(screen.getByRole('button', { name: '开启伙伴动效' })).toBeEnabled();
  view.unmount();
  render(<Companions />);
  expect(screen.getByRole('button', { name: '开启伙伴动效' })).toBeEnabled();
  await user.click(screen.getByRole('button', { name: '开启伙伴动效' }));
  expect(screen.getByRole('button', { name: '暂停伙伴动效' })).toBeEnabled();
});

it('responds to system motion changes and never overrides a user pause', async () => {
  const events = new EventTarget();
  let reduced = false;
  vi.stubGlobal('matchMedia', () => ({
    get matches() {
      return reduced;
    },
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  }));
  const user = userEvent.setup();
  render(<Companions />);
  await user.click(screen.getByRole('button', { name: '暂停伙伴动效' }));
  act(() => {
    reduced = true;
    events.dispatchEvent(new Event('change'));
  });
  expect(screen.getByRole('button', { name: '已按系统设置关闭动效' })).toBeDisabled();
  act(() => {
    reduced = false;
    events.dispatchEvent(new Event('change'));
  });
  expect(screen.getByRole('button', { name: '开启伙伴动效' })).toBeEnabled();
});
