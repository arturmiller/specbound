import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';
const root = `/api/organizations/${org}/resources`;

test('previews and imports grouped native OSCAL controls with real stored provenance', async ({ page }) => {
  await page.goto(`/catalogs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  await page.getByLabel('Erwartete Katalog-ID').fill('application-controls');
  const before = await (await page.request.get(root)).json();
  await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
  const preview = page.getByRole('region', { name: 'Katalogvorschau' });
  await expect(preview.getByText('Struktur geprüft · noch nicht registriert')).toBeVisible();
  expect((await (await page.request.get(root)).json()).length).toBe(before.length);
  await expect(preview.getByRole('heading', { name: /Application Governance/ })).toBeVisible();
  await page.getByRole('button', { name: 'Katalog registrieren' }).click();
  await expect(page.getByRole('heading', { name: 'Application Controls', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Application Governance/ })).toBeVisible();
  const auth = page.locator('summary').filter({ hasText: 'SEC-API-001' });
  await auth.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Public API requests require authentication.', { exact: true })).toBeVisible();
  await expect(page.getByText('api.authentication/v1', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Anforderung in Git', exact: true })).toHaveAttribute('href', `https://github.com/fixture/oscal/blob/${'a'.repeat(40)}/catalogs/application.json`);
  const savedUrl = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Application Controls', exact: true })).toBeVisible();
  expect(page.url()).toBe(savedUrl);
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.locator('summary').filter({ hasText: 'PY-LIC-001' }).click();
    await expect(page.getByText('python.package-license/v1', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('summary').filter({ hasText: 'PY-LIC-001' }).click();
  }
  await page.getByLabel('Controls suchen').fill('no-match');
  await expect(page.getByRole('button', { name: 'Suche zurücksetzen' })).toBeVisible();
  await page.getByRole('button', { name: 'Suche zurücksetzen' }).click();
  await expect(page.locator('summary').filter({ hasText: 'PY-LIC-001' })).toBeVisible();
});

test('wrong native identity stays an explicit error and does not create a revision', async ({ page }) => {
  await page.goto(`/catalogs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  await page.getByLabel('Erwartete Katalog-ID').fill('missing-catalog');
  const before = await (await page.request.get(root)).json();
  await page.getByRole('button', { name: 'Katalog registrieren' }).click();
  await expect(page.getByRole('alert')).toContainText('ungültig oder noch nicht unterstützt');
  expect((await (await page.request.get(root)).json()).length).toBe(before.length);
  await expect(page).toHaveURL(/view=connect/);
});
