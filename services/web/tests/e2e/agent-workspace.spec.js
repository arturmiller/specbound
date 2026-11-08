import { expect, test } from '@playwright/test';

test('registers an agent and assigns viewer memberships that survive reload', async ({ page, request }) => {
  const orgResponse = await request.post('http://127.0.0.1:18762/organizations', { data: { name: 'Agent Workspace' } });
  expect(orgResponse.status()).toBe(201);
  const org = await orgResponse.json();
  for (const name of ['Platform', 'Billing']) {
    const response = await request.post(`http://127.0.0.1:18762/organizations/${org.id}/teams`, { data: { name } });
    expect(response.status()).toBe(201);
  }
  await page.goto(`/agents?organization=${org.id}`);
  await expect(page.getByText('Keine Agenten registriert.')).toBeVisible();
  await page.getByRole('link', { name: '+ Agent registrieren' }).click();
  await page.getByLabel('Anzeigename').fill('Review bot');
  await page.getByRole('button', { name: 'Agent anlegen und Teams zuordnen' }).click();
  await expect(page.getByRole('heading', { name: 'Agent einem Team zuordnen' })).toBeVisible();
  const rows = page.locator('.agent-team-list li');
  await rows.filter({ hasText: 'Platform' }).getByRole('button', { name: 'Als Viewer hinzufügen' }).click();
  await rows.filter({ hasText: 'Billing' }).getByRole('button', { name: 'Als Viewer hinzufügen' }).click();
  await expect(rows.filter({ hasText: 'Platform' })).toContainText('viewer');
  await page.reload();
  await expect(rows.filter({ hasText: 'Billing' })).toContainText('viewer');
  await page.getByRole('link', { name: 'Zur Agentenliste' }).click();
  const agentRow = page.getByRole('row').filter({ hasText: 'Review bot' });
  await expect(agentRow).toContainText('Platform');
  await expect(agentRow).toContainText('Billing');
  await expect(agentRow).toContainText('Nicht hinterlegt');
  await agentRow.getByRole('link', { name: 'Review bot' }).click();
  await expect(page.getByText(/Teammitgliedschaft allein/)).toBeVisible();
});

test('loading, forbidden access and missing membership data are explicit on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:owner' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 'team', name: 'Platform' }] });
    if (path === '/api/teams/team/members') return route.fulfill({ status: 403, body: '{}' });
    if (path === '/api/organizations/org/agents') { await pending; return route.fulfill({ json: [{ id: 'agent:one', name: 'Bot', kind: 'agent' }] }); }
    return route.fulfill({ json: [] });
  });
  await page.goto('/agents?organization=org');
  await expect(page.getByText(/Agenten werden geladen/)).toBeVisible();
  release();
  await expect(page.getByRole('heading', { name: 'Agentenidentitäten' })).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: 'Bot' })).toContainText('Nicht vollständig verfügbar');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.getByRole('link', { name: 'Bot' }).click();
  await expect(page.getByText('Mitgliedschaft nicht verfügbar')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Als Viewer hinzufügen' })).toHaveCount(0);
  await page.route('**/api/organizations/org/agents', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.goto('/agents?organization=org');
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByRole('link', { name: '+ Agent registrieren' })).toHaveCount(0);
});
