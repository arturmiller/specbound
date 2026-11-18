import { expect, test } from '@playwright/test';

test('workspace errors never fall back to a browser-selected or first organization', async ({ page }) => {
  const requested = [];
  page.on('request', (request) => requested.push(new URL(request.url()).pathname));
  for (const status of [503, 403]) {
    await page.route('**/api/workspace', (route) => route.fulfill({ status, json: { detail: 'Unavailable' } }));
    await page.goto('/?organization=foreign&product=foreign');
    await expect(page.getByRole('heading', { name: 'Arbeitsbereich nicht verfügbar' })).toBeVisible();
    await expect(page.getByRole('alert')).toContainText(status === 403 ? 'Rechte' : 'nicht konfiguriert');
    await expect(page.getByRole('combobox', { name: 'Produkt auswählen' })).toHaveCount(0);
    await page.unroute('**/api/workspace');
  }
  expect(requested.some((path) => path === '/api/organizations' || path.includes('/organizations/foreign'))).toBe(false);
});
