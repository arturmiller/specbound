import { expect, test } from '@playwright/test';

test('creates a team and member and shows them after reload', async ({ page, request }) => {
  const organization = await request.post('http://127.0.0.1:18762/organizations', {
    data: { name: 'E2E organization' },
  });
  expect(organization.status()).toBe(201);
  const { id } = await organization.json();
  await page.goto(`/?organization=${encodeURIComponent(id)}`);
  await expect(page.getByLabel('Organisation')).toHaveValue(id);
  await page.getByLabel('Teamname').fill('Platform Team');
  await page.getByRole('button', { name: 'Team erstellen' }).click();
  await expect(page.getByRole('button', { name: 'Platform Team' })).toBeVisible();
  await page.getByLabel('Principal-ID').fill('user:alice');
  await page.getByLabel('Rolle').selectOption('viewer');
  await page.getByRole('button', { name: 'Mitglied hinzufügen' }).click();
  await expect(page.getByText('user:alice', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Platform Team' })).toBeVisible();
  await expect(page.getByText('user:alice', { exact: true })).toBeVisible();
});

test('explains that sign-in is required when the API denies access', async ({ page }) => {
  await page.route('**/api/organizations', (route) => route.fulfill({ status: 401, body: '{}' }));
  await page.goto('/');
  await expect(page.getByText(/Anmeldung erforderlich/)).toBeVisible();
});
