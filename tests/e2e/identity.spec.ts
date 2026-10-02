import { execFileSync } from 'node:child_process';
import { expect, test } from '@playwright/test';

const password = process.env.E2E_PASSWORD;
test.describe('real Cookie identity lifecycle', () => {
  test.skip(!password, 'Requires disposable fixture accounts; no identity APIs are mocked');
  test('login, reload, idle expiry, return to the original page and logout', async ({
    page,
    context,
  }) => {
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login$/);
    await page.getByLabel('账号', { exact: true }).fill('fixture_learner');
    await page.getByLabel('密码', { exact: true }).fill(password!);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
    const cookie = (await context.cookies()).find(item => item.name === '__Host-jl_session');
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.secure).toBe(true);
    expect(cookie?.sameSite).toBe('Lax');
    await page.reload();
    await expect(page.getByRole('heading', { name: '个人资料' })).toBeVisible();
    if (process.env.E2E_FIXTURE_MODE === 'docker') {
      execFileSync('docker', [
        'compose',
        'exec',
        '-T',
        'api',
        'python',
        'tools/identity_fixture.py',
        'expire',
      ]);
    } else {
      execFileSync(process.env.E2E_PYTHON ?? 'python', ['tools/identity_fixture.py', 'expire']);
    }
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText('会话已结束。登录后，继续刚才的任务。')).toBeVisible();
    await page.getByLabel('账号', { exact: true }).fill('fixture_learner');
    await page.getByLabel('密码', { exact: true }).fill(password!);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect((await context.cookies()).some(item => item.name === '__Host-jl_session')).toBe(false);
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login$/);
  });
  test('confirmed counselor role chooses the counselor workspace', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('账号', { exact: true }).fill('fixture_counselor');
    await page.getByLabel('密码', { exact: true }).fill(password!);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page).toHaveURL(/\/counselor$/);
    await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
  });
});
