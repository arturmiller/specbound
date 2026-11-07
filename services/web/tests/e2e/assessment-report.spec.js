import { expect, test } from '@playwright/test';

test('the assessment link opens its exact revision and provenance', async ({ page, request }) => {
  const response = await request.post('http://127.0.0.1:18762/__e2e/assessment');
  expect(response.status()).toBe(200);
  const { id, sha } = await response.json();
  await page.goto(`/assessments/${id}`);
  await expect(page.getByRole('heading', { name: 'Assessment-Bericht' })).toBeVisible();
  await expect(page.getByText(id, { exact: true })).toBeVisible();
  await expect(page.getByText(sha, { exact: true })).toBeVisible();
  await expect(page.getByText(/Quellverweis: repo:/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Evidence und Fakten' })).toBeVisible();
  await expect(page.getByText(/publicly_reachable/).last()).toBeVisible();
});
