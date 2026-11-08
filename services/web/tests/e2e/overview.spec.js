import { expect, test } from '@playwright/test';

test('search and filters lead from actual findings to the exact report and product', async ({ page, request }) => {
  const seeded = await request.post('http://127.0.0.1:18762/__e2e/assessment?failing=true');
  expect(seeded.status()).toBe(200);
  const item = await seeded.json();
  await page.goto(`/overview?organization=${item.organizationId}`);
  const overview = page.getByRole('region', { name: 'Übersicht und Suche' });
  await expect(overview.getByRole('link', { name: /TEST-1/ })).toHaveAttribute('href', `/assessments/${item.id}`);
  await overview.getByLabel('Teamfilter').selectOption(item.teamId);
  await overview.getByLabel('Scope').selectOption('test');
  await overview.getByLabel('Suche').fill('TEST-1');
  await expect(overview.getByRole('link', { name: /TEST-1/ })).toBeVisible();
  await expect(overview.getByText('Keine passenden Produkte.')).toBeVisible();
  await overview.getByRole('link', { name: /TEST-1/ }).click();
  await expect(page).toHaveURL(new RegExp(`/assessments/${item.id}$`));
  await expect(page.getByText(item.id, { exact: true })).toBeVisible();
  await page.goto(`/overview?organization=${item.organizationId}`);
  await page.getByRole('region', { name: 'Übersicht und Suche' }).getByRole('link', { name: 'Product' }).click();
  await expect(page).toHaveURL(new RegExp(`product=${item.productId}`));
  await expect(page.getByRole('heading', { name: 'Produktdetails' })).toBeVisible();
});

test('a pack result opens the actual selected pack revision', async ({ page, request }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const response = await request.post(`http://127.0.0.1:18762/organizations/${org}/packs`, {
    data: { repository: 'fixture/overview-pack', tag: 'v1.2.0', kind: 'governance' },
  });
  expect(response.status()).toBe(201);
  const pack = await response.json();
  await page.goto(`/overview?organization=${org}`);
  const overview = page.getByRole('region', { name: 'Übersicht und Suche' });
  await overview.getByLabel('Suche').fill('overview-pack');
  await overview.getByRole('link', { name: /v1.2.0/ }).click();
  await expect(page).toHaveURL(new RegExp(`pack=${pack.id}`));
  const detail = page.locator('.panel').filter({ has: page.getByRole('heading', { name: 'Pack-Details' }) });
  await expect(detail.getByText('Repository: fixture/overview-pack')).toBeVisible();
});
