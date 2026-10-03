import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { RegisterPage, ForgotPasswordPage, ResetPasswordPage } from './AccountPages';
const server = setupServer(
  http.get('*/api/v1/auth/csrf', () =>
    HttpResponse.json({ csrf_token: 'test-email-csrf-token-1234' }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount(path = '/register') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: '/register', element: <RegisterPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
      { path: '/learner', element: <h1>学员工作台</h1> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { client, router };
}
it('shows delivery failure without pretending a code was sent', async () => {
  server.use(
    http.post('*/api/v1/auth/registration-code', () =>
      HttpResponse.json({ title: '邮件服务暂不可用', code: 'EMAIL_UNAVAILABLE' }, { status: 503 }),
    ),
  );
  const user = userEvent.setup();
  mount();
  await user.type(screen.getByLabelText('邮箱'), 'learner@example.invalid');
  await user.click(screen.getByRole('button', { name: '获取验证码' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('邮件服务暂不可用');
  expect(screen.queryByText('验证码已发送，请查看邮箱。')).not.toBeInTheDocument();
});
it('registers with the documented contract and stores the returned real session', async () => {
  server.use(
    http.post('*/api/v1/auth/register', async ({ request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('test-email-csrf-token-1234');
      expect(await request.json()).toEqual({
        email: 'learner@example.invalid',
        code: '123456',
        password: 'training-password',
        display_name: '学员',
      });
      return HttpResponse.json(
        {
          user: { id: 'x', display_name: '学员', roles: ['learner'] },
          csrf_token: 'rotated-email-csrf-1234',
        },
        { status: 201 },
      );
    }),
  );
  const user = userEvent.setup();
  const { client } = mount();
  await user.type(screen.getByLabelText('称呼'), '学员');
  await user.type(screen.getByLabelText('邮箱'), 'learner@example.invalid');
  await user.type(screen.getByLabelText('验证码'), '123456');
  await user.type(screen.getByLabelText('密码'), 'training-password');
  await user.click(screen.getByRole('button', { name: '注册' }));
  expect(await screen.findByRole('heading', { name: '学员工作台' })).toBeVisible();
  expect(client.getQueryData(['session'])).toEqual({
    id: 'x',
    display_name: '学员',
    roles: ['learner'],
  });
});
it('uses a uniform reset request acknowledgement', async () => {
  server.use(
    http.post('*/api/v1/auth/password-reset-requests', () =>
      HttpResponse.json({ message: '请求已受理，请查看邮箱。' }, { status: 202 }),
    ),
  );
  const user = userEvent.setup();
  mount('/forgot-password');
  await user.type(screen.getByLabelText('邮箱'), 'learner@example.invalid');
  await user.click(screen.getByRole('button', { name: '发送找回链接' }));
  expect(await screen.findByRole('status')).toHaveTextContent('请求已受理');
});
it('submits the fragment token once and clears private cache after resetting', async () => {
  const token = 'a'.repeat(43);
  server.use(
    http.post('*/api/v1/auth/password-resets', async ({ request }) => {
      expect(await request.json()).toEqual({ token, password: 'updated-training-password' });
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const user = userEvent.setup();
  const { client } = mount('/reset-password#token=' + token);
  client.setQueryData(['private-record'], { private: true });
  await user.type(screen.getByLabelText('新密码'), 'updated-training-password');
  await user.click(screen.getByRole('button', { name: '保存新密码' }));
  expect(await screen.findByRole('status')).toHaveTextContent('密码已更新');
  expect(client.getQueryData(['private-record'])).toBeUndefined();
  expect(window.location.hash).toBe('');
});
