/**
 * U4 AC4: the owner path sign-in → organisation → repository → import → map → library → skill →
 * decision → export → usage with the keyboard only, against the stub API (`e2e/stub.ts`).
 * `e2e/live/keyboard.spec.ts` walks the same path against the real service.
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import { chosen, commit, enter, org, raw, repoId, sourceUrl, stubApi, tabTo } from './stub';

test('owner completes sign-in, import, library, review and export with keyboard only', async ({ page }) => {
  test.setTimeout(120000);
  await stubApi(page);
  await page.goto('/import?step=login');
  await enter(page, page.getByRole('button', { name: 'Continue with GitHub', exact: true }));
  await page.waitForURL(/\/import\?.*step=organization/);
  await enter(page, page.getByRole('link', { name: 'Use this organization', exact: true }));
  expect(new URL(page.url()).searchParams.get('org')).toBe(org.slug);
  await enter(page, page.getByRole('link', { name: 'Open import status', exact: true }));
  expect(new URL(page.url()).searchParams.get('repo')).toBe(repoId);
  await enter(page, page.getByRole('link', { name: 'Read this import', exact: true }));
  expect(new URL(page.url()).searchParams.get('import_id')).toBe('im-1');
  await expect(page.getByText(commit.slice(0, 12)).first()).toBeVisible();

  const navigation = page.getByRole('navigation', { name: 'Main navigation' });
  await enter(page, navigation.getByRole('link', { name: 'Map', exact: true }));
  await expect(page.getByRole('heading', { level: 1, name: 'Repository knowledge map' })).toBeVisible();
  await enter(page, navigation.getByRole('link', { name: 'Library', exact: true }));
  await tabTo(page, page.getByLabel('Search name, description or path', { exact: true }));
  await page.keyboard.type(chosen.name);
  await enter(page, page.getByRole('button', { name: 'Apply filters', exact: true }));
  await enter(page, page.getByRole('link', { name: chosen.name, exact: true }));
  await expect(page.getByText('Immutable revision')).toBeVisible();
  await enter(page, page.getByRole('link', { name: 'Source & scope', exact: true }));
  const href = await page.getByRole('link', { name: /Open exact source revision/ }).getAttribute('href');
  expect(href).toBe(sourceUrl(chosen));
  const pending = page.waitForEvent('download');
  await enter(page, page.getByRole('button', { name: 'Download exact SKILL.md', exact: true }));
  const download = await pending;
  expect(await fs.readFile((await download.path())!, 'utf8')).toBe(raw(chosen));

  await enter(page, navigation.getByRole('link', { name: 'Proposals', exact: true }));
  await enter(page, page.getByRole('link', { name: 'p-1', exact: true }));
  await tabTo(page, page.locator('input[name=decision][value=approve]'));
  await page.keyboard.press('Space');
  await tabTo(page, page.getByLabel('Reason for this decision', { exact: true }));
  await page.keyboard.type('Reviewed the exact source, scope and revision with the keyboard.');
  await enter(page, page.getByRole('button', { name: 'Save decision', exact: true }));
  await expect(page.getByText(/Recorded: approved_for_export/)).toBeVisible();
  await enter(page, page.getByRole('button', { name: 'Create export', exact: true }));
  await expect(page.getByText('guidefold proposals apply ex-1 --write')).toBeVisible();
  await expect(page.getByText(/Waiting for your Git review/)).toBeVisible();

  await enter(page, navigation.getByRole('link', { name: 'Usage & quality', exact: true }));
  await expect(page.getByText('Exposed but never loaded').first()).toBeVisible();
  await tabTo(page, page.getByLabel('Reason', { exact: true }).first());
  await page.keyboard.type('Checked in Git.');
  await enter(page, page.getByRole('button', { name: 'Record decision', exact: true }).first());
  await expect(page.getByText('Reviewed, no change needed')).toBeVisible();
});

test('focus lands in main on a route change, and the skip link reaches it from the top', async ({ page }) => {
  await stubApi(page);
  await page.goto('/library?org=' + org.slug + '&repo=' + repoId);
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await enter(page, page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Map', exact: true }));
  await expect(page.locator('main')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  const skip = page.getByRole('link', { name: 'Skip to content' });
  for (let step = 0; step < 40 && !(await skip.evaluate(element => element === document.activeElement)); step += 1) await page.keyboard.press('Shift+Tab');
  await expect(skip).toBeFocused();
  await page.keyboard.press('Enter');
  expect(new URL(page.url()).hash).toBe('#main');
});
