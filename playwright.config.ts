import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'pnpm dev',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: !process.env.CI,
      },
});
