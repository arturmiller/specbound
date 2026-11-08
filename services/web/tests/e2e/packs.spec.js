import { expect, test } from '@playwright/test';

test('connects a fixture pack and shows validated controls and pinned provenance', async ({ page }) => {
  await page.goto('/?organization=123e4567-e89b-12d3-a456-426614174000');
  await expect(page.getByRole('heading', { name: 'Pack-Katalog' })).toBeVisible();
  await page.getByLabel('Repository', { exact: true }).fill('fixture/security');
  await page.getByLabel('Release-Tag').fill('v1.2.0');
  await page.getByRole('button', { name: 'Pack verbinden' }).click();
  await expect(page.getByText('SEC-NET-001')).toBeVisible();
  await expect(page.getByText('Commit:')).toContainText('a'.repeat(40));
  await expect(page.getByText('Repository: fixture/security')).toBeVisible();
  await expect(page.getByText('Tag: v1.2.0')).toBeVisible();
  await expect(page.getByText(/Agenten haben kein Freigaberecht/)).toBeVisible();
  await expect(page.getByText('Freigabestatus: Nicht freigegeben')).toBeVisible();
  await page.getByRole('button', { name: 'Governance-Pack freigeben' }).click();
  await expect(page.getByText(/Freigabestatus: Freigegeben von/)).toBeVisible();
  await expect(page.getByLabel(/branch/i)).toHaveCount(0);
  await page.reload();
  await expect(page.getByText('SEC-NET-001')).toBeVisible();
  await expect(page.getByText('Commit:')).toContainText('a'.repeat(40));
  await expect(page.getByText(/Freigabestatus: Freigegeben von/)).toBeVisible();
  await page.getByRole('button', { name: 'Freigabe zurücknehmen' }).click();
  await expect(page.getByText('Freigabestatus: Nicht freigegeben')).toBeVisible();
});
