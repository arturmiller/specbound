import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('imports a native profile and navigates its selected controls and catalog', async ({ page }) => {
  await page.goto(`/profiles?organization=${org}&view=connect`);
  const catalog = await page.request.post(`/api/organizations/${org}/resources`, { data: {
    apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource',
    metadata: { id: 'catalog-source', version: '1.0.0', name: 'Catalog source' },
    spec: { resourceType: 'Catalog', provider: 'github', repository: 'fixture/oscal', ref: 'main', refType: 'branch', manifestPath: 'catalogs/application.json', expected: { id: 'application-controls', version: '1.0.0' } },
  } });
  expect(catalog.status()).toBe(201);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  await page.getByLabel('Erwartete Profil-ID').fill('application-baseline');
  await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
  await expect(page.getByRole('region', { name: 'Profilvorschau' })).toBeVisible();
  await page.getByRole('button', { name: 'Profil registrieren' }).click();
  await expect(page.getByRole('heading', { name: 'Application Baseline', exact: true })).toBeVisible();
  const licensing = page.locator('details.resource-control').filter({ has: page.locator('summary').filter({ hasText: 'PY-LIC-001' }) });
  await licensing.locator('summary').first().click();
  await licensing.getByText('Prüflogik anzeigen', { exact: true }).click();
  await expect(licensing.locator('.pack-json').first()).toContainText('"ISC"');
  await expect(licensing.getByRole('link', { name: 'Anforderung in Git' })).toHaveAttribute('href', `https://github.com/fixture/oscal/blob/${'a'.repeat(40)}/catalogs/application.json`);
  await page.getByRole('link', { name: 'Application Controls · 1.0.0', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Application Controls', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Application Baseline · 1.0.0', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Application Baseline', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Application Baseline', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
