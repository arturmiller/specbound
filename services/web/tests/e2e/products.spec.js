import { expect, test } from '@playwright/test';

test('creates a product, verifies its repository and reopens details after reload', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const team = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'Produktteam' } });
  expect(team.status()).toBe(201);
  const { id: teamId } = await team.json();
  await page.goto(`/products?organization=${org}`);
  await page.getByRole('link', { name: 'Produkt registrieren' }).click();
  await page.getByLabel('Produktname').fill('Catalog Service');
  await page.getByLabel('Owner-Team').selectOption(teamId);
  await page.getByRole('button', { name: 'Produkt erstellen und weiter' }).click();
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
  await expect(page.getByText('Catalog Service', { exact: true }).first()).toBeVisible();
  await page.getByLabel('Git-Repository').fill('fixture/catalog');
  await page.getByRole('button', { name: 'Repository verbinden' }).click();
  await expect(page.getByText('GitHub-Zugriff bestätigt')).toBeVisible();
  await expect(page.getByText('fixture/catalog', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/product=/);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
  await expect(page.getByText('Catalog Service', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('fixture/catalog', { exact: true })).toBeVisible();
});

test('keeps the product and repository when GitHub verification fails', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const team = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'Fehlerteam' } });
  expect(team.status()).toBe(201);
  const { id: teamId } = await team.json();
  await page.route('**/products/*/repositories/*/github', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto(`/products?organization=${org}`);
  await page.getByRole('link', { name: 'Produkt registrieren' }).click();
  await page.getByLabel('Produktname').fill('Unverified Service');
  await page.getByLabel('Owner-Team').selectOption(teamId);
  await page.getByRole('button', { name: 'Produkt erstellen und weiter' }).click();
  await page.getByLabel('Git-Repository').fill('fixture/unavailable');
  await page.getByRole('button', { name: 'Repository verbinden' }).click();
  await expect(page.getByText(/GitHub-Zugriff konnte nicht bestätigt werden/)).toBeVisible();
  await page.reload();
  await expect(page.getByText('Unverified Service', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('fixture/unavailable', { exact: true })).toBeVisible();
  await page.unroute('**/products/*/repositories/*/github');
  await page.getByRole('button', { name: 'Zugriff prüfen' }).click();
  await expect(page.getByText('GitHub-Zugriff bestätigt')).toBeVisible();
});


test('waits for the selected product repositories before allowing a connection', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const team = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'Ladeteam' } });
  expect(team.status()).toBe(201);
  const { id: teamId } = await team.json();
  await page.goto(`/products?organization=${org}`);
  await page.getByRole('link', { name: 'Produkt registrieren' }).click();
  await page.getByLabel('Produktname').fill('Loading Service');
  await page.getByLabel('Owner-Team').selectOption(teamId);
  let release;
  const waitForRelease = new Promise((resolve) => { release = resolve; });
  let requestStarted;
  const loadingStarted = new Promise((resolve) => { requestStarted = resolve; });
  await page.route('**/products/*/repositories', async (route) => {
    if (route.request().method() === 'GET') {
      requestStarted();
      await waitForRelease;
    }
    await route.continue();
  });
  await page.getByRole('button', { name: 'Produkt erstellen und weiter' }).click();
  await loadingStarted;
  await page.getByLabel('Git-Repository').fill('fixture/loading');
  const connect = page.getByRole('button', { name: 'Repository verbinden' });
  await expect(connect).toBeDisabled();
  release();
  await expect(connect).toBeEnabled();
  await connect.click();
  await expect(page.getByText('fixture/loading', { exact: true })).toBeVisible();
});

test('viewers can browse product sources but cannot create or connect', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:viewer' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 'team', name: 'Platform' }] });
    if (path === '/api/teams/team/members') return route.fulfill({ json: [{ principalId: 'user:viewer', role: 'viewer' }] });
    if (path === '/api/organizations/org/products') return route.fulfill({ json: [{ id: 'product', name: 'Service', ownerTeamId: 'team' }] });
    if (path === '/api/products/product/repositories') return route.fulfill({ json: [{ id: 'repo', provider: 'github', repository: 'owner/service' }] });
    return route.fulfill({ json: {} });
  });
  await page.goto('/products?organization=org');
  await expect(page.getByRole('link', { name: 'Service' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Produkt registrieren' })).toHaveCount(0);
  await page.getByLabel('Produkte suchen').fill('other');
  await expect(page.getByText('Keine Produkte für diese Auswahl.')).toBeVisible();
  await page.getByLabel('Produkte suchen').clear();
  await page.getByRole('link', { name: 'Quellen ansehen' }).click();
  await expect(page.getByText('owner/service')).toBeVisible();
  await expect(page.getByText('Du kannst dieses Produkt nur lesen.')).toBeVisible();
  await expect(page.getByLabel('Git-Repository')).toHaveCount(0);
  await expect(page.getByText('Nicht verfügbar.', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.reload();
  await expect(page.getByText('owner/service')).toBeVisible();
});

test('product loading and forbidden errors do not look like an empty inventory', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { id: 'user:viewer' } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] }));
  await page.route('**/api/organizations/org/teams', (route) => route.fulfill({ json: [] }));
  let release;
  const waiting = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/organizations/org/products', async (route) => { await waiting; await route.fulfill({ status: 403, body: '{}' }); });
  await page.goto('/products?organization=org');
  await expect(page.getByText('Produkte werden geladen …')).toBeVisible();
  release();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Noch keine Produkte vorhanden.')).toHaveCount(0);
});

test('maintainers can only choose teams where they may edit', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/config') return route.fulfill({ json: { enabled: false } });
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user:maintainer' } });
    if (path === '/api/organizations') return route.fulfill({ json: [{ id: 'org', name: 'Org', ownerPrincipalId: 'user:owner' }] });
    if (path === '/api/organizations/org/teams') return route.fulfill({ json: [{ id: 'edit', name: 'Editable' }, { id: 'read', name: 'Read only' }] });
    if (path === '/api/teams/edit/members') return route.fulfill({ json: [{ principalId: 'user:maintainer', role: 'maintainer' }] });
    if (path === '/api/teams/read/members') return route.fulfill({ json: [{ principalId: 'user:maintainer', role: 'viewer' }] });
    if (path === '/api/organizations/org/products') return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
  await page.goto('/products?organization=org');
  await page.getByRole('link', { name: 'Produkt registrieren' }).click();
  const owners = page.getByLabel('Owner-Team');
  await expect(owners.locator('option', { hasText: 'Editable' })).toHaveCount(1);
  await expect(owners.locator('option', { hasText: 'Read only' })).toHaveCount(0);
});
