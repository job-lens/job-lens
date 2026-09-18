import { expect, test } from '@playwright/test';

test('real Web -> gateway -> API -> migrated PostgreSQL', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('API 与数据库已连接');
});
test('a direct workspace URL preserves the SPA and fails closed without identity service', async ({ page }) => {
  await page.goto('/learner');
  await expect(page.getByText('身份服务暂不可用')).toBeVisible();
  await page.reload();
  await expect(page.getByText('身份服务暂不可用')).toBeVisible();
});
test('unknown client paths render an error instead of breaking the app', async ({ page }) => {
  await page.goto('/missing-page');
  await expect(page.getByText('页面不存在')).toBeVisible();
});
test('mocked learner identity cannot enter the counselor workspace', async ({ page }) => {
  await page.route('**/api/v1/me', route => route.fulfill({json: {
    id:'00000000-0000-4000-8000-000000000001', display_name:'测试账号', roles:['learner'],
  }}));
  await page.goto('/counselor');
  await expect(page.getByText('无权访问此区域')).toBeVisible();
});
test('mocked expired session redirects to the login boundary', async ({ page }) => {
  await page.route('**/api/v1/me', route => route.fulfill({status:401, json: {
    type:'urn:job-lens:problem:unauthenticated', status:401, code:'UNAUTHENTICATED', title:'请登录',trace_id:'test',
  }}));
  await page.goto('/learner');
  await expect(page).toHaveURL(/\/login$/);
});
