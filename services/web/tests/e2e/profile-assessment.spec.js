import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('starts a profile-bound scan and retains unsupported controls in its historical report', async ({ page }) => {
  await page.goto(`/products?organization=${org}`);
  let productId;
  for (const [resourceType, manifestPath, id] of [
    ['Catalog', 'catalogs/application.json', 'application-controls'],
    ['Profile', 'profiles/application-baseline.json', 'application-baseline'],
    ['Product', 'products/audio-visualizer.json', 'audio-visualizer'],
  ]) {
    const response = await page.request.post(`/api/organizations/${org}/resources`, { data: {
      apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id: 'source', version: '1.0.0', name: 'Source' },
      spec: { resourceType, provider: 'github', repository: 'fixture/oscal', ref: 'main', manifestPath, expected: { id, version: '1.0.0' } },
    } });
    expect(response.status()).toBe(201);
    if (resourceType === 'Product') productId = (await response.json()).resolved.productId;
  }
  await page.goto(`/products?organization=${org}&product=${productId}&view=repository`);
  const scan = page.getByRole('region', { name: 'Lizenzscan für djfun/audio-visualizer-python' });
  await expect(scan.getByText(/Scan fixiert das geltende Produktprofil/)).toBeVisible();
  await expect(scan.getByRole('button', { name: 'Öffentlichen Lizenzscan starten' })).toBeEnabled();
  await scan.getByRole('button', { name: 'Öffentlichen Lizenzscan starten' }).click();
  await expect(scan.getByText('Wartet auf den lokalen Worker')).toBeVisible();
  const processed = await page.request.post('/api/__e2e/process-public-license-scan');
  expect((await processed.json()).processed).toBe(true);
  await expect(scan.getByText('Abgeschlossen')).toBeVisible({ timeout: 8000 });
  await expect(scan.getByText('Application Baseline · 1.0.0')).toBeVisible();
  await expect(scan.getByText('OBSERVED', { exact: true })).toBeVisible();
  await scan.getByRole('link', { name: /Assessment und Findings/ }).click();
  const governance = page.getByRole('region', { name: 'Fixierter Geltungsbereich' });
  await expect(governance.getByRole('row').filter({ hasText: 'SEC-API-001' })).toContainText('Nicht unterstützt');
  await expect(governance.getByRole('row').filter({ hasText: 'SEC-API-001' })).toContainText('UNKNOWN');
  await expect(governance.getByRole('row').filter({ hasText: 'PY-LIC-001' })).toContainText('FAIL');
  await expect(governance.getByRole('link', { name: 'checks/application.json' })).toHaveAttribute('href', `https://github.com/fixture/oscal/blob/${'a'.repeat(40)}/checks/application.json`);
  await page.reload();
  await expect(governance).toContainText('2 ausgewählte Controls');
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
