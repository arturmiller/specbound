import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('connects a provider pack and shows the real manifest and contract references', async ({ page }) => {
  await page.goto(`/providers?organization=${org}&view=catalog`);
  await expect(page.getByRole('heading', { name: 'Evidence Provider Packs' })).toBeVisible();
  await page.getByRole('link', { name: 'Git-Repository verbinden' }).click();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/provider-valid');
  await page.getByLabel('Release-Tag').fill('v1.2.0');
  await page.getByRole('button', { name: 'Provider-Pack verbinden' }).click();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
  await expect(page.getByText('org.acme.aws-network', { exact: true })).toBeVisible();
  await expect(page.getByText('fixture/provider-valid', { exact: true })).toBeVisible();
  await expect(page.getByText('a'.repeat(40), { exact: true })).toBeVisible();
  await expect(page.getByText('Input: contracts/collect-request.json')).toBeVisible();
  await page.getByRole('link', { name: 'net.internet-reachability/v1' }).click();
  await expect(page.getByText('Schema-Referenz: schemas/reachability.json')).toBeVisible();
  await expect(page.getByText('tests/reachability.yaml', { exact: true })).toBeVisible();
  await expect(page.getByText('Schema-Inhalt im Katalog nicht gespeichert.')).toBeVisible();
  await expect(page.getByText('Fixture-Inhalte und Testergebnisse sind im Katalog nicht gespeichert.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Capability-Vertrag und Testreferenzen' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Packs', exact: true }).click();
  await page.getByRole('row').filter({ hasText: 'fixture/provider-valid' }).getByRole('link', { name: 'org.acme.aws-network' }).click();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
});

test('invalid provider manifest stays visible as an error without an import', async ({ page }) => {
  await page.goto(`/providers?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('fixture/provider-invalid');
  await page.getByLabel('Release-Tag').fill('v1.2.0');
  await page.getByRole('button', { name: 'Provider-Pack verbinden' }).click();
  await expect(page.getByRole('alert')).toContainText('Provider-Manifest, Schema oder Repository ist ungültig');
  await expect(page).toHaveURL(/view=connect/);
});

test('viewers can inspect the mobile catalogue without a write action', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const provider = { id: 'provider', kind: 'provider', repository: 'fixture/provider', tag: 'v1', commit: 'a'.repeat(40), manifest: { metadata: { id: 'fixture.provider', version: '1' }, runtime: { kind: 'approved-container', image: 'image@sha256:123', input: 'contracts/in.json', output: 'contracts/out.json' }, capabilities: [{ id: 'fixture.read', version: 'v1', outputSchema: 'schemas/read.json' }] } };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:viewer', kind: 'user' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/packs') return route.fulfill({ json: [provider] });
    return route.fulfill({ json: [] });
  });
  await page.goto('/providers?organization=org&view=catalog');
  await expect(page.getByRole('link', { name: 'fixture.provider' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Git-Repository verbinden' })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  const table = page.getByLabel('Provider-Packs, horizontal scrollbar');
  await table.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.getByRole('link', { name: 'fixture.provider' }).click();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
  await expect(page.getByText('Eine Deklaration bestätigt weder Freigabe noch Verfügbarkeit.')).toBeVisible();
  await page.goto('/providers?organization=org&pack=provider&view=contract&capability=missing');
  await expect(page.getByText('Diese Capability ist in der Revision nicht vorhanden.')).toBeVisible();
  await expect(page.getByText('Schema-Referenz: schemas/read.json')).toHaveCount(0);
});

test('loading and forbidden provider catalogues are not shown as empty', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { id: 'user:viewer', kind: 'user' } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/packs', async (route) => { await waiting; await route.fulfill({ status: 403, body: '{}' }); });
  await page.goto('/providers?organization=org');
  await expect(page.getByText('Provider-Packs werden geladen …')).toBeVisible();
  release();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Noch keine Provider-Packs verbunden.')).toHaveCount(0);
});
