import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('imports two source manifests with real schemas, permissions and control usage', async ({ page }) => {
  await page.goto(`/evidence-packs?organization=${org}`);
  const catalog = await page.request.post(`/api/organizations/${org}/resources`, { data: {
    apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id: 'catalog', version: '1.0.0', name: 'Catalog' },
    spec: { resourceType: 'Catalog', provider: 'github', repository: 'fixture/oscal', ref: 'main', manifestPath: 'catalogs/application.json', expected: { id: 'application-controls', version: '1.0.0' } },
  } });
  expect(catalog.status()).toBe(201);
  for (const [folder, id] of [['example', 'org.specbound.example-auth'], ['second', 'org.specbound.example-license']]) {
    await page.goto(`/evidence-packs?organization=${org}&view=connect`);
    await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal');
    await page.getByLabel('Manifestpfad').fill(`evidence/${folder}/provider.json`);
    await page.getByLabel('Erwartete Evidence Pack-ID').fill(id);
    await page.getByRole('button', { name: 'Vorschau prüfen' }).click();
    await expect(page.getByRole('region', { name: 'Evidence Packvorschau' })).toContainText('keine Ausführungsfreigabe');
    await page.getByRole('button', { name: 'Evidence Pack registrieren' }).click();
    await expect(page.getByRole('heading', { name: 'Provider-Manifest', exact: true })).toBeVisible();
    const contracts = page.getByRole('region', { name: 'Datenverträge und Berechtigungen' });
    await expect(contracts).toContainText('Registrierung: gespeichert · Struktur: validiert');
    await contracts.locator('summary').filter({ hasText: 'contracts/request.json' }).click();
    await expect(contracts.locator('pre').filter({ hasText: 'https://json-schema.org/draft/2020-12/schema' }).first()).toBeVisible();
    await expect(contracts.getByRole('link', { name: 'Datei in Git' }).first()).toHaveAttribute('href', `https://github.com/fixture/oscal/blob/${'a'.repeat(40)}/evidence/${folder}/contracts/request.json`);
    await page.reload();
    await expect(page.getByRole('region', { name: 'Capability-Zuordnung' })).toContainText(folder === 'second' ? 'PY-LIC-001' : 'SEC-API-001');
  }
  const packs = (await (await page.request.get(`/api/organizations/${org}/packs`)).json()).filter((item) => item.repository === 'fixture/oscal');
  expect(new Set(packs.map((item) => item.manifestPath))).toEqual(new Set(['evidence/example/provider.json', 'evidence/second/provider.json']));
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('rejects invalid provider contracts without saving a source', async ({ page }) => {
  await page.goto(`/evidence-packs?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/oscal-invalid');
  await page.getByLabel('Manifestpfad').fill('evidence/second/provider.json');
  await page.getByLabel('Erwartete Evidence Pack-ID').fill('org.specbound.example-license');
  await page.getByRole('button', { name: 'Evidence Pack registrieren' }).click();
  await expect(page.getByRole('alert')).toContainText('ungültig');
  const resources = await (await page.request.get(`/api/organizations/${org}/resources`)).json();
  expect(resources.some((item) => item.source.repository === 'fixture/oscal-invalid')).toBe(false);
});
