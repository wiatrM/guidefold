/** Library filters: an unknown URL value is named and kept until the operator replaces or clears it. */
import { test, expect } from '@playwright/test';
import { axeViolations, chosen, open, stubApi } from './stub';

test('unknown URL filter stays visible until the user explicitly replaces or clears it', async ({ page }) => {
  test.setTimeout(90000);
  await stubApi(page);
  for (const [key, label] of [['scope', 'Scope'], ['owner', 'Owner from source'], ['layer', 'Source layer'], ['status', 'Source status']]) {
    await open(page, 'library', '&' + key + '=missing-value');
    const field = page.getByLabel(label, { exact: true });
    await expect(field).toHaveValue('missing-value');
    await expect(field).toHaveAttribute('aria-invalid', 'true');
    await expect(field.locator('option:checked')).toHaveText('Not available in this snapshot: missing-value');
    await expect(page.getByText(/This snapshot has no value missing-value/)).toBeVisible();
    await expect(page.getByText('Filter value unavailable', { exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    expect(new URL(page.url()).searchParams.get(key)).toBe('missing-value');
    await expect(field).toHaveValue('missing-value');
    expect(await axeViolations(page), key).toEqual([]);
    await field.selectOption('');
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    expect(new URL(page.url()).searchParams.has(key)).toBe(false);
    await expect(field).not.toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();
  }
});

test('a facet value outside the current page stays selectable and the cursor is dropped on a new query', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library', '&cursor=page-9&scope=' + encodeURIComponent(chosen.scope));
  await expect(page.getByLabel('Scope', { exact: true })).toHaveValue(chosen.scope);
  await expect(page.getByText(/Reading a page after the first/)).toBeVisible();
  await page.getByLabel('Search name, description or path', { exact: true }).fill('turnstile');
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  const url = new URL(page.url());
  expect(url.searchParams.get('q')).toBe('turnstile');
  expect(url.searchParams.get('scope')).toBe(chosen.scope);
  expect(url.searchParams.has('cursor')).toBe(false);
  await expect(page.getByText('First page.')).toBeVisible();
});
