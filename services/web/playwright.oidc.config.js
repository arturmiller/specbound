import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/oidc',
  retries: 0,
  timeout: 30000,
  expect: { timeout: 6000 },
  use: { baseURL: 'http://127.0.0.1:18766', browserName: 'chromium' },
  webServer: [
    {
      command: 'python -m tests.oidc_test_provider',
      cwd: '../api',
      url: 'http://127.0.0.1:18764/.well-known/openid-configuration',
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: 'python -m tests.oidc_e2e_server',
      cwd: '../api',
      url: 'http://127.0.0.1:18765/healthz',
      env: {
        OIDC_ISSUER: 'http://127.0.0.1:18764',
        OIDC_JWKS_URL: 'http://127.0.0.1:18764/jwks',
        OIDC_CLIENT_ID: 'specbound-web',
        OIDC_AUDIENCE: 'urn:specbound:api',
      },
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: 'npm run dev -- --port 18766 --strictPort',
      url: 'http://127.0.0.1:18766/',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:18765' },
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
