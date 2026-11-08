import { expect, test } from '@playwright/test';

test('search and filters lead from actual findings to the exact report and product', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  const overviewData = await (await request.get(`http://127.0.0.1:18762/organizations/${item.organizationId}/overview`)).json();
  const finding = overviewData.findings.find((entry) => entry.snapshotId === item.id);
  await page.goto(`/overview?organization=${item.organizationId}`);
  const overview = page.getByRole('region', { name: 'Übersicht und Suche' });
  await expect(overview.getByRole('link', { name: /TEST-1/ })).toHaveAttribute('href', `/findings?organization=${item.organizationId}&finding=${finding.id}`);
  await overview.getByLabel('Teamfilter').selectOption(item.teamId);
  await overview.getByLabel('Scope').selectOption('test');
  await overview.getByLabel('Suche').fill('TEST-1');
  await expect(overview.getByRole('link', { name: /TEST-1/ })).toBeVisible();
  await expect(overview.getByText('Keine passenden Produkte.')).toBeVisible();
  await overview.getByRole('link', { name: /TEST-1/ }).click();
  await expect(page.getByRole('link', { name: 'Assessment-Bericht öffnen' })).toHaveAttribute('href', `/assessments/${item.id}`);
  await page.getByRole('link', { name: 'Assessment-Bericht öffnen' }).click();
  await expect(page).toHaveURL(new RegExp(`/assessments/${item.id}$`));
  await expect(page.getByText(item.id, { exact: true }).first()).toBeVisible();
  await page.goto(`/overview?organization=${item.organizationId}`);
  const productResults = page.locator('.overview-results .panel').filter({ has: page.getByRole('heading', { name: 'Produkte', exact: true }) });
  await productResults.getByRole('link', { name: 'Product' }).click();
  await expect(page).toHaveURL(new RegExp(`product=${item.productId}`));
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
});

test('dashboard metrics and filters use several teams and historical snapshots', async ({ page }) => {
  const data = {
    products: [{ id: 'p1', name: 'Alpha', teamId: 't1' }, { id: 'p2', name: 'Beta', teamId: 't2' }],
    packs: [{ id: 'pack1', name: 'security', repository: 'org/security', tag: 'v1', kind: 'governance' }],
    findings: [{ id: 'f1', productId: 'p1', subjectId: 's1', controlId: 'CTL-1', environment: 'prod', status: 'open', snapshotId: 'a1' }, { id: 'f2', productId: 'p2', subjectId: 's2', controlId: 'CTL-2', environment: 'test', status: 'open', snapshotId: 'a2' }, { id: 'f3', productId: 'p1', subjectId: 's3', controlId: 'CTL-3', environment: 'prod', status: 'resolved', snapshotId: 'a1' }],
    assessments: [{ id: 'a1', productId: 'p1', environment: 'prod', context: 'baseline', createdAt: '2026-01-01T00:00:00Z', gitSha: 'a'.repeat(40), counts: { PASS: 2, FAIL: 1, UNKNOWN: 1, NOT_APPLICABLE: 0 }, evaluations: [] }, { id: 'a2', productId: 'p2', environment: 'test', context: 'pull_request', createdAt: '2026-02-01T00:00:00Z', gitSha: 'b'.repeat(40), counts: { PASS: 0, FAIL: 0, UNKNOWN: 2, NOT_APPLICABLE: 1 }, evaluations: [] }],
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 't1', name: 'Team A' }, { id: 't2', name: 'Team B' }] });
    if (path === '/api/organizations/org/overview') return route.fulfill({ json: data });
    return route.fulfill({ json: [] });
  });
  await page.goto('/overview?organization=org');
  const metrics = page.locator('.overview-metrics');
  const metric = (label) => metrics.locator('.panel').filter({ hasText: label });
  await expect(metric('Verbundene Packs')).toContainText('1');
  await expect(metric('Passende Produkte')).toContainText('2');
  await expect(metric('Bewertungen in Snapshots')).toContainText('7');
  await expect(metric('Offene Findings')).toContainText('2');
  await expect(metric('UNKNOWN in Snapshots')).toContainText('3');
  await expect(page.getByRole('img', { name: 'Bewertungen pro historischem Snapshot' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Verteilung von 7 historischen Bewertungen' })).toBeVisible();
  await page.getByLabel('Teamfilter').selectOption('t1');
  await expect(metric('Passende Produkte')).toContainText('1');
  await expect(metric('Bewertungen in Snapshots')).toContainText('4');
  await expect(metric('Offene Findings')).toContainText('1');
  await expect(metric('UNKNOWN in Snapshots')).toContainText('1');
  await page.getByLabel('Scope').selectOption('prod');
  await expect(page.getByRole('link', { name: /CTL-1/ })).toHaveAttribute('href', '/findings?organization=org&finding=f1');
  await page.getByRole('textbox', { name: 'Suche' }).fill('CTL-2');
  await expect(metric('Offene Findings')).toContainText('0');
  await expect(page.getByText('Keine passenden Produkte.')).toBeVisible();
  await page.getByRole('textbox', { name: 'Suche' }).clear();
  delete data.assessments[0].counts.UNKNOWN;
  await page.getByRole('button', { name: 'Aktualisieren' }).click();
  await expect(metric('Bewertungen in Snapshots')).toContainText('UNKNOWN');
  await expect(page.getByText('Bewertungszahlen sind unvollständig: UNKNOWN.')).toHaveCount(2);
});

test('dashboard loading, empty and denied states remain honest on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  await page.route('**/api/organizations/org/teams', (route) => route.fulfill({ json: [] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  let denied = false;
  await page.route('**/api/organizations/org/overview', async (route) => { await waiting; if (denied) await route.fulfill({ status: 403, body: '{}' }); else await route.fulfill({ json: { products: [], packs: [], findings: [], assessments: [] } }); });
  await page.goto('/overview?organization=org');
  await expect(page.getByText('Übersicht wird geladen …')).toBeVisible();
  release();
  await expect(page.getByText('Keine Bewertungen vorhanden. Gesamtzustand: UNKNOWN.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  denied = true;
  await page.getByRole('button', { name: 'Aktualisieren' }).click();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.locator('.overview-metrics')).toHaveCount(0);
});

test('a failed team list does not pretend the filter is complete', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  await page.route('**/api/organizations/org/teams', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/api/organizations/org/overview', (route) => route.fulfill({ json: { products: [], packs: [], findings: [], assessments: [] } }));
  await page.goto('/overview?organization=org');
  await expect(page.getByRole('alert')).toContainText('Teamfilter nicht verfügbar');
  await expect(page.getByLabel('Teamfilter')).toBeDisabled();
});

test('a pack result opens the actual selected pack revision', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const response = await request.post(`http://127.0.0.1:18762/organizations/${org}/packs`, {
    data: { repository: 'fixture/overview-pack', tag: 'v1.2.0', kind: 'governance' },
  });
  expect(response.status()).toBe(201);
  const pack = await response.json();
  await page.goto(`/overview?organization=${org}`);
  const overview = page.getByRole('region', { name: 'Übersicht und Suche' });
  await overview.getByLabel('Suche').fill('overview-pack');
  await overview.getByRole('link', { name: /v1.2.0/ }).click();
  await expect(page).toHaveURL(new RegExp(`pack=${pack.id}`));
  await expect(page.getByRole('heading', { name: 'com.acme.security' })).toBeVisible();
  await expect(page.getByText('fixture/overview-pack', { exact: true })).toBeVisible();
});
