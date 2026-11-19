import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';
const primary = ['Produkte', 'Kataloge', 'Profile', 'Evidence Packs'];

test('opens a pinned governance pack in the new portal and exports native manifests', async ({ page }) => {
  const root = `/api/organizations/${org}/packs`;
  const created = await page.request.post(root, { data: { repository: 'fixture/security', tag: 'v1.2.0', kind: 'governance' } });
  expect(created.status()).toBe(201);
  const pack = await created.json();
  expect((await page.request.put(`${root}/${pack.id}/approval`)).ok()).toBe(true);

  await page.goto('/catalogs');
  await page.getByRole('link', { name: 'Archiv der Governance-Packs', exact: true }).click();
  await expect(page).toHaveURL(/catalogs\?view=archive/);
  const nav = page.getByRole('navigation', { name: 'Hauptnavigation' });
  await expect(nav.getByRole('link')).toHaveText(primary);
  await page.locator(`a[href$="pack=${pack.id}"]`).click();
  await expect(page.getByText(/Freigegeben von/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'pack.yaml' })).toHaveAttribute('href', pack.manifestUrl);
  await expect(page.locator('summary', { hasText: 'SEC-NET-001' })).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Mit Prüfbindungen herunterladen', exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('governance-manifeste.zip');

  await page.goto(`/packs?organization=${org}&pack=${pack.id}`);
  await expect(nav.getByRole('link')).toHaveText(primary);
  await expect(page.getByText(/Freigegeben von/)).toBeVisible();
  await expect(page.getByRole('button', { name: /freigeben|zurücknehmen/i })).toHaveCount(0);
});

test('denied pack archives are distinguishable from empty archives', async ({ page }) => {
  await page.route('**/api/auth/config', (route) => route.fulfill({ json: { enabled: false } }));
  await page.route('**/api/organizations', (route) => route.fulfill({ json: [{ id: 'org', name: 'Org' }] }));
  await page.route('**/api/organizations/org/packs', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.goto('/packs?organization=org');
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Keine alten Governance-Packs vorhanden.')).toHaveCount(0);
  await page.unroute('**/api/organizations/org/packs');
  await page.route('**/api/organizations/org/packs', (route) => route.fulfill({ json: [] }));
  await page.reload();
  await expect(page.getByText('Keine alten Governance-Packs vorhanden.')).toBeVisible();
});
