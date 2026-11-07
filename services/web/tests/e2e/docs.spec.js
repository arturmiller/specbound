import { expect, test } from '@playwright/test';

test('documentation categories show runnable examples and limitations', async ({ page }) => {
  await page.goto('/#docs/getting-started');
  const docs = page.getByRole('region', { name: 'Dokumentation' });
  const article = docs.getByRole('article', { name: 'Dokumentationsinhalt' });
  for (const [label, command] of [
    ['Getting Started', 'start'], ['Packs', 'packs'], ['Evidence', 'evidence'],
    ['Security', 'security'], ['PR Integration', 'pr'],
  ]) {
    await docs.getByRole('link', { name: label, exact: true }).click();
    await expect(article.getByRole('heading', { name: label, exact: true })).toBeVisible();
    await expect(article.getByRole('heading', { name: 'Einschränkungen' })).toBeVisible();
    await expect(article.locator('code').filter({ hasText: `docs_examples.py ${command}` })).toBeVisible();
  }
  await page.reload();
  await expect(article.getByRole('heading', { name: 'PR Integration' })).toBeVisible();
});
