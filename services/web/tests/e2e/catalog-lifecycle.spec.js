import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';
const root = `/api/organizations/${org}/resources`;

test('removes a catalog with confirmation, retains its profile and restores the pinned revision', async ({ page }) => {
  const saved = {};
  for (const [kind, path, id] of [['Catalog', 'catalogs/application.json', 'application-controls'], ['Profile', 'profiles/application-baseline.json', 'application-baseline']]) {
    const response = await page.request.post(root, { data: { apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id, version: '1.0.0', name: id }, spec: { resourceType: kind, provider: 'github', repository: 'fixture/oscal-removal', ref: 'main', refType: 'branch', manifestPath: path, expected: { id, version: '1.0.0' } } } });
    expect(response.status()).toBe(201);
    saved[kind] = await response.json();
  }
  const catalogUrl = `${root}/${saved.Catalog.id}`;
  await page.goto(`/catalogs?resource=${saved.Catalog.id}`);
  await page.getByRole('button', { name: 'Katalog entfernen', exact: true }).click();
  await page.getByRole('button', { name: 'Abbrechen', exact: true }).click();
  expect((await (await page.request.get(catalogUrl)).json()).state).toBe('registered');
  await page.getByRole('button', { name: 'Katalog entfernen', exact: true }).click();
  await page.getByRole('button', { name: 'Entfernen bestätigen', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'aus der aktiven Liste entfernt' })).toBeVisible();
  expect(await (await page.request.get(`${root}/${saved.Profile.id}`)).json()).toEqual(saved.Profile);
  const archived = await (await page.request.get(catalogUrl)).json();
  expect(archived).toEqual({ ...saved.Catalog, state: 'archived' });
  expect((await (await page.request.get(root)).json()).some((item) => item.id === saved.Catalog.id)).toBe(false);
  await page.getByRole('link', { name: 'Alle Kataloge', exact: true }).click();
  await expect(page.locator(`.resource-product-grid a[href*="resource=${saved.Catalog.id}"]`)).toHaveCount(0);
  await page.getByText('Entfernte Kataloge (1)', { exact: true }).click();
  await page.locator(`a[href*="resource=${saved.Catalog.id}"]`).click();
  await page.setViewportSize({ width: 320, height: 844 });
  await page.getByRole('button', { name: 'Katalog wiederherstellen', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Katalog entfernen', exact: true })).toBeVisible();
  expect(await (await page.request.get(catalogUrl)).json()).toEqual(saved.Catalog);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
