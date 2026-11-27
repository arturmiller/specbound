import { expect, test } from '@playwright/test';

test('the assessment link opens its exact revision and provenance', async ({ page, request }) => {
  const response = await request.post('http://127.0.0.1:18762/__e2e/assessment');
  expect(response.status()).toBe(200);
  const { id, sha } = await response.json();
  await page.goto(`/assessments/${id}`);
  await expect(page.getByRole('heading', { name: 'Prüfung bestanden' })).toBeVisible();
  await expect(page.getByText(id, { exact: true })).toHaveCount(0);
  await expect(page.getByText(sha, { exact: true })).toBeHidden();
  await page.getByText('Technische Details', { exact: true }).click();
  await expect(page.getByText(sha, { exact: true })).toBeVisible();
  await page.getByText('Weitere Einzelbewertungen (1)', { exact: true }).click();
  await page.locator('.assessment-item > summary').click();
  await page.getByText('Prüfregel und technische Herkunft').click();
  await expect(page.getByText(/Quellverweis: repo:/)).toBeVisible();
  const evidenceLink = page.getByRole('link', { name: 'Nachweis öffnen' });
  await expect(evidenceLink).toHaveAttribute('href', /\/evidence\?organization=.+&evidence=.+&view=detail/);
  await evidenceLink.click();
  await expect(page.getByText(/publicly_reachable/).last()).toBeVisible();
});
