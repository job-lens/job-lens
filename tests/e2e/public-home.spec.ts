import { expect, test } from '@playwright/test';

for (const width of [1440, 390]) {
  test(`anonymous homepage at ${width}px stays public and fits the viewport`, async ({ page }) => {
    const apiRequests: string[] = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(
      page.getByRole('heading', { name: '把工作任务，变成能完成的每一步。' }),
    ).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    expect(apiRequests).toEqual([]);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: '跳到主要内容' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('main')).toBeFocused();
    await page.getByRole('link', { name: '登录并开始' }).click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: '登录' })).toBeVisible();
  });
}
