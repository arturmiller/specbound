import { expect, test } from '@playwright/test';

test('creates a team and member and shows them after reload', async ({ page, request }) => {
  const organization = await request.post('http://127.0.0.1:18762/organizations', {
    data: { name: 'E2E organization' },
  });
  expect(organization.status()).toBe(201);
  const { id } = await organization.json();
  await page.goto(`/teams?organization=${encodeURIComponent(id)}`);
  await expect(page.getByLabel('Organisation')).toHaveValue(id);
  await page.getByRole('link', { name: 'Team erstellen' }).click();
  await page.getByLabel('Teamname').fill('Platform Team');
  await page.getByRole('button', { name: 'Team erstellen und weiter' }).click();
  await expect(page.getByRole('heading', { name: 'Mitglieder & Rollen' })).toBeVisible();
  await page.getByLabel('Principal-ID').fill('user:alice');
  await page.getByLabel('Rolle', { exact: true }).selectOption('viewer');
  await page.getByRole('button', { name: 'Mitglied hinzufügen' }).click();
  await expect(page.getByText('user:alice', { exact: true })).toBeVisible();
  await page.getByLabel('Rolle von user:alice').selectOption('maintainer');
  await page.reload();
  await expect(page.getByText('user:alice', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Rolle von user:alice')).toHaveValue('maintainer');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Entfernen: user:alice' }).click();
  await expect(page.getByText('Noch keine Mitglieder vorhanden.')).toBeVisible();
  const teamId = new URL(page.url()).searchParams.get('team');
  const product = await request.post(`http://127.0.0.1:18762/organizations/${id}/products`, { data: { name: 'Owned product', ownerTeamId: teamId } });
  expect(product.status()).toBe(201);
  await page.getByRole('link', { name: 'Team ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Platform Team' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Owned product' })).toBeVisible();
  await page.getByRole('link', { name: 'Alle Teams' }).click();
  await expect(page.getByRole('link', { name: 'Platform Team' })).toBeVisible();
});

test('viewers have no writing actions and can use the mobile layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:viewer', kind: 'user' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Organization', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 'team', name: 'Platform' }] });
    if (path === '/api/organizations/org/products') return route.fulfill({ json: [] });
    if (path === '/api/teams/team/members') return route.fulfill({ json: [{ id: 'member', principalId: 'user:viewer', role: 'viewer' }] });
    return route.fulfill({ json: {} });
  });
  await page.goto('/teams?organization=org&team=team&view=members');
  await expect(page.getByText('user:viewer')).toBeVisible();
  await expect(page.getByRole('button', { name: /hinzufügen|entfernen/i })).toHaveCount(0);
  await expect(page.getByLabel('Rolle von user:viewer')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.getByRole('link', { name: 'Teamdetails' }).click();
  await page.getByRole('link', { name: 'Alle Teams' }).click();
  await expect(page.getByRole('link', { name: 'Team erstellen' })).toHaveCount(0);
});

test('team permission failures and loading state are visible', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { id: 'user:viewer' } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Organization', ownerPrincipalId: 'user:owner' }] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/teams', async (route) => { await waiting; await route.fulfill({ status: 403, body: '{}' }); });
  await page.goto('/teams?organization=org');
  await expect(page.getByText('Teams werden geladen …')).toBeVisible();
  release();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Noch keine Teams vorhanden.')).toHaveCount(0);
});

test('team admins can manage members without creating organization teams', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:admin' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Organization', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 'team', name: 'Platform' }] });
    if (path === '/api/organizations/org/products') return route.fulfill({ json: [] });
    if (path === '/api/teams/team/members') return route.fulfill({ json: [{ id: 'member', principalId: 'user:admin', role: 'admin' }] });
    return route.fulfill({ json: {} });
  });
  await page.goto('/teams?organization=org&team=team&view=members');
  await expect(page.getByLabel('Principal-ID')).toBeVisible();
  await expect(page.getByLabel('Rolle von user:admin')).toBeVisible();
  await page.getByRole('link', { name: 'Teamdetails' }).click();
  await page.getByRole('link', { name: 'Alle Teams' }).click();
  await expect(page.getByRole('link', { name: 'Team erstellen' })).toHaveCount(0);
});

test('explains that sign-in is required when the API denies access', async ({ page }) => {
  await page.route('**/api/organizations', (route) => route.fulfill({ status: 401, body: '{}' }));
  await page.goto('/');
  await expect(page.getByText(/Anmeldung erforderlich/)).toBeVisible();
});

test('agent membership shows its read-only and approval limits', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const teamResponse = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'Agent team' } });
  expect(teamResponse.status()).toBe(201);
  const team = await teamResponse.json();
  const agentResponse = await request.post(`http://127.0.0.1:18762/organizations/${org}/agents`, { data: { name: 'Read agent' } });
  expect(agentResponse.status()).toBe(201);
  const agent = await agentResponse.json();
  const membership = await request.post(`http://127.0.0.1:18762/teams/${team.id}/members`, { data: { principalId: agent.id, role: 'viewer' } });
  expect(membership.status()).toBe(201);
  await page.goto(`/teams?organization=${org}&team=${team.id}`);
  await expect(page.getByText(agent.id, { exact: true })).toBeVisible();
  await expect(page.getByText('Agent: Lesen; keine Pack-Freigabe')).toBeVisible();
});
