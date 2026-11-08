import { expect, test } from '@playwright/test';

test('a real finding links its exact assessment and evidence with separate revisions', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  const overview = await (await request.get(`http://127.0.0.1:18762/organizations/${item.organizationId}/overview`)).json();
  const finding = overview.findings.find((entry) => entry.snapshotId === item.id);
  const report = await (await request.get(`http://127.0.0.1:18762/assessments/${item.id}`)).json();
  const event = report.findings.find((entry) => entry.id === finding.id);
  const evaluation = report.evaluations.find((entry) => entry.id === event.evaluationId);
  const evidence = report.evidence.find((entry) => evaluation.evidenceIds.includes(entry.id));
  expect(evidence).toBeTruthy();
  await page.addInitScript(() => { Date.now = () => Date.parse('2027-01-01T00:00:00Z'); });
  await page.goto(`/overview?organization=${item.organizationId}`);
  await page.getByRole('link', { name: /TEST-1.*open/ }).click();
  await expect(page.getByRole('heading', { name: /TEST-1/ })).toBeVisible();
  await expect(page.getByText('FAIL', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(report.assessment.gitSha, { exact: true })).toBeVisible();
  await expect(page.getByText(report.assessment.packSha, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Assessment-Bericht öffnen' })).toHaveAttribute('href', `/assessments/${item.id}`);
  await expect(page.getByText(/Abgelaufen · UNKNOWN/)).toBeVisible();
  await page.getByRole('link', { name: evidence.id }).click();
  await expect(page.getByRole('heading', { name: 'Evidence-Details' })).toBeVisible();
  await expect(page.getByText('Abgelaufen · UNKNOWN')).toBeVisible();
  await expect(page.getByText('FAIL', { exact: true })).toBeVisible();
  await expect(page.locator('dl div').filter({ has: page.getByText('Provider-/Packrevision', { exact: true }) }).locator('dd')).toHaveText(evidence.collectorRevision);
  await expect(page.locator('dl div').filter({ has: page.getByText('Governance-Packrevision', { exact: true }) }).locator('dd')).toHaveText(report.assessment.packSha);
  await expect(page.getByRole('link', { name: 'Zum Finding', exact: false }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Evidence-Details' })).toBeVisible();
  await page.getByRole('link', { name: 'Zum Finding', exact: false }).first().click();
  await expect(page.getByRole('heading', { name: /TEST-1/ })).toBeVisible();
  const forged = `/evidence?${new URLSearchParams({ organization: item.organizationId, evidence: evidence.id, view: 'detail', assessment: item.id, finding: 'wrong' })}`;
  await page.goto(forged);
  await expect(page.getByRole('alert')).toContainText('nicht nachweisbar zugeordnet', { timeout: 15000 });
  await expect(page.getByRole('link', { name: 'Zum Finding', exact: false })).toHaveCount(0);
});

test('unknown and N/A results do not silently resolve a finding', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let status = 'UNKNOWN';
  const finding = { id: 'finding1', productId: 'product1', subjectId: 'subject1', controlId: 'CTRL-1', environment: 'test', status: 'open', snapshotId: 'snapshot1' };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/overview') return route.fulfill({ json: { products: [{ id: 'product1', name: 'Product' }], findings: [finding], packs: [], assessments: [] } });
    if (path === '/api/assessments/snapshot1') return route.fulfill({ json: { assessment: { id: 'snapshot1', organizationId: 'org', productId: 'product1', context: 'baseline', environment: 'test', gitSha: 'a'.repeat(40), packSha: 'b'.repeat(40), pullRequestNumber: null }, findings: [{ id: 'finding1', evaluationId: 'evaluation1', outcome: status, state: 'open', reason: 'No evidence' }], evaluations: [{ id: 'evaluation1', status, reason: 'No evidence', evidenceIds: [], control: { id: 'CTRL-1' }, subject: { id: 'subject1' }, coverage: null }], evidence: [] } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/findings?organization=org&finding=finding1');
  await expect(page.getByRole('heading', { name: /CTRL-1/ })).toBeVisible();
  await expect(page.getByText('Finding finding1 · Status open · test')).toBeVisible();
  await expect(page.getByText('Keine Evidence mit dieser Bewertung verknüpft.')).toBeVisible();
  await expect(page.getByText('UNKNOWN', { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  status = 'NOT_APPLICABLE';
  await page.reload();
  await expect(page.getByText('N/A', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Finding finding1 · Status open · test')).toBeVisible();
});

test('forbidden findings do not expose a trace', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/overview', async (route) => {
    await pending;
    await route.fulfill({ status: 403, body: '{}' });
  });
  await page.goto('/findings?organization=org&finding=foreign');
  await expect(page.getByText(/Finding und Assessment werden geladen/)).toBeVisible();
  release();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Nachvollziehbarkeit und Assessment')).toHaveCount(0);
});
