import { expect, test } from '@playwright/test';

test('missing provider evidence stays UNKNOWN with reason and coverage', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?missing_provider=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  await page.goto(`/overview?organization=${item.organizationId}`);
  const overview = page.getByRole('region', { name: 'Übersicht und Suche' });
  const assessments = overview.locator('.panel').filter({ has: page.getByRole('heading', { name: 'Assessments', exact: true }) });
  await expect(assessments.getByText(/UNKNOWN: 1/)).toBeVisible();
  await assessments.getByRole('link', { name: new RegExp(item.sha.slice(0, 12)) }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe(`/assessments/${item.id}`);
  const status = page.locator('.assessment-status');
  await expect(status).toHaveText('UNKNOWN');
  await expect(status).toHaveClass(/status-unknown/);
  await expect(status).not.toHaveClass(/status-pass/);
  await expect(page.getByText(/Grund: Aktueller Nachweis fehlt oder ist mehrdeutig/)).toBeVisible();
  await expect(page.getByText(/Quellabdeckung: covered/)).toBeVisible();
  await expect(page.getByText('Keine Evidence für diesen Snapshot.')).toBeVisible();
});
