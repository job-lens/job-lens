import { expect, test } from '@playwright/test';

const password = process.env.E2E_PASSWORD;
test.describe('real training review and rework', () => {
  test.skip(!password, 'Requires synthetic training fixtures in a disposable test database');
  test.describe.configure({ retries: 0 });
  test('learner completes steps, counselor requests one redo, learner resubmits and receives a pass', async ({
    page,
  }) => {
    async function login(role: 'learner' | 'counselor') {
      await page.goto('/login');
      await page.getByLabel('账号', { exact: true }).fill('mock_' + role);
      await page.getByLabel('密码', { exact: true }).fill(password!);
      await page.getByRole('button', { name: '登录', exact: true }).click();
      await expect(page).toHaveURL(role === 'learner' ? /\/learner$/ : /\/counselor$/);
    }
    async function logout() {
      await page.getByRole('button', { name: '退出登录' }).click();
      await expect(page).toHaveURL(/\/login$/);
    }
    await login('learner');
    await page.getByRole('link', { name: '查看任务', exact: true }).click();
    const taskUrl = page.url();
    const taskId = taskUrl.split('/').at(-1)!;
    await page.getByRole('button', { name: '开始训练' }).click();
    for (const instruction of [
      '先核对清单上的名称。',
      '按顺序放到对应的位置。',
      '再检查一次，确认没有遗漏。',
    ]) {
      await expect(page.getByRole('heading', { name: instruction, exact: true })).toBeVisible();
      await page.getByRole('button', { name: '这一步完成了' }).click();
    }
    await page.getByRole('button', { name: '提交结果' }).click();
    await expect(page.getByRole('heading', { name: '结果已提交。' })).toBeVisible();
    await logout();
    await login('counselor');
    await page.goto('/counselor/tasks/' + taskId);
    await page.getByRole('link', { name: '审核提交' }).click();
    await page.getByRole('radio', { name: '需修改', exact: true }).check();
    await page.getByRole('checkbox', { name: '需重做' }).last().check();
    await page.getByLabel('反馈说明').fill('前两步已完成，第三步请再检查一次。');
    await page.getByRole('button', { name: '提交审核' }).click();
    await expect(page.getByRole('heading', { name: '审核结论（已提交）' })).toBeVisible();
    await logout();
    await login('learner');
    await page.goto(taskUrl);
    await page.getByRole('button', { name: '继续修改' }).click();
    await expect(
      page.getByRole('heading', { name: '再检查一次，确认没有遗漏。', exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: '这一步完成了' }).click();
    await page.getByRole('button', { name: '提交结果' }).click();
    await expect(page.getByRole('heading', { name: '结果已提交。' })).toBeVisible();
    await logout();
    await login('counselor');
    await page.goto('/counselor/tasks/' + taskId);
    await page.getByRole('link', { name: '审核提交' }).click();
    await page.getByLabel('反馈说明').fill('检查完成，这次训练通过。');
    await page.getByRole('button', { name: '提交审核' }).click();
    await expect(page.getByRole('heading', { name: '审核结论（已提交）' })).toBeVisible();
    await logout();
    await login('learner');
    await page.goto(taskUrl);
    await expect(page.getByRole('heading', { name: '这次训练完成了。' })).toBeVisible();
    await expect(page.getByText('检查完成，这次训练通过。').first()).toBeVisible();
  });
});
