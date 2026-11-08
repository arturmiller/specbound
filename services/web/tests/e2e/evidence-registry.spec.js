import { expect, test } from '@playwright/test';

test('opens persisted evidence with scope, provenance and expired freshness', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  const report = await (await request.get(`http://127.0.0.1:18762/assessments/${item.id}`)).json();
  const evidence = report.evidence[0];
  expect(evidence).toBeTruthy();
  await page.addInitScript(() => { Date.now = () => Date.parse('2027-01-01T00:00:00Z'); });
  await page.goto(`/evidence?organization=${item.organizationId}`);
  await expect(page.getByRole('heading', { name: 'Evidence-Register' })).toBeVisible();
  await expect(page.getByText('Abgelaufen · UNKNOWN')).toBeVisible();
  await page.getByRole('link', { name: evidence.id }).click();
  await expect(page.getByRole('heading', { name: 'Gespeicherte Observation' })).toBeVisible();
  await expect(page.getByText(evidence.collectorRevision, { exact: true })).toBeVisible();
  await expect(page.getByText(evidence.collectorImage, { exact: true })).toBeVisible();
  await expect(page.getByText(evidence.targetRevision, { exact: true })).toBeVisible();
  await expect(page.getByText(evidence.provenance.sourceRef, { exact: true })).toBeVisible();
  await expect(page.getByText('Abgelaufen · UNKNOWN')).toBeVisible();
  await expect(page.getByText(/Eine Provider-ID ist in diesem Datensatz nicht gespeichert/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Gespeicherte Observation' })).toBeVisible();
  await page.getByRole('link', { name: 'Zurück zum Evidence-Register' }).click();
  await expect(page.getByRole('link', { name: evidence.id })).toBeVisible();
});

test('evidence pagination, freshness and mobile keyboard use actual page data', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => { Date.now = () => Date.parse('2026-06-01T00:00:00Z'); });
  const record = (id, expiresAt) => ({ id, productId: 'product', subjectId: 'subject:one', capability: 'fixture.read/v1', environment: 'test', targetRevision: 'a'.repeat(40), collectorRevision: 'b'.repeat(40), collectorImage: 'fixture@sha256:123', provenance: { sourceRef: 'collector:fixture' }, value: { result: true }, observedAt: '2026-01-01T00:00:00Z', expiresAt, ttlSeconds: 60 });
  const first = Array.from({ length: 10 }, (_, i) => record(`evidence-${i}`, '2026-02-01T00:00:00Z'));
  const last = record('evidence-last', '2026-12-01T00:00:00Z');
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (url.pathname === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (url.pathname === '/api/organizations/org/products') return route.fulfill({ json: [{ id: 'product', name: 'Product' }] });
    if (url.pathname === '/api/organizations/org/evidence') return route.fulfill({ json: url.searchParams.get('offset') === '10' ? { items: [last], nextOffset: null } : { items: first, nextOffset: 10 } });
    if (url.pathname === '/api/organizations/org/evidence/evidence-last') return route.fulfill({ json: last });
    return route.fulfill({ json: [] });
  });
  await page.goto('/evidence?organization=org');
  await expect(page.getByRole('link', { name: 'evidence-0' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  const table = page.getByLabel('Evidence, horizontal scrollbar');
  await table.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.getByRole('link', { name: 'Nächste Seite' }).click();
  await expect(page.getByText('Zeitlich gültig')).toBeVisible();
  await page.getByRole('link', { name: 'evidence-last' }).click();
  await expect(page.getByText('Zeitlich gültig')).toBeVisible();
  await page.getByRole('link', { name: 'Zurück zum Evidence-Register' }).click();
  await expect(page).toHaveURL(/offset=10/);
  await page.getByRole('link', { name: 'Vorherige Seite' }).click();
  await expect(page.getByRole('link', { name: 'evidence-0' })).toBeVisible();
});

test('provider directory shows declarations without inventing health', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const created = await request.post(`http://127.0.0.1:18762/organizations/${org}/packs`, { data: { repository: 'fixture/provider-directory', tag: 'v1.2.0', kind: 'provider' } });
  expect(created.status()).toBe(201);
  await page.goto(`/providers?organization=${org}`);
  await expect(page.getByRole('heading', { name: 'Evidence Provider', exact: true })).toBeVisible();
  const row = page.getByRole('row').filter({ hasText: 'fixture/provider-directory' });
  // The directory links a declared revision; health is not inferred from import.
  await expect(row).toContainText('UNKNOWN');
  await row.getByRole('link').click();
  await expect(page.getByRole('heading', { name: 'Network Provider' })).toBeVisible();
  await expect(page.getByText('Ausführungsfreigabe und Zugangsdaten: UNKNOWN.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Evidence-Register öffnen' })).toBeVisible();
  await page.getByRole('link', { name: 'Manifest ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Provider-Manifest' })).toBeVisible();
});

test('empty, loading and forbidden evidence states are distinct', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  let forbidden = false;
  await page.route('**/api/organizations/org/evidence?*', async (route) => {
    await waiting;
    if (forbidden) await route.fulfill({ status: 403, body: '{}' });
    else await route.fulfill({ json: { items: [], nextOffset: null } });
  });
  await page.goto('/evidence?organization=org');
  await expect(page.getByText('Evidence wird geladen …')).toBeVisible();
  release();
  await expect(page.getByText('Keine Evidence auf dieser Seite vorhanden. Evidenzlage: UNKNOWN.')).toBeVisible();
  forbidden = true;
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Keine Evidence auf dieser Seite vorhanden. Evidenzlage: UNKNOWN.')).toHaveCount(0);
});
