import { expect, test } from '@playwright/test';

const first = { id: 'org-one', name: 'Acme Engineering', ownerPrincipalId: 'user:owner' };
const second = { id: 'org-two', name: 'Second Organization', ownerPrincipalId: 'user:owner' };

async function mockPortal(page, initialOrganizations = []) {
  const organizations = [...initialOrganizations];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data;
    if (path === '/api/healthz') data = { status: 'ok' };
    else if (path === '/api/auth/config') data = { enabled: false };
    else if (path === '/api/auth/me') data = { id: 'user:owner', kind: 'user' };
    else if (path === '/api/organizations' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      data = { ...first, name: body.name };
      organizations.push(data);
    } else if (path === '/api/organizations') data = organizations;
    else if (path.endsWith('/overview')) data = { products: [], packs: [], findings: [], assessments: [] };
    else data = [];
    await route.fulfill({ json: data });
  });
}

test('creates an organization and navigates with stable URLs and browser history', async ({ page }) => {
  await mockPortal(page);
  await page.goto('/settings');
  await expect(page.getByText('Keine Organisationen verfügbar.')).toBeVisible();
  await page.getByLabel('Organisationsname').fill(first.name);
  await page.getByRole('button', { name: 'Organisation erstellen' }).click();
  await expect(page.getByRole('combobox', { name: 'Organisation' })).toHaveValue(first.id);
  await expect(page.getByRole('heading', { name: first.name })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Hauptnavigation' });
  await nav.getByRole('link', { name: 'Teams', exact: true }).click();
  await expect(page).toHaveURL(/\/teams\?organization=org-one/);
  await expect(nav.getByRole('link', { name: 'Teams', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Workspace-Einstellungen' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Organisation' })).toHaveValue(first.id);
  await page.goto('/agents?organization=org-one');
  await expect(page.getByRole('heading', { name: 'Agentenidentitäten' })).toBeVisible();
});

test('organization switch clears selections from the previous organization', async ({ page }) => {
  await mockPortal(page, [first, second]);
  await page.goto('/teams?organization=org-one&team=team-old&product=product-old&pack=pack-old&agent=agent-old');
  await expect(page.getByRole('combobox', { name: 'Organisation' })).toHaveValue(first.id);
  await page.getByRole('combobox', { name: 'Organisation' }).selectOption(second.id);
  await expect(page).toHaveURL(/organization=org-two/);
  await expect(page).not.toHaveURL(/team=|product=|pack=|agent=/);
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Organisation' })).toHaveValue(second.id);
});

test('a forbidden organization response is visible and does not show an onboarding form', async ({ page }) => {
  await mockPortal(page);
  await page.route('**/api/organizations', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.goto('/settings?organization=foreign');
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByLabel('Organisationsname')).toHaveCount(0);
});

test('the portal stays usable at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockPortal(page, [first]);
  await page.goto('/settings?organization=org-one');
  await expect(page.getByRole('heading', { name: 'Workspace-Einstellungen' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.getByRole('navigation', { name: 'Hauptnavigation' }).getByRole('link', { name: 'Teams', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Teams', exact: true })).toBeVisible();
});
