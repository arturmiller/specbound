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

test('assigns a manifest to an existing product through its scope page', async ({ page }) => {
  const context = await (await page.request.get('/api/workspace')).json();
  const root = `/api/organizations/${org}`;
  for (const [kind, path, id] of [['Catalog', 'catalogs/application.json', 'application-controls'], ['Profile', 'profiles/application-baseline.json', 'application-baseline']]) {
    const response = await page.request.post(`${root}/resources`, { data: {
      apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource',
      metadata: { id, version: '1.0.0', name: id },
      spec: { resourceType: kind, provider: 'github', repository: 'fixture/oscal', ref: 'main', manifestPath: path, expected: { id, version: '1.0.0' } },
    } });
    expect(response.status()).toBe(201);
  }
  const product = await (await page.request.post(`${root}/products`, {
    data: { name: 'Existing Audio Visualizer', ownerTeamId: context.defaultOwnerTeamId },
  })).json();
  const repositories = `/api/products/${product.id}/repositories`;
  const binding = await (await page.request.post(repositories, {
    data: { provider: 'github', repository: 'djfun/audio-visualizer-python' },
  })).json();
  await page.goto(`/products?product=${product.id}&view=scope`);
  await page.getByRole('link', { name: 'Produktmanifest zuordnen' }).click();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal-adoption');
  await page.getByLabel('Erwartete Produkt-ID').fill('audio-visualizer-adoption');
  const assign = page.getByRole('button', { name: 'Manifest zuordnen', exact: true });
  await expect(assign).toBeDisabled();
  await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
  await expect(assign).toBeEnabled();
  await assign.click();
  await expect(page).toHaveURL(new RegExp(`product=${product.id}&view=scope`));
  await expect(page.getByText('Geltendes Profil:')).toBeVisible();
  expect((await (await page.request.get(repositories)).json())[0].id).toBe(binding.id);
});
