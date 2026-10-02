import { expect, test } from '@playwright/test';

for (const width of [1440, 390]) {
  test(`anonymous homepage at ${width}px stays public and fits the viewport`, async ({ page }) => {
    const apiRequests: string[] = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: '慢慢来，一起完成。' })).toBeVisible();
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

test('the companions stay still with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const image = page.getByRole('img', { name: '三个安静相伴的小机器人' });
  await expect(image).toBeVisible();
  expect(await image.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
});
