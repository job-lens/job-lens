import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { WorkspaceShell } from './WorkspaceShell';

const server = setupServer(
  http.get('*/api/v1/me/profile', () => HttpResponse.json({ display_name: '林老师' })),
);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
});
afterAll(() => server.close());
function mount(roles: string[], path = '/counselor', width = 1280) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['session'], { id: 'synthetic-user', display_name: '林老师', roles });
  const router = createMemoryRouter(
    [
      {
        element: <WorkspaceShell />,
        children: [
          { path: '/counselor', element: <h1>个案内容</h1> },
          { path: '/learner', element: <h1>学员任务</h1> },
          { path: '/settings', element: <h1>账户设置内容</h1> },
          { path: '/notifications', element: <h1>通知列表内容</h1> },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}
it('shows only destinations for the confirmed role and preserves location-aware navigation', async () => {
  const router = mount(['counselor']);
  const nav = screen.getByRole('navigation', { name: '主导航' });
  expect(within(nav).queryByRole('link', { name: '我的任务' })).not.toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: '工作台' })).toHaveAttribute('aria-current', 'page');
  await userEvent.click(within(nav).getByRole('link', { name: '个案管理' }));
  expect(router.state.location.search).toBe('?tab=cases');
  expect(within(nav).getByRole('link', { name: '个案管理' })).toHaveAttribute(
    'aria-current',
    'page',
  );
  expect(within(nav).getByRole('link', { name: '工作台' })).not.toHaveAttribute('aria-current');
  expect(await screen.findByText('林老师')).toBeVisible();
});
it('keeps counselor routes out of learner navigation', () => {
  mount(['learner'], '/learner');
  const nav = screen.getByRole('navigation', { name: '主导航' });
  expect(within(nav).getByRole('link', { name: '我的任务' })).toBeVisible();
  expect(within(nav).queryByRole('link', { name: '个案管理' })).not.toBeInTheDocument();
  expect(within(nav).queryByRole('link', { name: '辅导与求助' })).not.toBeInTheDocument();
});
it('retains the collapsed rail when navigating and keeps named controls', async () => {
  mount(['counselor']);
  await userEvent.click(screen.getByRole('button', { name: '收起侧栏' }));
  expect(screen.getByRole('button', { name: '展开侧栏' })).toBeVisible();
  await userEvent.click(screen.getByRole('link', { name: '通知中心' }));
  expect(await screen.findByRole('heading', { name: '通知列表内容' })).toBeVisible();
  expect(screen.getByRole('button', { name: '展开侧栏' })).toBeVisible();
  expect(screen.getByRole('button', { name: '退出登录' })).toHaveAccessibleName('退出登录');
});
it('contains mobile focus, closes on Escape, and returns focus to the trigger', async () => {
  mount(['counselor'], '/counselor', 390);
  const user = userEvent.setup();
  const trigger = screen.getByRole('button', { name: '打开菜单' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await user.click(trigger);
  const drawer = screen.getByRole('dialog', { name: '融职境导航' });
  expect(drawer).toHaveAttribute('aria-modal', 'true');
  expect(screen.getByRole('button', { name: '关闭菜单' })).toHaveFocus();
  expect(document.querySelector('main')?.parentElement).toHaveAttribute('inert');
  within(drawer).getByRole('button', { name: '退出登录' }).focus();
  await user.tab();
  expect(within(drawer).getByRole('link', { name: '融职境工作台' })).toHaveFocus();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
it('closes the drawer on navigation and supports reopening repeatedly', async () => {
  const router = mount(['learner'], '/learner', 390);
  const user = userEvent.setup();
  const trigger = screen.getByRole('button', { name: '打开菜单' });
  await user.click(trigger);
  await user.click(screen.getByRole('link', { name: '设置' }));
  await waitFor(() => expect(router.state.location.pathname).toBe('/settings'));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  await user.click(trigger);
  expect(screen.getByRole('dialog')).toBeVisible();
  await user.click(screen.getByRole('button', { name: '关闭菜单' }));
  expect(trigger).toHaveFocus();
});
it('uses the confirmed session identity without a second profile request', async () => {
  let profileRequests = 0;
  server.use(
    http.get('*/api/v1/me/profile', () => {
      profileRequests += 1;
      return new HttpResponse(null, { status: 401 });
    }),
  );
  mount(['counselor']);
  expect(screen.getByText('林老师')).toBeVisible();
  await userEvent.click(screen.getByRole('link', { name: '通知中心' }));
  expect(await screen.findByRole('heading', { name: '通知列表内容' })).toBeVisible();
  expect(profileRequests).toBe(0);
});
it('clears a mobile drawer when resizing to desktop so it does not reopen on return', async () => {
  mount(['learner'], '/learner', 390);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '打开菜单' }));
  expect(screen.getByRole('dialog')).toBeVisible();
  act(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(document.querySelector('main')?.parentElement).not.toHaveAttribute('inert');
  act(() => {
    Object.defineProperty(window, 'innerWidth', { value: 390, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '打开菜单' })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  await user.click(screen.getByRole('button', { name: '打开菜单' }));
  expect(screen.getByRole('dialog')).toBeVisible();
});
