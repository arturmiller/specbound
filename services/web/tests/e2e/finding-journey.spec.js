import { expect, test } from '@playwright/test';

test('a persisted finding leads to its exact assessment and recorded history', async ({ page, request }) => {
  const response = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(response.status()).toBe(200);
  const item = await response.json();
  const overview = await (await request.get(`http://127.0.0.1:18762/organizations/${item.organizationId}/overview`)).json();
  const finding = overview.findings.find((entry) => entry.snapshotId === item.id);
  const history = await (await request.get(`http://127.0.0.1:18762/organizations/${item.organizationId}/findings/${finding.id}/history`)).json();
  expect(history.history.map((entry) => entry.snapshotId)).toEqual([item.id]);
  await page.goto(`/findings?${new URLSearchParams({ organization: item.organizationId, finding: finding.id })}`);
  await page.getByRole('link', { name: 'Lösungsweg ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Lösungsweg betrachten' })).toBeVisible();
  await expect(page.locator('dl div').filter({ has: page.getByText('Produktteam', { exact: true }) }).locator('dd')).toHaveText('Team');
  await expect(page.getByRole('link', { name: 'Versionsgenauen Bericht öffnen' })).toHaveAttribute('href', `/assessments/${item.id}`);
  await expect(page.getByText('FAIL · Finding open')).toBeVisible();
  await expect(page.getByText(/Git-Diff und ein manueller Recheck sind hier nicht verfügbar/)).toBeVisible();
  await page.getByRole('link', { name: 'Verlauf ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Finding-Verlauf' })).toBeVisible();
  await expect(page.getByText('Nicht nachgewiesen')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Assessment öffnen' }).first()).toHaveAttribute('href', `/assessments/${item.id}`);
  await page.reload();
  await expect(page.getByText('FAIL · Finding open')).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Lösungsweg betrachten' })).toBeVisible();
});

test('history keeps UNKNOWN open and distinguishes a later PASS from Git status', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const finding = { id: 'finding1', productId: 'product1', subjectId: 'subject1', controlId: 'CTRL-1', environment: 'test', status: 'resolved', snapshotId: 'snapshot3' };
  const events = [
    { id: 'event1', snapshotId: 'snapshot1', outcome: 'FAIL', stateAfter: 'open', reason: 'Failed', observedAt: '2026-01-01T00:00:00Z', gitSha: 'a'.repeat(40), packSha: 'd'.repeat(40) },
    { id: 'event2', snapshotId: 'snapshot2', outcome: 'UNKNOWN', stateAfter: 'open', reason: 'No evidence', observedAt: '2026-01-02T00:00:00Z', gitSha: 'b'.repeat(40), packSha: 'd'.repeat(40) },
    { id: 'event3', snapshotId: 'snapshot3', outcome: 'PASS', stateAfter: 'resolved', reason: 'Passed', observedAt: '2026-01-03T00:00:00Z', gitSha: 'c'.repeat(40), packSha: 'd'.repeat(40) },
  ];
  let mode = 'pending';
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/overview') return route.fulfill({ json: { products: [{ id: 'product1', name: 'Product', teamId: 'team1' }], findings: [finding], packs: [], assessments: [] } });
    if (path === '/api/assessments/snapshot3') return route.fulfill({ json: { assessment: { id: 'snapshot3', organizationId: 'org', productId: 'product1', context: 'baseline', environment: 'test', gitSha: 'c'.repeat(40), packSha: 'd'.repeat(40), pullRequestNumber: null }, findings: [{ id: 'finding1', evaluationId: 'evaluation3', outcome: 'PASS', state: 'resolved', reason: 'Passed' }], evaluations: [{ id: 'evaluation3', status: 'PASS', reason: 'Passed', evidenceIds: [], control: { id: 'CTRL-1' }, subject: { id: 'subject1' }, coverage: null }], evidence: [] } });
    if (path === '/api/organizations/org/findings/finding1/history') {
      if (mode === 'forbidden') return route.fulfill({ status: 403, body: '{}' });
      if (mode === 'pending') await pending;
      return route.fulfill({ json: { finding: { ...finding, organizationId: 'org', lastSnapshotId: mode === 'stale' ? 'old' : 'snapshot3' }, history: mode === 'empty' ? [] : events } });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto('/findings?organization=org&finding=finding1&view=resolution');
  await expect(page.getByText('Finding-Verlauf wird geladen …')).toBeVisible();
  mode = 'ok';
  release();
  await expect(page.getByText('UNKNOWN · Finding open')).toBeVisible();
  await expect(page.getByText('PASS · Finding resolved')).toBeVisible();
  await expect(page.getByText('Nicht nachgewiesen')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Assessment öffnen' }).nth(1)).toHaveAttribute('href', '/assessments/snapshot1');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  mode = 'empty';
  await page.reload();
  await expect(page.getByText('Keine Ereignisse für dieses Finding gespeichert.')).toBeVisible();
  mode = 'stale';
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Bitte neu laden');
  await expect(page.getByText('PASS · Finding resolved')).toHaveCount(0);
  mode = 'forbidden';
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Keine Ereignisse für dieses Finding gespeichert.')).toHaveCount(0);
});
