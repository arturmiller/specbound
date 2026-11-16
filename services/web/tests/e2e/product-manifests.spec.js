import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('registers a real product manifest and follows product to profile and catalog after reload', async ({ page }) => {
  await page.goto(`/products?organization=${org}`);
  for (const [resourceType, manifestPath, id] of [
    ['Catalog', 'catalogs/application.json', 'application-controls'],
    ['Profile', 'profiles/application-baseline.json', 'application-baseline'],
  ]) {
    const response = await page.request.post(`/api/organizations/${org}/resources`, { data: {
      apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource',
      metadata: { id, version: '1.0.0', name: id },
      spec: { resourceType, provider: 'github', repository: 'fixture/oscal', ref: 'main', manifestPath, expected: { id, version: '1.0.0' } },
    } });
    expect(response.status()).toBe(201);
  }
  await page.reload();
  await page.getByRole('link', { name: 'Produkt aus Manifest registrieren' }).click();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
  await page.getByLabel('Erwartete Produkt-ID').fill('audio-visualizer');
  await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
  await expect(page.getByRole('region', { name: 'Produktvorschau' })).toContainText('2 geltende Controls');
  await page.getByRole('button', { name: 'Produkt registrieren' }).click();
  const scope = page.getByRole('region', { name: 'Geltungsbereich' });
  await expect(scope.getByRole('heading', { name: 'Geltungsbereich' })).toBeVisible();
  await expect(scope.getByRole('link', { name: 'djfun/audio-visualizer-python' })).toBeVisible();
  await expect(scope.getByRole('link', { name: 'fixture/oscal' })).toHaveCount(0);
  await page.reload();
  await expect(scope.getByText('2 ausdrücklich zugeordnete Controls:')).toBeVisible();
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await scope.getByRole('link', { name: 'Application Baseline · 1.0.0' }).click();
  await expect(page.getByRole('heading', { name: 'Application Baseline', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Application Controls · 1.0.0' }).click();
  await expect(page.getByRole('heading', { name: 'Application Controls', exact: true })).toBeVisible();
});
