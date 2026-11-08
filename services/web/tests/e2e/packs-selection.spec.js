import { expect, test } from '@playwright/test';

test('retains the selected pack and its approval when the page reloads', async ({ page }) => {
  const org = '123e4567-e89b-12d3-a456-426614174000';
  const pack = (id) => ({
    id, repository: `fixture/${id}`, tag: 'v1.0.0', commit: 'a'.repeat(40), kind: 'governance',
    manifest: { metadata: { id, version: '1.0.0' } }, controls: [], capabilities: [],
  });
  const packs = [pack('first'), pack('second')];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data;
    if (path === '/api/healthz') data = { status: 'ok' };
    else if (path === '/api/auth/config') data = { enabled: false };
    else if (path === '/api/organizations') data = [{ id: org, name: 'Fixture Organization' }];
    else if (path === `/api/organizations/${org}/packs`) {
      if (route.request().method() === 'POST') { data = pack('third'); packs.push(data); }
      else data = packs;
    }
    else if (path === `/api/organizations/${org}/packs/first/approval`) data = { revisionId: 'first', approved: false, approvedBy: null };
    else if (path === `/api/organizations/${org}/packs/second/approval`) data = { revisionId: 'second', approved: true, approvedBy: 'user:fixture' };
    else if (path === `/api/organizations/${org}/packs/third/approval`) data = { revisionId: 'third', approved: false, approvedBy: null };
    else if (path.endsWith('/overview')) data = { products: [], packs: [], findings: [], assessments: [] };
    else data = [];
    await route.fulfill({ json: data });
  });

  await page.goto(`/?organization=${org}`);
  await page.getByRole('button', { name: 'second · v1.0.0' }).click();
  await expect(page).toHaveURL(/pack=second/);
  await expect(page.getByText('Freigabestatus: Freigegeben von user:fixture')).toBeVisible();
  await page.goto(page.url());
  await expect(page.getByRole('button', { name: 'second · v1.0.0' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Freigabestatus: Freigegeben von user:fixture')).toBeVisible();

  await page.getByLabel('Repository', { exact: true }).fill('fixture/third');
  await page.getByLabel('Release-Tag').fill('v1.0.0');
  await page.getByRole('button', { name: 'Pack verbinden' }).click();
  await expect(page.getByRole('button', { name: 'third · v1.0.0' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/pack=third/);
  await page.reload();
  await expect(page.getByRole('button', { name: 'third · v1.0.0' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Freigabestatus: Nicht freigegeben')).toBeVisible();
});
