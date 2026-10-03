import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { proxy: { '/api': process.env.JOB_LENS_API_PROXY ?? 'http://127.0.0.1:8000' } },
  test: {
    environment: './test/environment.ts',
    globals: true,
    setupFiles: './src/test/setup.ts',
    restoreMocks: true,
  },
});
