import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';
const root = `/api/organizations/${org}/resources`;
const ownCatalogs = (items) => items.filter((item) => item.resourceType === 'Catalog' && item.source.repository === 'fixture/oscal');

test('previews and imports grouped native OSCAL controls with real stored provenance', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  await page.goto(`/catalogs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  await expect(page.getByLabel('Erwartete Katalog-ID')).toHaveCount(0);
  await expect(page.getByLabel('Erwartete Version')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Katalog registrieren' })).toBeDisabled();
  const before = ownCatalogs(await (await page.request.get(root)).json());
  await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
  const preview = page.getByRole('region', { name: 'Katalogvorschau' });
  await expect(preview.getByText('Struktur geprüft · noch nicht registriert')).toBeVisible();
  await expect(preview.getByText('application-controls · Version 1.0.0')).toBeVisible();
  expect((ownCatalogs(await (await page.request.get(root)).json())).length).toBe(before.length);
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
  await expect(page.getByRole('heading', { name: 'Application Controls', exact: true })).toBeVisible({ timeout: 10000 });
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
  expect(consoleErrors).toEqual([]);
});

test('a changed source requires a new preview before registration', async ({ page }) => {
  await page.goto(`/catalogs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  const before = ownCatalogs(await (await page.request.get(root)).json());
  const register = page.getByRole('button', { name: 'Katalog registrieren' });
  const check = page.getByRole('button', { name: 'Vorschau prüfen' });
  await check.click();
  await expect(register).toBeEnabled();
  const ref = page.getByLabel('Git-Ref', { exact: true });
  await ref.fill('another-branch');
  await expect(register).toBeDisabled();
  await ref.fill('main');
  await page.route(`**${root}?preview=false`, (route) => route.fulfill({
    status: 409, json: { detail: 'Reviewed configuration or references changed; check again' },
  }));
  await register.click();
  await expect(page.getByRole('alert')).toContainText('Prüfe die Vorschau erneut');
  await expect(register).toBeDisabled();
  await expect(page.getByRole('region', { name: 'Katalogvorschau' })).toHaveCount(0);
  expect((ownCatalogs(await (await page.request.get(root)).json())).length).toBe(before.length);
  await check.click();
  await expect(register).toBeEnabled();
});

test('a slow source can be cancelled or times out and a later retry remains usable', async ({ page }) => {
  await page.clock.install();
  await page.goto(`/catalogs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  const data = { resourceType: 'Catalog', repository: 'fixture/oscal', ref: 'main', refType: 'branch', manifestPath: 'catalogs/application.json' };
  const fixture = await (await page.request.post(`${root}/preview`, { data })).json();
  const release = [];
  let requests = 0;
  await page.route(`**${root}/preview`, async (route) => {
    requests += 1;
    if (requests <= 2) await new Promise((resolve) => release.push(resolve));
    await route.fulfill({ json: fixture });
  });
  const check = page.getByRole('button', { name: 'Vorschau prüfen', exact: true });
  await check.click();
  await expect(page.getByRole('button', { name: 'Abbrechen', exact: true })).toBeVisible();
  await expect.poll(() => release.length).toBe(1);
  await page.getByRole('button', { name: 'Abbrechen', exact: true }).click();
  await expect(check).toBeEnabled();
  release[0]();
  await expect(page.getByRole('region', { name: 'Katalogvorschau' })).toHaveCount(0);
  await check.click();
  await expect.poll(() => release.length).toBe(2);
  await page.clock.fastForward(45001);
  await expect(page.getByRole('alert')).toContainText('Zeitlimit');
  await expect(check).toBeEnabled();
  await expect(page.getByText('Quelle wird gelesen und geprüft …')).toHaveCount(0);
  release[1]();
  await check.click();
  await expect(page.getByRole('region', { name: 'Katalogvorschau' })).toContainText('Application Controls');
  await expect(page.getByRole('alert')).toHaveCount(0);
});
