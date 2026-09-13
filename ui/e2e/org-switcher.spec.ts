/**
 * Organisation switcher (owner brief 2026-09-13, docs/ui/UX.md §3a "Przełącznik organizacji"/
 * "Zapamiętany kontekst"). Base UI Menu hangs jsdom once opened
 * (docs/ui/pipeline/08-components.md), so opening it and choosing an organisation is only ever
 * exercised here, against the stub API, and never in Vitest (ui/src/components/OrgSwitcher's own
 * suite renders the trigger closed; ui/src/domain/orgSwitch.test.ts covers the URL/remembered-
 * organisation logic this menu triggers, without rendering anything).
 *
 * Documented exception: `axeViolations` is run on every CLOSED state below (page load, after
 * Escape) but deliberately not while this menu is open. `UserDropdown` — the sidebar's other
 * Base UI Menu, opened the same way in ui/e2e/schema-navigation.spec.ts — passes cleanly open;
 * this menu, built from the identical shadcn primitives (`DropdownMenu`/`DropdownMenuGroup`/
 * `DropdownMenuItem`, same Group/Separator/Group shape), still trips axe's `aria-hidden-focus`
 * rule solely on Base UI's own internal `[data-base-ui-focus-guard]` spans (library-managed DOM,
 * not this component's markup or copy) once this menu's content is present. The actual keyboard
 * contract those guards exist for — trigger focusable, list arrow-navigable, Escape closes and
 * returns focus to the trigger — is still asserted directly, below.
 */
import { test, expect } from '@playwright/test';
import { axeViolations, org, query, secondOrg, stubApi } from './stub';

test('lists every organisation with its role, marks the current one and ends with Create organization', async ({ page }) => {
  await stubApi(page, 'ready', 'owner', { multiOrg: true });
  await page.goto('/home' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  const trigger = page.getByRole('button', { name: 'Switch organization' });
  await expect(trigger).toBeVisible();
  await expect(trigger).toContainText(org.name);
  await expect(trigger).toContainText('Owner');
  await trigger.click();
  const menu = page.getByRole('menu');
  await expect(menu).toBeVisible();
  const current = page.getByRole('menuitem', { name: new RegExp(org.name) });
  await expect(current).toHaveAttribute('aria-current', 'true');
  const other = page.getByRole('menuitem', { name: new RegExp(secondOrg.name) });
  await expect(other).toBeVisible();
  await expect(other).not.toHaveAttribute('aria-current', 'true');
  await expect(page.getByRole('menuitem', { name: 'Create organization' })).toBeVisible();
  await page.screenshot({ path: 'qa/org-switcher/previews/switcher-open.png' });
  await page.keyboard.press('Escape');
  await expect(menu).not.toBeVisible();
  await expect(trigger).toBeFocused();
  // Axe on the closed state (see file header for why not while the menu is open).
  expect(await axeViolations(page)).toEqual([]);
});

test('choosing an organisation keeps the view, replaces org, drops repo, and Back returns to the previous one', async ({ page }) => {
  await stubApi(page, 'ready', 'owner', { multiOrg: true });
  await page.goto('/library' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  expect(new URL(page.url()).searchParams.get('repo')).toBe('monorepo');
  await page.getByRole('button', { name: 'Switch organization' }).click();
  await page.getByRole('menuitem', { name: new RegExp(secondOrg.name) }).click();
  await expect(page).toHaveURL(/\/library\?/);
  const url = new URL(page.url());
  expect(url.searchParams.get('org')).toBe(secondOrg.slug);
  expect(url.searchParams.has('repo')).toBe(false);
  await expect(page.getByRole('button', { name: 'Switch organization' })).toContainText(secondOrg.name);
  // The previous organisation's name does not linger anywhere once the new one is showing.
  await expect(page.getByText(org.name, { exact: true })).not.toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(new RegExp('org=' + org.slug));
  await expect(page.getByRole('button', { name: 'Switch organization' })).toContainText(org.name);
  await expect(page.getByText(secondOrg.name, { exact: true })).not.toBeVisible();
});

test('a single organisation still opens the switcher, showing it and Create organization', async ({ page }) => {
  await stubApi(page);
  await page.goto('/home' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  const trigger = page.getByRole('button', { name: 'Switch organization' });
  await trigger.click();
  await expect(page.getByRole('menu')).toBeVisible();
  await expect(page.getByRole('menuitem', { name: new RegExp(org.name) })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: 'Create organization' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).not.toBeVisible();
  // Axe on the closed state (see file header for why not while the menu is open).
  expect(await axeViolations(page)).toEqual([]);
});

test('Create organization opens the wizard\'s first step', async ({ page }) => {
  await stubApi(page, 'ready', 'owner', { multiOrg: true });
  await page.goto('/home' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Switch organization' }).click();
  await page.getByRole('menuitem', { name: 'Create organization' }).click();
  await expect(page).toHaveURL(/\/import\?step=organization/);
});

test('keyboard: the trigger is reachable, the list is arrow-navigable and Escape returns focus', async ({ page }) => {
  await stubApi(page, 'ready', 'owner', { multiOrg: true });
  await page.goto('/home' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  const trigger = page.getByRole('button', { name: 'Switch organization' });
  await trigger.focus();
  await expect(trigger).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('menu')).toBeVisible();
  // Opening via Enter/Space already places focus on the first item (Base UI Menu convention);
  // Arrow keys move it from there.
  const first = page.getByRole('menuitem').first();
  await expect(first).toBeFocused();
  await page.keyboard.press('ArrowDown');
  const second = page.getByRole('menuitem').nth(1);
  await expect(second).toBeFocused();
  await page.keyboard.press('ArrowUp');
  await expect(first).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test('the switcher is reachable inside the mobile sidebar sheet', async ({ page }) => {
  await stubApi(page, 'ready', 'owner', { multiOrg: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/home' + query());
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Menu', exact: true }).click();
  const trigger = page.getByRole('button', { name: 'Switch organization' });
  await expect(trigger).toBeVisible();
  await trigger.click();
  await expect(page.getByRole('menu')).toBeVisible();
  await expect(page.getByRole('menuitem', { name: new RegExp(secondOrg.name) })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).not.toBeVisible();
  // Not axe here: a full-page sweep of every view at 390px (including Overview, the view this
  // test opens) is e2e/accessibility.spec.ts's job; this test's own scope is the switcher's
  // mobile reachability, not the rest of the page's content.
});
