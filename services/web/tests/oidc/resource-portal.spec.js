import { expect, test } from '@playwright/test';

test('authenticated resource portal keeps product context above tabs and exposes every mobile destination', async ({ page }) => {
  test.setTimeout(60000);
  const errors = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto('/?organization=foreign');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await expect(page.getByRole('heading', { name: 'Produkte', exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Organisation', exact: true })).toHaveCount(0);
  const nav = page.getByRole('navigation', { name: 'Hauptnavigation' });
  await expect(nav.getByRole('link')).toHaveCount(4);
  await page.getByText('Weitere Funktionen', { exact: true }).click();
  for (const label of ['Findings', 'PR Checks', 'Manuelle Produktverwaltung', 'Administration']) {
    await expect(page.getByRole('link', { name: label, exact: true })).toHaveAttribute('href', /organization=123e4567-e89b-12d3-a456-426614174010/);
  }
  await page.getByText('Weitere Funktionen', { exact: true }).click();
  await page.getByRole('link', { name: 'Audio Visualizer', exact: true }).click();
  const picker = page.getByRole('combobox', { name: 'Produkt auswählen' });
  await expect(picker).toHaveValue(/.+/);
  await expect(page.getByRole('heading', { name: 'Anforderungen', exact: true })).toBeVisible();
  expect(await picker.evaluate((element) => Boolean(element.closest('.product-views')))).toBe(false);
  await page.getByRole('navigation', { name: 'Produktansichten' }).getByRole('link', { name: 'Prüfungen', exact: true }).click();
  await picker.selectOption({ label: 'Platform API' });
  await expect(page.getByRole('heading', { name: 'Platform API', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/view=scans/);
  await expect(page).not.toHaveURL(/assessment=|organization=foreign/);
  await page.reload();
  await expect(picker).toHaveValue('123e4567-e89b-12d3-a456-426614174012');
  await page.getByRole('link', { name: 'Geltungsbereich', exact: true }).click();
  await expect(picker).toHaveValue('123e4567-e89b-12d3-a456-426614174012');
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    for (const label of ['Produkte', 'Kataloge', 'Profile', 'Evidence Packs']) {
      const link = nav.getByRole('link', { name: label, exact: true });
      await expect(link).toBeInViewport();
      await link.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByRole('heading', { name: label, exact: true, level: 1 })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Produkt auswählen' })).toHaveCount(0);
      if (label === 'Kataloge' || label === 'Profile') {
        const card = page.locator('.resource-product-grid article').first();
        await expect(card.getByRole('link', { name: 'Schema ansehen' })).toBeVisible();
        const manifest = card.getByRole('link', { name: /\.json$/ });
        expect(await manifest.evaluate((element) => element.getBoundingClientRect().width)).toBeGreaterThan(150);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    await nav.getByRole('link', { name: 'Kataloge', exact: true }).click();
    await page.getByRole('link', { name: 'Katalog registrieren', exact: true }).click();
    for (const label of ['Repository', 'Git-Ref', 'Ref-Typ', 'Manifestpfad', 'Erwartete Katalog-ID', 'Erwartete Version']) {
      const field = page.getByLabel(label, { exact: true });
      await expect(field).toBeVisible();
      await field.focus();
      await expect(field).toBeFocused();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Kataloge', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('OIDC callback returns to native resource routes', async ({ page }) => {
  for (const route of ['/catalogs', '/profiles', '/evidence-packs']) {
    await page.goto(route);
    await page.getByRole('button', { name: 'Anmelden' }).click();
    await expect(page).toHaveURL(new RegExp(`${route}$`));
    await expect(page.getByRole('navigation', { name: 'Hauptnavigation' })).toBeVisible();
    await page.getByRole('button', { name: 'Lokal abmelden' }).click();
  }
});
