import { expect, test } from '@playwright/test';

const org = '123e4567-e89b-12d3-a456-426614174000';

test('shows all fourteen package evaluations and evidence on controls with stable selection and focus', async ({ page }) => {
  await page.goto(`/products?organization=${org}`);
  let productId;
  for (const [resourceType, manifestPath, id] of [
    ['Catalog', 'catalogs/application.json', 'application-controls'],
    ['Profile', 'profiles/application-baseline.json', 'application-baseline'],
    ['Product', 'products/audio-visualizer.json', 'audio-visualizer'],
  ]) {
    const response = await page.request.post(`/api/organizations/${org}/resources`, { data: {
      apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id: 'source', version: '1.0.0', name: 'Source' },
      spec: { resourceType, provider: 'github', repository: 'fixture/oscal', ref: 'main', manifestPath, expected: { id, version: '1.0.0' } },
    } });
    expect(response.status()).toBe(201);
    if (resourceType === 'Product') productId = (await response.json()).resolved.productId;
  }
  await page.goto(`/products?organization=${org}&product=${productId}&view=scans`);
  const scan = page.getByRole('region', { name: 'Lizenzscan für djfun/audio-visualizer-python' });
  await expect(scan.getByRole('button', { name: 'Öffentlichen Lizenzscan starten' })).toBeEnabled();
  await scan.getByRole('button', { name: 'Öffentlichen Lizenzscan starten' }).click();
  await expect(scan.getByText('Wartet auf den lokalen Worker')).toBeVisible();
  const processed = await page.request.post('/api/__e2e/process-public-license-scan?package_count=14');
  expect((await processed.json()).processed).toBe(true);
  await expect(scan.getByText('Abgeschlossen')).toBeVisible({ timeout: 8000 });
  await scan.getByRole('link', { name: /Assessment und Findings/ }).click();
  await expect(page.getByRole('heading', { name: 'Anforderungen', exact: true })).toBeVisible();
  await expect(page.getByText('2 Controls · 14 Einzelbewertungen · 14 ausgewählte Nachweise')).toBeVisible();
  const licensing = page.locator('.requirements-control').filter({ has: page.locator('summary').filter({ hasText: 'PY-LIC-001' }) });
  await licensing.locator('summary').first().focus();
  await page.keyboard.press('Enter');
  await expect(licensing.getByRole('article', { name: /^Bewertung package-/ })).toHaveCount(14);
  await expect(licensing.getByRole('article', { name: 'Bewertung package-14' })).toBeVisible();
  await expect(licensing.getByRole('article', { name: /^Nachweis / })).toHaveCount(14);
  await expect(licensing.getByRole('link', { name: 'uv.lock', exact: true }).last()).toHaveAttribute('href', `https://github.com/djfun/audio-visualizer-python/blob/${'a'.repeat(40)}/uv.lock`);
  await licensing.getByText('Wert, Integrität und technische Herkunft', { exact: true }).last().click();
  await expect(licensing.getByText(`Metadaten SHA-256: ${'b'.repeat(64)}`).last()).toBeVisible();
  const status = page.getByLabel('Status', { exact: true });
  await status.focus();
  await status.selectOption('FAIL');
  await expect(status).toBeFocused();
  await expect(licensing).toHaveAttribute('open', '');
  await page.getByLabel('Controls suchen').fill('does-not-exist');
  await expect(page.getByText('Keine Controls für diese Filter.')).toBeVisible();
  await page.getByRole('button', { name: 'Filter zurücksetzen' }).click();
  await expect(licensing).toHaveAttribute('open', '');
  const selection = page.getByLabel('Prüfung', { exact: true });
  const saved = await selection.inputValue();
  await selection.focus();
  await selection.selectOption('current');
  await expect(selection).toBeFocused();
  await expect(page.getByText('2 Controls · 0 Einzelbewertungen · 0 ausgewählte Nachweise')).toBeVisible();
  await selection.selectOption(saved);
  await expect(licensing.getByRole('article', { name: /^Bewertung package-/ })).toHaveCount(14);
  await page.reload();
  await expect(selection).toHaveValue(saved);
  await expect(licensing).toHaveAttribute('open', '');
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test('rejects foreign assessment links and labels historical expired evidence', async ({ page }) => {
  await page.goto(`/products?organization=${org}`);
  const fixture = await (await page.request.post('/api/__e2e/assessment')).json();
  const workspace = await (await page.request.get('/api/workspace')).json();
  const product = await (await page.request.post(`/api/organizations/${org}/products`, { data: { name: 'Separate product', ownerTeamId: workspace.defaultOwnerTeamId } })).json();
  await page.goto(`/products?organization=${org}&product=${product.id}&view=requirements&assessment=${fixture.id}`);
  await expect(page.getByRole('alert')).toContainText('Die gewählte Prüfung ist für dieses Produkt nicht verfügbar.');
  await expect(page.locator('.requirements-control')).toHaveCount(0);
  await page.getByRole('button', { name: 'Aktuelle Anforderungen anzeigen' }).click();
  await expect(page.getByText(/Ohne Profilzuordnung/)).toBeVisible();
  const historical = await (await page.request.post('/api/__e2e/assessment?workspace=true')).json();
  await page.goto(`/products?organization=${historical.organizationId}&product=${historical.productId}&view=requirements&assessment=${historical.id}`);
  const control = page.locator('.requirements-control').first();
  await control.locator('summary').first().click();
  await expect(page.getByText(/Historische Profilgeltung und Quellzuordnung/)).toBeVisible();
  await expect(control.getByText(/Beim Abruf abgelaufen/)).toBeVisible();
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
