import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  // The live audit needs a running local backend (vite /api proxy ->
  // localhost:8000) and a Windows screenshot dir; CI runs the mocked suite.
  testIgnore: process.env.CI ? ['**/live-console-audit.spec.ts'] : [],
  fullyParallel: true,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
