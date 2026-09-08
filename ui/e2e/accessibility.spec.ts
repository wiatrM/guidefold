/** Axe over the seven views and the gallery at three widths, against the stub API (`e2e/stub.ts`). */
import { test, expect } from '@playwright/test';
import { axeViolations, chosen, noHorizontalScroll, query, stubApi } from './stub';

const views: [string, string][] = [
  ['import', '&step=result'], ['library', ''], ['map', '&tab=repository'],
  ['skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision],
  ['proposals', '&proposal=p-1'], ['usage', ''], ['organization', ''],
];
for (const width of [1280, 820, 390]) test('seven views and gallery axe at ' + width, async ({ page }) => {
  test.setTimeout(120000);
  await stubApi(page);
  await page.setViewportSize({ width, height: 720 });
  for (const [view, extra] of views) {
    await page.goto('/' + view + query(extra));
    await page.locator('main').waitFor();
    await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
    expect(await axeViolations(page), view).toEqual([]);
    expect(await noHorizontalScroll(page), view).toBe(true);
  }
  await page.goto('/__components');
  await page.locator('[data-component=Field]').waitFor();
  expect(await axeViolations(page), '__components').toEqual([]);
  expect(await noHorizontalScroll(page), '__components').toBe(true);
});

test('revealed proposal bodies and the mobile menu remain accessible', async ({ page }) => {
  await stubApi(page);
  await page.setViewportSize({ width: 390, height: 720 });
  await page.goto('/proposals' + query('&proposal=p-1'));
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await page.getByText('Read the source body', { exact: true }).click();
  await page.getByText('Read the candidate body', { exact: true }).click();
  await page.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Navigate ·' }) }).locator('summary').click();
  expect(await axeViolations(page)).toEqual([]);
  expect(await noHorizontalScroll(page)).toBe(true);
});
