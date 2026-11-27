import { expect, test } from '@playwright/test';

test('opens the exact saved PR result from a compact run list', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(seeded.status()).toBe(200);
  const { id, sha, organizationId } = await seeded.json();
  const overview = await (await request.get(`http://127.0.0.1:18762/organizations/${organizationId}/overview`)).json();
  expect(overview.assessments.find((item) => item.id === id).pullRequestNumber).toBe(17);
  await page.goto(`/pr-checks?organization=${organizationId}`);
  await expect(page.getByRole('heading', { name: 'PR-Prüfungen', exact: true })).toBeVisible();
  const run = page.getByRole('list', { name: 'Gespeicherte PR-Prüfungen' }).getByRole('link', { name: /PR #17/ });
  await expect(run).toContainText('1 Verstoß');
  await expect(run).not.toContainText(sha);
  await run.click();
  await expect(page).toHaveURL(new RegExp(`/assessments/${id}$`));
  await expect(page.getByRole('heading', { name: 'Prüfung fehlgeschlagen' })).toBeVisible();
  await expect(page.getByText(id, { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Quellverweis: repo:/)).toBeHidden();
  await page.getByRole('link', { name: 'PR-Prüfungen', exact: true }).last().click();
  await expect(run).toBeVisible();
});

test('loading, empty, denied and missing states remain distinct on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/overview', async (route) => { await pending; await route.fulfill({ json: { products: [], assessments: [] } }); });
  await page.goto('/pr-checks?organization=org');
  await expect(page.getByText(/Assessments werden geladen/)).toBeVisible();
  release();
  await expect(page.getByText('Keine sichtbaren PR-Assessments gespeichert.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.unroute('**/api/organizations/org/overview');
  await page.route('**/api/organizations/org/overview', (route) => route.fulfill({ json: {
    products: [{ id: 'product', name: 'Produktname' }],
    assessments: Array.from({ length: 12 }, (_, index) => ({
      id: `run-${index}`, productId: 'product', context: 'pull_request', pullRequestNumber: index + 1,
      createdAt: '2026-11-22T07:00:00Z', counts: { PASS: 1, FAIL: 0, UNKNOWN: 0 },
    })),
  } }));
  await page.reload();
  const runs = page.getByRole('list', { name: 'Gespeicherte PR-Prüfungen' }).getByRole('link');
  await expect(runs).toHaveCount(10);
  await page.getByRole('button', { name: 'Weitere Läufe anzeigen' }).click();
  await expect(runs).toHaveCount(12);
  await page.unroute('**/api/organizations/org/overview');
  await page.route('**/api/organizations/org/overview', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await page.route('**/api/assessments/missing', (route) => route.fulfill({ status: 404, body: '{}' }));
  await page.goto('/assessments/missing');
  await expect(page.getByRole('alert')).toContainText('Assessment nicht gefunden');
  await page.route('**/api/assessments/foreign', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.goto('/assessments/foreign');
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await page.route('**/api/assessments/base', (route) => route.fulfill({ json: { assessment: { id: 'base', organizationId: 'org', productId: 'product', context: 'baseline', pullRequestNumber: null, environment: 'production', gitSha: 'a'.repeat(40), packSha: 'b'.repeat(40), counts: { PASS: 0, FAIL: 0, UNKNOWN: 0, NOT_APPLICABLE: 0 } }, evaluations: [], evidence: [], findings: [] } }));
  await page.goto('/assessments/base?view=review');
  await expect(page.getByRole('heading', { name: 'Prüfung unvollständig' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Assessment-Ansichten' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Prüfungen', exact: true })).toBeVisible();
});
