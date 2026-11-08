import { defineConfig } from '@playwright/test';

// Runs against the explicit local-auth Compose stack, not a mocked API.
export default defineConfig({
  testDir: './tests/local-auth',
  workers: 1,
  retries: 0,
  timeout: 60000,
  expect: { timeout: 10000 },
  use: { baseURL: 'http://127.0.0.1:5173', browserName: 'chromium' },
});
