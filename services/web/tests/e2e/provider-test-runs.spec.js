import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('owner can reserve a synthetic test run and see it after reload', async ({ page }) => {
  await page.goto(`/providers?organization=${org}&view=connect`);
  await page.getByLabel('Repository', { exact: true }).fill('arturmiller/specbound-example-provider');
  await page.getByLabel('Release-Tag').fill('v1.1.0');
  await page.getByRole('button', { name: 'Provider-Pack verbinden' }).click();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
  const runs = page.getByRole('region', { name: 'Synthetische Testläufe' });
  await expect(runs.getByText('Die Ausführung ist noch nicht verfügbar.', { exact: false })).toBeVisible();
  await expect(runs.getByText('Noch keine Testläufe vorgemerkt.')).toBeVisible();
  await runs.getByRole('button', { name: 'Testlauf vormerken' }).click();
  await expect(runs.getByText('Vorgemerkt · synthetisch')).toBeVisible();
  await expect(runs.getByText('Pack-Commit:', { exact: false })).toContainText('a'.repeat(40));
  await page.reload();
  await expect(runs.getByText('Vorgemerkt · synthetisch')).toBeVisible();
  await expect(runs.getByText('erzeugt keine Evidence', { exact: false })).toBeVisible();
});

test('viewer cannot see or create runs on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:viewer', kind: 'user' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/packs') return route.fulfill({ json: [{ id: 'pack', repository: 'arturmiller/specbound-example-provider', tag: 'v1.1.0', commit: 'a'.repeat(40), kind: 'provider', manifest: { metadata: { id: 'example', version: '1.1.0' }, runtime: { kind: 'approved-container', image: 'image', input: 'in', output: 'out' }, capabilities: [{ id: 'demo.fixture', version: 'v1', outputSchema: 'schema' }] } }] });
    return route.fulfill({ json: [] });
  });
  await page.goto('/providers?organization=org&pack=pack');
  const runs = page.getByRole('region', { name: 'Synthetische Testläufe' });
  await expect(runs.getByText('Nur Organisationseigentümer können Testläufe vormerken und ansehen.')).toBeVisible();
  await expect(runs.getByRole('button', { name: 'Testlauf vormerken' })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('a failed test-run request is not shown as an empty list', async ({ page }) => {
  let release;
  const wait = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:owner', kind: 'user' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/packs') return route.fulfill({ json: [{ id: 'pack', repository: 'arturmiller/specbound-example-provider', tag: 'v1.1.0', commit: 'a'.repeat(40), kind: 'provider', manifest: { metadata: { id: 'example', version: '1.1.0' }, runtime: { kind: 'approved-container', image: 'image', input: 'in', output: 'out' }, capabilities: [{ id: 'demo.fixture', version: 'v1', outputSchema: 'schema' }] } }] });
    if (path.endsWith('/test-runs')) { await wait; return route.fulfill({ status: 503, body: '{}' }); }
    return route.fulfill({ json: [] });
  });
  await page.goto('/providers?organization=org&pack=pack');
  const runs = page.getByRole('region', { name: 'Synthetische Testläufe' });
  await expect(runs.getByRole('status')).toContainText('Testläufe werden geladen');
  release();
  await expect(runs.getByRole('alert')).toContainText('Testläufe konnten nicht geladen werden');
  await expect(runs.getByText('Noch keine Testläufe vorgemerkt.')).toHaveCount(0);
  await expect(runs.getByRole('button', { name: 'Testlauf vormerken' })).toBeDisabled();
});
