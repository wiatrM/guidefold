/**
 * axe na siedmiu widokach U4 w trybie API, przy realnych danych.
 *
 * Bez `networkidle`: heartbeat dostępu i pollery importu/publikacji nigdy nie pozwolą sieci
 * ucichnąć, więc bramką jest `main` plus zerowa liczba `aria-busy`.
 */
import { test, expect } from '@playwright/test';
import { anImportId, api, axeViolations, open, repoBase, settled, signIn, someSkills } from './live';

test('axe finds no violation on the seven views in API mode', async ({ page }) => {
  test.setTimeout(180000);
  await signIn(page);

  const importId = await anImportId(page);
  const skills = await someSkills(page);
  const chosen = skills[0];
  const proposals = await api<{ items: { proposal_id: string }[] }>(page, `${repoBase}/proposals`);
  const scopes = await api<{ items?: { scope?: string }[] }>(page, `${repoBase}/map/scopes`);
  const scope = scopes.items?.[0]?.scope ?? chosen.scope;

  const views: [string, string, string?][] = [
    ['import', `&step=result&import_id=${importId}`],
    ['library', ''],
    ['map', `&tab=scopes&scope=${encodeURIComponent(scope)}`],
    ['skill', `&skill=${encodeURIComponent(chosen.skill_id)}&revision=${chosen.revision_id}`],
    ['proposals', proposals.items[0] ? `&proposal=${proposals.items[0].proposal_id}` : ''],
    ['usage', ''],
    ['organization', ''],
    ['organization', '&tab=audit', 'organization, audit tab'],
  ];

  for (const [view, extra, label] of views) {
    await open(page, view, extra);
    await page.evaluate(() => document.fonts.ready);
    const violations = await axeViolations(page);
    expect(violations, label ?? view).toEqual([]);
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    expect(fits, `${label ?? view} scrolls horizontally`).toBe(true);
  }
});

test('the seven views stay accessible at 390 px, and the mobile menu with them', async ({ page }) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 390, height: 720 });
  await signIn(page);

  for (const view of ['import', 'library', 'map', 'proposals', 'usage', 'organization']) {
    await open(page, view);
    await page.evaluate(() => document.fonts.ready);
    expect(await axeViolations(page), view).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), view).toBe(true);
  }

  await open(page, 'proposals');
  await page.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Navigate ·' }) }).locator('summary').click();
  await settled(page);
  expect(await axeViolations(page), 'mobile menu open').toEqual([]);
});
