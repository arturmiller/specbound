import { expect, test } from '@playwright/test';

test('stored PR finding leads to its exact assessment and back to the inbox', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  const data = await (await request.get(`http://127.0.0.1:18762/organizations/${item.organizationId}/overview`)).json();
  const finding = data.findings.find((entry) => entry.snapshotId === item.id);
  const assessment = data.assessments.find((entry) => entry.id === item.id);
  expect(finding.context).toBe('pull_request');
  expect(finding.pullRequestNumber).toBe(17);
  await page.goto(`/findings?organization=${item.organizationId}`);
  const row = page.getByRole('row').filter({ hasText: 'TEST-1' });
  await expect(row).toContainText('PR #17');
  await expect(row).toContainText(assessment.gitSha);
  await page.getByRole('combobox', { name: 'Team', exact: true }).selectOption(item.teamId);
  await page.getByRole('searchbox', { name: 'Suche' }).fill('TEST-1');
  await expect(row).toBeVisible();
  await row.getByRole('link').click();
  await expect(page.getByRole('link', { name: 'Assessment-Bericht öffnen' })).toHaveAttribute('href', `/assessments/${item.id}`);
  await page.getByRole('link', { name: 'Zur Finding-Inbox' }).click();
  await expect(page.getByRole('heading', { name: 'Finding-Inbox' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('row').filter({ hasText: 'TEST-1' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('link', { name: 'Assessment-Bericht öffnen' })).toBeVisible();
});

const data = {
  products: [{ id: 'p1', name: 'Alpha', teamId: 't1' }, { id: 'p2', name: 'Beta', teamId: 't2' }],
  findings: [
    { id: 'f1', productId: 'p1', subjectId: 's1', controlId: 'CTL-1', environment: 'test', status: 'open', snapshotId: 'a1', context: 'pull_request', pullRequestNumber: 17 },
    { id: 'f2', productId: 'p2', subjectId: 's2', controlId: 'CTL-2', environment: 'prod', status: 'resolved', snapshotId: 'a2', context: 'pull_request', pullRequestNumber: 18 },
    { id: 'f3', productId: 'p1', subjectId: 's3', controlId: 'BASELINE', environment: 'prod', status: 'open', snapshotId: 'a3', context: 'baseline', pullRequestNumber: null },
  ],
  assessments: [
    { id: 'a1', productId: 'p1', context: 'pull_request', environment: 'test', pullRequestNumber: 17, gitSha: 'a'.repeat(40) },
    { id: 'a2', productId: 'p1', context: 'pull_request', environment: 'prod', pullRequestNumber: 18, gitSha: 'b'.repeat(40) },
  ],
};

async function mockPortal(page, overview = data, teamStatus = 200) {
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill(teamStatus === 200 ? { json: [{ id: 't1', name: 'Team A' }, { id: 't2', name: 'Team B' }] } : { status: teamStatus, body: '{}' });
    if (path === '/api/organizations/org/overview') return route.fulfill({ json: overview });
    return route.fulfill({ json: [] });
  });
}

test('filters PR data without attributing baseline findings or another product revision', async ({ page }) => {
  await mockPortal(page);
  await page.goto('/findings?organization=org');
  await expect(page.getByRole('row').filter({ hasText: 'CTL-1' })).toContainText('a'.repeat(40));
  const row = page.getByRole('row').filter({ hasText: 'CTL-2' });
  await expect(row).toContainText('Revision nicht verfügbar');
  await expect(row).not.toContainText('b'.repeat(40));
  await expect(page.getByText('BASELINE', { exact: true })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('resolved');
  await expect(page.getByRole('row').filter({ hasText: 'CTL-1' })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Team', exact: true }).selectOption('t1');
  await expect(page.getByText('Keine PR-Findings für diese Filter.')).toBeVisible();
  await page.getByRole('combobox', { name: 'Herkunft' }).selectOption('baseline');
  await expect(page.getByText('Baseline-Findings und ihre Triage sind in dieser Ansicht noch nicht verfügbar.')).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: 'CTL-2' })).toHaveCount(0);
});

test('planned views remain honest and support navigation on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPortal(page);
  await page.goto('/findings?organization=org');
  await expect(page.getByRole('heading', { name: 'Finding-Inbox' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const scroll = page.getByLabel('Findings, horizontal scrollbar');
  await scroll.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => scroll.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.getByRole('link', { name: 'Baseline-Triage', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Baseline-Triage' })).toBeVisible();
  await expect(page.getByText('UNKNOWN').first()).toBeVisible();
  await expect(page.getByRole('link', { name: '#65' })).toHaveAttribute('href', /\/issues\/65$/);
  await page.reload();
  await page.getByRole('link', { name: 'Baseline-Abschluss', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Baseline-Abschluss' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Baseline-Triage' })).toBeVisible();
});

test('empty and inaccessible data and unavailable team filter are distinct', async ({ page }) => {
  await mockPortal(page, { products: [], findings: [], assessments: [] }, 503);
  await page.goto('/findings?organization=org');
  await expect(page.getByText('Keine sichtbaren PR-Findings gespeichert.')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Teamfilter nicht verfügbar');
  await expect(page.getByRole('combobox', { name: 'Team', exact: true })).toBeDisabled();
  await page.route('**/api/organizations/org/overview', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Keine sichtbaren PR-Findings gespeichert.')).toHaveCount(0);
});

test('loading is visible until the overview arrives', async ({ page }) => {
  await mockPortal(page);
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/overview', async (route) => {
    await waiting;
    await route.fulfill({ json: { products: [], findings: [], assessments: [] } });
  });
  await page.goto('/findings?organization=org');
  await expect(page.getByRole('status').filter({ hasText: 'Findings werden geladen' })).toBeVisible();
  release();
  await expect(page.getByText('Keine sichtbaren PR-Findings gespeichert.')).toBeVisible();
});
