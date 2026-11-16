import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('registers two manifest paths from the same branch through the persisted API', async ({ page }) => {
  const saved = [];
  for (const folder of ['example', 'second']) {
    await page.goto(`/providers?organization=${org}&view=connect`);
    await page.getByLabel('Repository', { exact: true }).fill('fixture/multi-providers');
    await page.getByLabel('Ref-Typ').selectOption('branch');
    await page.getByLabel('Git-Ref', { exact: true }).fill('main');
    await page.getByLabel('Manifestpfad').fill(`evidence/${folder}/provider.json`);
    await page.getByRole('button', { name: 'Provider-Pack verbinden' }).click();
    await expect(page.getByRole('heading', { name: 'Provider-Manifest', exact: true })).toBeVisible();
    const link = page.getByRole('link', { name: `evidence/${folder}/provider.json`, exact: true });
    await expect(link).toHaveAttribute('href', `https://github.com/fixture/multi-providers/blob/${'a'.repeat(40)}/evidence/${folder}/provider.json`);
    await expect(page.getByRole('link', { name: 'Schema ansehen' })).toHaveAttribute('href', '/api/contracts/provider-pack');
    saved.push(page.url());
    await page.reload();
    await expect(link).toBeVisible();
  }
  expect(saved[0]).not.toEqual(saved[1]);
  await page.goto(`/providers?organization=${org}&view=catalog`);
  for (const id of ['org.specbound.example-auth', 'org.specbound.example-license']) {
    await expect(page.getByText(id, { exact: true })).toBeVisible();
  }
});
