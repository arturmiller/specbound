import { expect, test } from '@playwright/test';

test('signs in with PKCE and sends a verified access token to the API', async ({ page, request }) => {
  await page.goto('/');
  const authorizedRequest = page.waitForRequest((request) => request.url().endsWith('/api/workspace') && Boolean(request.headers().authorization));
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await expect(page.getByText('Angemeldet.', { exact: false })).toBeVisible();
  const apiRequest = await authorizedRequest;
  const authorization = apiRequest.headers().authorization;
  const me = await request.get('http://127.0.0.1:18765/auth/me', { headers: { authorization } });
  expect(me.status()).toBe(200);
  expect((await me.json()).kind).toBe('user');
  await expect(page.getByRole('heading', { name: 'Produkte', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Lokal abmelden' }).click();
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();
});

test('rejects an unsolicited authorization callback', async ({ page }) => {
  await page.goto('/?code=invalid&state=unknown');
  await expect(page.getByRole('alert')).toContainText('Anmeldung konnte nicht initialisiert werden');
  await expect(page).not.toHaveURL(/code=/);
});

test('returns to the requested assessment after signing in', async ({ page }) => {
  await page.goto('/assessments/example-report');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe('/assessments/example-report');
  await expect(page.getByRole('alert')).toContainText('Assessment nicht gefunden');
});

test('returns to a portal route and its document anchor after signing in', async ({ page }) => {
  await page.goto('/docs#docs/security');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await expect.poll(() => ({ pathname: new URL(page.url()).pathname, hash: new URL(page.url()).hash })).toEqual({ pathname: '/docs', hash: '#docs/security' });
  await expect(page.getByRole('article', { name: 'Dokumentationsinhalt' }).getByRole('heading', { name: 'Security', exact: true })).toBeVisible();
});
