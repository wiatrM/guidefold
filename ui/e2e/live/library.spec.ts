/**
 * Biblioteka na realnym katalogu: filtry żyją w adresie, a wartość, której snapshot nie ma,
 * jest nazwana zamiast po cichu rozszerzona do "All".
 */
import { test, expect } from '@playwright/test';
import { api, open, repoBase, seed, signIn, someSkills } from './live';

test('filters live in the URL and the result echoes the snapshot', async ({ page }) => {
  await signIn(page);
  const skills = await someSkills(page);
  const chosen = skills[0];

  await open(page, 'library');
  await expect(page.getByRole('heading', { name: 'Find an instruction' })).toBeVisible();

  await page.getByLabel('Search name, description or path', { exact: true }).fill(chosen.name);
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`q=${encodeURIComponent(chosen.name)}`));
  await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();

  // Scope jest fasetą, nie pierwszym kluczem sortowania: filtrujemy i czytamy echo.
  await open(page, 'library', `&scope=${encodeURIComponent(chosen.scope)}`);
  const table = page.getByRole('region', { name: 'Skill summaries matching the current filters' });
  await expect(table).toBeVisible();
  await expect(page.getByLabel('Scope', { exact: true })).toHaveValue(chosen.scope);
  const answer = await api<{ items: unknown[]; snapshot_id: string | null }>(page, `${repoBase}/skills?scope=${encodeURIComponent(chosen.scope)}`);
  expect(answer.items.length).toBeGreaterThan(0);
  if (answer.snapshot_id) {
    await expect(page.getByText(answer.snapshot_id, { exact: false }).first()).toBeVisible();
  }
});

test('a scope this snapshot does not have is named, kept in the URL and never widened', async ({ page }) => {
  await signIn(page);
  const absent = 'no.such.scope.in.this.snapshot';
  await open(page, 'library', `&scope=${absent}`);

  await expect(page.getByText(`This snapshot has no value ${absent}`, { exact: false })).toBeVisible();
  await expect(page.getByText('This value is not available in this snapshot. Choose another value or clear this filter.')).toBeVisible();
  await expect(page.getByLabel('Scope', { exact: true }).getByRole('option', { name: `Not available in this snapshot: ${absent}` })).toHaveCount(1);
  await expect(page.getByLabel('Scope', { exact: true })).toHaveValue(absent);
  await expect(page.getByText('Filter value unavailable').first()).toBeVisible();
  // Nic nie zostało rozszerzone: adres wciąż niesie odrzuconą wartość.
  expect(new URL(page.url()).searchParams.get('scope')).toBe(absent);
});

test('the result count and the pager agree with the API', async ({ page }) => {
  await signIn(page);
  const answer = await api<{ items: unknown[]; next_cursor: string | null }>(page, `${repoBase}/skills`);
  await open(page, 'library');
  await expect(page.getByText(`${answer.items.length} on this page`)).toBeVisible();
  const next = page.getByRole('button', { name: 'Next page', exact: true });
  if (answer.next_cursor) {
    await expect(next).toBeEnabled();
    await next.click();
    await expect(page).toHaveURL(/cursor=/);
    await expect(page.getByText('Reading a page after the first. The cursor stays in the address.')).toBeVisible();
  } else {
    await expect(page.getByText('First page.')).toBeVisible();
  }
  expect(seed.repo.length).toBeGreaterThan(0);
});
