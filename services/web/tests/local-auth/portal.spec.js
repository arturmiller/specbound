import { expect, test } from '@playwright/test';

const login = process.env.SPECBOUND_LOCAL_TEST_USER || 'local-e2e';

async function signIn(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await page.locator('input[name="login"]').fill(login);
  await page.locator('input[name="password"]').fill('local-only');
  await page.getByRole('button', { name: 'Sign-in' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
}

test('local login uses an API access token and creates the first organization', async ({ page, request }) => {
  const api = 'http://127.0.0.1:8000';
  expect((await request.get(`${api}/organizations`)).status()).toBe(401);
  expect((await request.get(`${api}/organizations`, { headers: { Authorization: 'Bearer invalid' } })).status()).toBe(401);

  await signIn(page);
  await expect(page.getByText('Keine Organisationen verfügbar.')).toBeVisible();

  const tokens = await page.evaluate(() => {
    const key = Object.keys(sessionStorage).find((item) => item.startsWith('oidc.user:'));
    if (!key) throw new Error('OIDC session missing');
    const user = JSON.parse(sessionStorage.getItem(key));
    const [header, payload] = user.access_token.split('.').slice(0, 2).map((part) => JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/'))));
    return { access: user.access_token, id: user.id_token, header, payload };
  });
  expect(tokens.header).toMatchObject({ alg: 'RS256', typ: 'at+jwt' });
  expect(tokens.payload).toMatchObject({ iss: 'http://127.0.0.1:15556', aud: 'urn:specbound:api', client_id: 'specbound-web' });
  expect(tokens.payload.scope.split(' ')).toContain('openid');
  expect((await request.get(`${api}/auth/me`, { headers: { Authorization: `Bearer ${tokens.access}` } })).status()).toBe(200);
  expect((await request.get(`${api}/organizations`, { headers: { Authorization: `Bearer ${tokens.id}` } })).status()).toBe(401);

  await page.getByLabel('Organisationsname').fill('Lokale Organisation');
  await page.getByRole('button', { name: 'Organisation erstellen' }).click();
  await expect(page.getByRole('combobox', { name: 'Organisation', exact: true })).toHaveValue(/.+/);
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Teams', exact: true }).click();
  await page.getByRole('link', { name: 'Team erstellen' }).click();
  await page.getByLabel('Teamname').fill('Lokales Team');
  await page.getByRole('button', { name: 'Team erstellen und weiter' }).click();
  await expect(page.getByRole('heading', { name: 'Mitglieder & Rollen' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Produkte', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Produkte', level: 1 })).toBeVisible();
  await page.getByRole('link', { name: 'Produkt registrieren' }).click();
  await page.getByLabel('Produktname').fill('Lokales Produkt');
  await page.getByRole('button', { name: 'Produkt erstellen und weiter' }).click();
  await page.getByLabel('Git-Repository').fill('fixture/local-e2e');
  await page.getByRole('button', { name: 'Repository verbinden' }).click();
  await expect(page.getByText(/GitHub-Zugriff konnte nicht bestätigt werden/)).toBeVisible();
  await page.reload();
  await expect(page.getByText('fixture/local-e2e', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Discovery ansehen' }).click();
  await expect(page.getByText('Keine Scanbeobachtungen vorhanden. Discovery-Zustand: UNKNOWN.')).toBeVisible();
  await page.getByRole('link', { name: 'Produkt ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Packs', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Pack-Katalog', level: 1 })).toBeVisible();
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Teams', exact: true }).click();

  await page.reload();
  await expect(page.getByRole('link', { name: 'Lokales Team' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Organisation', exact: true }).locator('option')).toHaveCount(1);
});

test('existing organization persists after restart', async ({ page }) => {
  await signIn(page);
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Teams', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Lokales Team' })).toBeVisible();
  const organization = page.getByRole('combobox', { name: 'Organisation', exact: true });
  await expect(organization.locator('option')).toHaveCount(1);
  await expect(organization.locator('option')).toHaveText('Lokale Organisation');
  await expect(page.getByLabel('Organisationsname')).toHaveCount(0);
});
