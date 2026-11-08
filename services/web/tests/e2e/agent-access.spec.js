import { expect, test } from '@playwright/test';

test('issues a one-time credential, reloads its metadata and revokes it', async ({ page, request }) => {
  const orgResponse = await request.post('http://127.0.0.1:18762/organizations', { data: { name: 'Agent access' } });
  expect(orgResponse.status()).toBe(201);
  const org = await orgResponse.json();
  const agentResponse = await request.post(`http://127.0.0.1:18762/organizations/${org.id}/agents`, { data: { name: 'Review bot' } });
  expect(agentResponse.status()).toBe(201);
  const agent = await agentResponse.json();
  await page.route('**/api/organizations/**/agents/**/credentials', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch();
    const data = await response.json();
    data.token = 'sba_fixture_only';
    await route.fulfill({ response, json: data });
  });
  const base = `/agents?${new URLSearchParams({ organization: org.id, agent: agent.id, view: 'scope' })}`;
  await page.goto(base);
  await expect(page.getByRole('heading', { name: 'Agentenrechte und Zugang' })).toBeVisible();
  await expect(page.getByText('Keine Zugänge ausgestellt.')).toBeVisible();
  await page.getByRole('button', { name: 'Zugang ausstellen' }).click();
  await expect(page.getByText('sba_fixture_only')).toBeVisible();
  expect(await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))).not.toContain('sba_fixture_only');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Widerrufen' })).toBeVisible();
  await expect(page.getByText('sba_fixture_only')).toHaveCount(0);
  await page.getByRole('button', { name: 'Widerrufen' }).click();
  await expect(page.getByRole('button', { name: 'Widerrufen' })).toHaveCount(0);
  await expect(page.locator('.agent-credentials li')).toContainText('Widerrufen');
  await page.reload();
  await expect(page.locator('.agent-credentials li')).toContainText('Widerrufen');
  await page.getByRole('link', { name: 'Audit', exact: true }).click();
  await expect(page.getByText('agent.credential.created')).toBeVisible();
  await expect(page.getByText('agent.credential.revoked')).toBeVisible();
  await expect(page.getByText(/Git-Commits, PR-Aktivität/)).toBeVisible();
  await expect(page.getByText('sba_fixture_only')).toHaveCount(0);
});

test('unavailable credential and audit data do not appear empty or remain loading', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:owner' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/agents') return route.fulfill({ json: [{ id: 'agent:one', name: 'Bot', kind: 'agent' }] });
    if (path.endsWith('/credentials') || path.endsWith('/audit-events')) return route.fulfill({ status: 403, body: '{}' });
    return route.fulfill({ json: [] });
  });
  await page.goto('/agents?organization=org&agent=agent%3Aone&view=scope');
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText(/Zugänge werden geladen/)).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Zugang ausstellen' })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.getByRole('link', { name: 'Audit', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText(/Audit wird geladen/)).toHaveCount(0);
  await expect(page.getByText('Keine Audit-Ereignisse für diesen Agenten.')).toHaveCount(0);
});
