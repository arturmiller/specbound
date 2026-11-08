import { expect, test } from '@playwright/test';

test('creates a product, verifies its repository and reopens details after reload', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const team = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'Produktteam' } });
  expect(team.status()).toBe(201);
  const { id: teamId } = await team.json();
  await page.goto(`/?organization=${org}`);
  await page.getByLabel('Produktname').fill('Catalog Service');
  await page.getByLabel('Owner-Team').selectOption(teamId);
  await page.getByRole('button', { name: 'Produkt erstellen' }).click();
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
  await page.goto(`/?organization=${org}`);
  await page.getByLabel('Produktname').fill('Unverified Service');
  await page.getByLabel('Owner-Team').selectOption(teamId);
  await page.getByRole('button', { name: 'Produkt erstellen' }).click();
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
  await page.goto(`/?organization=${org}`);
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
  await page.getByRole('button', { name: 'Produkt erstellen' }).click();
  await loadingStarted;
  await page.getByLabel('Git-Repository').fill('fixture/loading');
  const connect = page.getByRole('button', { name: 'Repository verbinden' });
  await expect(connect).toBeDisabled();
  release();
  await expect(connect).toBeEnabled();
  await connect.click();
  await expect(page.getByText('fixture/loading', { exact: true })).toBeVisible();
});
