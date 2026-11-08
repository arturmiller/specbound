import { expect, test } from '@playwright/test';

test('discovery and product details show scoped facts and unknown assessment results', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?missing_provider=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  const response = await request.get(`http://127.0.0.1:18762/products/${item.productId}/discovery`);
  expect(response.status()).toBe(200);
  const scans = await response.json();
  const report = await (await request.get(`http://127.0.0.1:18762/assessments/${item.id}`)).json();
  expect(scans).toHaveLength(1);
  expect(scans[0].files).toContain('openapi.json');
  await page.goto(`/products?organization=${item.organizationId}&product=${item.productId}&view=discovery`);
  await expect(page.getByRole('heading', { name: 'Discovery prüfen' })).toBeVisible();
  await expect(page.getByText(/Dateien: openapi.json/)).toBeVisible();
  await expect(page.getByText(`Revision: ${scans[0].sourceRevision}`)).toBeVisible();
  await expect(page.getByText(/UNKNOWN ist weder PASS/)).toBeVisible();
  await page.getByRole('link', { name: 'Produkt ansehen' }).click();
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
  await expect(page.getByText(/repo:/)).toBeVisible();
  const evaluation = page.locator('.product-evaluations li').filter({ hasText: 'TEST-1' });
  await expect(evaluation).toContainText('UNKNOWN');
  await expect(evaluation).toContainText(report.evaluations[0].reason);
  await expect(page.getByRole('link', { name: 'Assessment mit Provenienz öffnen' })).toHaveAttribute('href', `/assessments/${item.id}`);
  await page.reload();
  await expect(evaluation).toContainText('UNKNOWN');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Discovery prüfen' })).toBeVisible();
});

test('missing scans and assessments remain unknown; forbidden scans are not empty', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const team = await request.post(`http://127.0.0.1:18762/organizations/${org}/teams`, { data: { name: 'No scan team' } });
  const product = await request.post(`http://127.0.0.1:18762/organizations/${org}/products`, { data: { name: 'No scan product', ownerTeamId: (await team.json()).id } });
  const item = await product.json();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/products?organization=${org}&product=${item.id}&view=discovery`);
  await expect(page.getByText('Keine Scanbeobachtungen vorhanden. Discovery-Zustand: UNKNOWN.')).toBeVisible();
  await expect(page.getByText('Kein Assessment vorhanden. Bewertung: UNKNOWN.')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Specbound' })).toBeFocused();
  await page.route('**/api/products/*/discovery', (route) => route.fulfill({ status: 403, body: '{}' }));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('fehlen die erforderlichen Rechte');
  await expect(page.getByText('Keine Scanbeobachtungen vorhanden. Discovery-Zustand: UNKNOWN.')).toHaveCount(0);
});
