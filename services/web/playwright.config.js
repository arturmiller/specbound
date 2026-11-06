import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  timeout: 20000,
  expect: { timeout: 4000 },
  use: { baseURL: 'http://127.0.0.1:18763', browserName: 'chromium' },
  webServer: [
    {
      command: 'python -m tests.e2e_server',
      cwd: '../api',
      url: 'http://127.0.0.1:18762/healthz',
      env: { OIDC_ISSUER: '', OIDC_JWKS_URL: '', OIDC_CLIENT_ID: '', OIDC_AUDIENCE: '' },
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: 'npm run dev -- --port 18763 --strictPort',
      url: 'http://127.0.0.1:18763/',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:18762' },
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
