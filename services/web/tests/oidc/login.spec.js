import { expect, test } from '@playwright/test';

test('signs in with PKCE and sends a verified access token to the API', async ({ page, request }) => {
  await page.goto('/');
  const authorizedRequest = page.waitForRequest((request) => request.url().endsWith('/api/organizations') && Boolean(request.headers().authorization));
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await expect(page.getByText('Angemeldet.', { exact: false })).toBeVisible();
  const apiRequest = await authorizedRequest;
  const authorization = apiRequest.headers().authorization;
  const me = await request.get('http://127.0.0.1:18765/auth/me', { headers: { authorization } });
  expect(me.status()).toBe(200);
  expect((await me.json()).kind).toBe('user');
  const org = await request.post('http://127.0.0.1:18765/organizations', {
    headers: { authorization }, data: { name: 'OIDC organization' },
  });
  expect(org.status()).toBe(201);
  await page.reload();
  await expect(page.getByLabel('Organisation')).toContainText('OIDC organization');
  await page.getByRole('button', { name: 'Lokal abmelden' }).click();
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();
});

test('rejects an unsolicited authorization callback', async ({ page }) => {
  await page.goto('/?code=invalid&state=unknown');
  await expect(page.getByRole('alert')).toContainText('Anmeldung konnte nicht initialisiert werden');
  await expect(page).not.toHaveURL(/code=/);
});
