import { expect, test } from '@playwright/test';

for (const width of [1440, 390]) {
  test(`anonymous homepage at ${width}px stays public and fits the viewport`, async ({ page }) => {
    const apiRequests: string[] = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: '让工作，有清楚的下一步。' })).toBeVisible();
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

test('the companions stop all idle motion with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const image = page.getByRole('img', { name: '三个相伴的小精灵' });
  await expect(image).toBeVisible();
  await expect(page.getByRole('button', { name: '已按系统设置关闭动效' })).toBeDisabled();
  const animations = await image.evaluate(element =>
    [...element.querySelectorAll('g')].map(part => getComputedStyle(part).animationName),
  );
  expect(animations.every(name => name === 'none')).toBe(true);
});

test('a paused companion does not restart after reloading', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/login');
  await page.getByRole('button', { name: '暂停伙伴动效' }).click();
  await page.reload();
  await expect(page.getByRole('button', { name: '开启伙伴动效' })).toBeVisible();
  const animations = await page
    .getByRole('img', { name: '三个相伴的小精灵' })
    .evaluate(element =>
      [...element.querySelectorAll('g')].map(part => getComputedStyle(part).animationName),
    );
  expect(animations.every(name => name === 'none')).toBe(true);
});
