import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';
const root = `/api/organizations/${org}/resources`;

test('reviews and adopts valid profile/product revisions, rejects invalid updates and retains historical evidence', async ({ page }) => {
  test.setTimeout(60000);
  const consoleErrors = [];
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  await page.goto('/products');
  await page.request.post('/api/__e2e/resource-revision?stage=initial');
  const saved = {};
  for (const [kind, path, id] of [
    ['Catalog', 'catalogs/application.json', 'application-controls'],
    ['Profile', 'profiles/application-baseline.json', 'application-baseline'],
    ['Product', 'products/audio-visualizer.json', 'audio-visualizer-updates'],
  ]) {
    const response = await page.request.post(root, { data: { apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id, version: '1.0.0', name: id }, spec: { resourceType: kind, provider: 'github', repository: 'fixture/oscal-updates', ref: 'main', refType: 'branch', manifestPath: path, expected: { id, version: '1.0.0' } } } });
    expect(response.status()).toBe(201);
    saved[kind] = await response.json();
  }
  const product = saved.Product.resolved.productId;
  const binding = (await (await page.request.get(`/api/products/${product}/repositories`)).json())[0];
  const scanUrl = `/api/products/${product}/repositories/${binding.id}/public-license-scans`;
  const job = await (await page.request.post(scanUrl, { data: { ref: 'main' } })).json();
  expect((await page.request.post(`/api/__e2e/process-public-license-scan?scan_id=${job.id}`)).status()).toBe(200);
  const snapshot = (await (await page.request.get(scanUrl)).json())[0].assessmentId;
  expect(snapshot).toBeTruthy();
  const historical = await (await page.request.get(`/api/assessments/${snapshot}`)).json();
  await page.request.post('/api/__e2e/resource-revision?stage=updated');
  await page.goto(`/profiles?resource=${saved.Profile.id}`);
  const revisions = page.getByRole('region', { name: 'Ressourcenrevision', exact: true });
  await revisions.getByRole('button', { name: 'Neue Revision prüfen', exact: true }).click();
  const comparison = page.getByRole('region', { name: 'Revisionsvergleich' });
  await expect(comparison).toContainText('Controls neu: PY-LIC-001');
  await expect(comparison.getByRole('link', { name: 'profiles/application-baseline.json' }).last()).toHaveAttribute('href', new RegExp(`/blob/${'c'.repeat(40)}/`));
  await comparison.getByRole('button', { name: 'Revision übernehmen', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Application Baseline', exact: true })).toBeVisible();
  await expect(page).not.toHaveURL(new RegExp(`resource=${saved.Profile.id}`));
  expect((await (await page.request.get(`/api/products/${product}/governance`)).json()).profile.id).toBe(saved.Profile.id);
  await page.goto(`/products?product=${product}&view=scope`);
  await page.setViewportSize({ width: 320, height: 844 });
  await page.request.post('/api/__e2e/resource-revision?stage=invalid');
  await revisions.getByRole('button', { name: 'Neue Revision prüfen', exact: true }).click();
  await expect(revisions.getByRole('alert')).toContainText('bisherige Stand bleibt erhalten');
  expect((await (await page.request.get(`/api/products/${product}/governance`)).json()).product.id).toBe(saved.Product.id);
  await page.request.post('/api/__e2e/resource-revision?stage=updated');
  await revisions.getByRole('button', { name: 'Neue Revision prüfen', exact: true }).click();
  await expect(comparison).toContainText('Controls neu: PY-LIC-001');
  await expect(comparison).toContainText('Bewertungsfolgen wurden nicht berechnet');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await comparison.getByRole('button', { name: 'Revision übernehmen', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Audio Visualizer Updated', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'example/updated-source', exact: true })).toBeVisible();
  await revisions.getByText('Übernahmeprotokoll (1)', { exact: true }).click();
  await expect(revisions).toContainText('user:e2e');
  expect(await (await page.request.get(`/api/assessments/${snapshot}`)).json()).toEqual(historical);
  await page.getByRole('navigation', { name: 'Produktansichten' }).getByRole('link', { name: 'Anforderungen', exact: true }).click();
  await page.getByRole('combobox', { name: 'Prüfung', exact: true }).selectOption(snapshot);
  await expect(page.getByText('2 Controls · 1 Einzelbewertungen · 1 ausgewählte Nachweise')).toBeVisible();
  await page.locator('.requirements-control summary').filter({ hasText: 'PY-LIC-001' }).click();
  await expect(page.locator('.requirements-control[open]')).toContainText('FAIL');
  await expect(page.locator('.requirements-control[open]')).toContainText('GPL-3.0-only');
  expect(consoleErrors.filter((message) => !message.includes('422 (Unprocessable Entity)'))).toEqual([]);
});
