import { expect, test } from '@playwright/test';

test('connects a fixture pack and shows validated controls and pinned provenance', async ({ page }) => {
  await page.goto('/packs?organization=123e4567-e89b-12d3-a456-426614174000');
  await expect(page.getByRole('heading', { name: 'Pack-Katalog' })).toBeVisible();
  await page.getByRole('link', { name: 'Repository verbinden' }).click();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/security');
  await page.getByLabel('Release-Tag').fill('v1.2.0');
  await page.getByRole('button', { name: 'Pack verbinden' }).click();
  await expect(page.getByRole('heading', { name: 'SEC-NET-001' })).toBeVisible();
  await expect(page.getByText('Commit:')).toContainText('a'.repeat(40));
  await expect(page.getByText('fixture/security', { exact: true })).toBeVisible();
  await expect(page.getByText('v1.2.0', { exact: true })).toBeVisible();
  await expect(page.getByText(/Agenten haben kein Freigaberecht/)).toBeVisible();
  await expect(page.getByText('Freigabestatus: Nicht freigegeben')).toBeVisible();
  await page.getByRole('button', { name: 'Governance-Pack freigeben' }).click();
  await expect(page.getByText(/Freigabestatus: Freigegeben von/)).toBeVisible();
  await expect(page.getByLabel(/branch/i)).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'SEC-NET-001' })).toBeVisible();
  await expect(page.getByText('Commit:')).toContainText('a'.repeat(40));
  await expect(page.getByText(/Freigabestatus: Freigegeben von/)).toBeVisible();
  await page.getByRole('button', { name: 'Freigabe zurücknehmen' }).click();
  await expect(page.getByText('Freigabestatus: Nicht freigegeben')).toBeVisible();
});

test('agents can read an approved pack but cannot connect or approve', async ({ page }) => {
  const org = 'org';
  const pack = { id: 'p1', repository: 'fixture/security', tag: 'v1', commit: 'a'.repeat(40), kind: 'governance', manifest: { metadata: { id: 'security', version: '1' } }, controls: [{ id: 'SEC-1', target: { kind: 'database' }, requiredEvidence: { capability: 'network/v1' } }, { id: 'SEC-2', target: { kind: 'storage' }, requiredEvidence: { capability: 'storage/v1' } }], capabilities: ['network/v1'] };
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'agent:fixture', kind: 'agent' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: org, name: 'Org', ownerPrincipalId: 'agent:fixture' }] });
    if (path === `/api/organizations/${org}/packs`) return route.fulfill({ json: [pack] });
    if (path === `/api/organizations/${org}/packs/p1/approval`) return route.fulfill({ json: { revisionId: 'p1', approved: true, approvedBy: 'user:owner' } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/packs?organization=org');
  await expect(page.getByRole('link', { name: 'security' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Repository verbinden' })).toHaveCount(0);
  await page.getByRole('link', { name: 'security' }).click();
  await expect(page.getByText('Freigabestatus: Freigegeben von user:owner')).toBeVisible();
  await expect(page.getByRole('button', { name: /freigeben|zurücknehmen/i })).toHaveCount(0);
  await expect(page.getByText('network/v1', { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.getByRole('button', { name: 'SEC-2' }).click();
  await expect(page.getByRole('heading', { name: 'SEC-2' })).toBeVisible();
  await expect(page.getByText('Evidence: storage/v1')).toBeVisible();
  const table = page.getByLabel('Kontrollen, horizontal scrollbar');
  await table.evaluate((element) => { element.scrollLeft = 0; });
  await table.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
});

test('loading and denied pack catalogues are not shown as empty', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { id: 'user:viewer', kind: 'user' } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/packs', async (route) => { await waiting; await route.fulfill({ status: 403, body: '{}' }); });
  await page.goto('/packs?organization=org');
  await expect(page.getByText('Packs werden geladen …')).toBeVisible();
  release();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Noch keine Packs verbunden.')).toHaveCount(0);
});

test('invalid manifests and changed tags are explained without creating a pack', async ({ page }) => {
  let status = 422;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:owner', kind: 'user' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/packs' && route.request().method() === 'POST') return route.fulfill({ status, body: '{}' });
    if (path === '/api/organizations/org/packs') return route.fulfill({ json: [] });
    return route.fulfill({ json: [] });
  });
  await page.goto('/packs?organization=org');
  await expect(page.getByText('Noch keine Packs verbunden.')).toBeVisible();
  await page.getByRole('link', { name: 'Repository verbinden' }).click();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/security');
  await page.getByLabel('Release-Tag').fill('v1');
  await page.getByRole('button', { name: 'Pack verbinden' }).click();
  await expect(page.getByRole('alert')).toContainText('Manifest oder Repository ist ungültig');
  status = 409;
  await page.getByRole('button', { name: 'Pack verbinden' }).click();
  await expect(page.getByRole('alert')).toContainText('Tag wurde verschoben');
  await expect(page).toHaveURL(/view=connect/);
});
