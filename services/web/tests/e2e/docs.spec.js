import { expect, test } from '@playwright/test';

test('documentation categories show runnable examples and limitations', async ({ page }) => {
  await page.goto('/docs#docs/getting-started');
  const docs = page.getByRole('region', { name: 'Dokumentation' });
  const article = docs.getByRole('article', { name: 'Dokumentationsinhalt' });
  for (const [label, command, id] of [
    ['Getting Started', 'start', 'getting-started'], ['Packs', 'packs', 'packs'], ['Evidence', 'evidence', 'evidence'],
    ['Security', 'security', 'security'], ['PR Integration', 'pr', 'pr-integration'],
  ]) {
    await docs.getByRole('link', { name: label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`#docs/${id}$`));
    await expect(article.getByRole('heading', { name: label, exact: true })).toBeVisible();
    await expect(article.getByRole('heading', { name: 'Einschränkungen' })).toBeVisible();
    await expect(article.locator('code').filter({ hasText: `docs_examples.py ${command}` })).toBeVisible();
    await page.reload();
    await expect(article.getByRole('heading', { name: label, exact: true })).toBeVisible();
  }
  await docs.getByRole('link', { name: 'Security', exact: true }).click();
  await page.goBack();
  await expect(article.getByRole('heading', { name: 'PR Integration' })).toBeVisible();
  await page.goto('/docs#docs/unknown');
  await expect(page.getByRole('alert')).toContainText('Anleitung nicht gefunden');
  await docs.getByRole('link', { name: 'Evidence', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(article.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await docs.getByRole('link', { name: 'Getting Started', exact: true }).click();
  const code = article.getByLabel('Codebeispiel, horizontal scrollbar').filter({ hasText: 'docker compose -p specbound-local' });
  expect(await code.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await code.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => code.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
});
