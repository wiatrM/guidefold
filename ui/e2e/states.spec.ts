/**
 * The six non-ready states of UX §7 on every view, each produced by the stub API rather than by
 * a URL flag: an empty organisation, a slow one, an incomplete one, a failing one, one whose
 * membership cannot be reconfirmed, and one the account does not belong to.
 */
import { test, expect, type Page } from '@playwright/test';
import { axeViolations, chosen, LOADING_DELAY_MS, noHorizontalScroll, query, stubApi, type Scenario } from './stub';

const skillView = '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision;
/** The address each view is opened at per scenario: an empty organisation has no skill or
 * proposal to name, and a failing one must not echo an identifier from the address as content. */
const viewsFor = (state: Scenario): [string, string][] => [
  ['import', '&step=result'],
  ['library', state === 'partial' ? '&scope=not-a-scope' : ''],
  ['map', state === 'partial' ? '&tab=repository&skill=' + encodeURIComponent(chosen.id) : '&tab=repository'],
  ['skill', state === 'empty' ? '' : skillView],
  ['proposals', state === 'empty' ? '' : '&proposal=p-1'],
  ['usage', ''],
  ['organization', state === 'empty' ? '&tab=integrations' : ''],
];
const content = /postgres-auth|urn:skill:|88e404561a9f|ada@meridian\.test/;

async function settle(page: Page, state: Scenario) {
  await page.locator('main').waitFor();
  if (state !== 'loading') await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
}
async function clean(page: Page, label: string) {
  expect(await axeViolations(page), label).toEqual([]);
  expect(await noHorizontalScroll(page), label).toBe(true);
}

for (const state of ['empty', 'loading', 'partial', 'error'] as const) test('seven views: ' + state, async ({ page }) => {
  test.setTimeout(90000);
  await stubApi(page, state);
  for (const [view, extra] of viewsFor(state)) {
    await page.goto('/' + view + query(extra));
    await settle(page, state);
    const main = page.locator('main');
    if (state === 'empty') {
      // An absence is named as one; nothing reads as a count of zero observations.
      await expect(main.getByText(/No (skills yet|import yet|proposals to review|observations|installation yet|skill selected)|This directory holds no imported object/).first()).toBeVisible();
      expect(await main.innerText(), view).not.toMatch(content);
    }
    if (state === 'loading') {
      await expect(main.locator('[aria-busy=true]').first()).toBeVisible();
      expect(await main.innerText(), view).not.toMatch(content);
    }
    if (state === 'partial' && view !== 'organization') {
      // Every view with an incomplete answer says so with a labelled badge, never colour alone.
      await expect(main.getByText('Partial', { exact: true }).first()).toBeVisible();
    }
    if (state === 'error') {
      await expect(main.getByText(/Could not read this view/).first()).toBeVisible();
      await expect(main.getByRole('button', { name: /^Retry/ }).first()).toBeVisible();
      expect(await main.innerText(), view).not.toMatch(content);
    }
    await clean(page, view + '/' + state);
  }
});

test('seven views: restricted, an organisation the account does not belong to', async ({ page }) => {
  test.setTimeout(90000);
  await stubApi(page, 'restricted');
  for (const [view, extra] of viewsFor('restricted')) {
    await page.goto('/' + view + query(extra));
    await settle(page, 'restricted');
    const main = page.locator('main');
    await expect(main.getByText('Organization unavailable')).toBeVisible();
    await expect(main.getByText('An organization in the URL is not authorization.')).toBeVisible();
    expect(await main.innerText(), view).not.toMatch(content);
    await expect(main.locator('input, textarea, select')).toHaveCount(0);
    expect(await page.title()).not.toContain('Meridian');
    await clean(page, view + '/restricted');
  }
});

test('seven views: degraded, membership past its confirmation window with /me failing', async ({ page }) => {
  test.setTimeout(120000);
  await stubApi(page, 'degraded');
  await page.clock.install();
  for (const [view, extra] of viewsFor('degraded')) {
    await page.goto('/' + view + query(extra));
    await settle(page, 'degraded');
    await expect(page.locator('main').getByText(/postgres-auth|Meridian|Imports|Members|Review queue|No observations|Repository tree/).first()).toBeVisible();
    // 45 s after the last successful /me the view is masked until a check succeeds again; the
    // stub refuses every /me after the first, so the mask stays and offers a manual re-check.
    await page.clock.fastForward(46000);
    const main = page.locator('main');
    await expect(main.getByText(/Access not reconfirmed|Confirming access/).first()).toBeVisible();
    await expect(main.getByText(/Membership was last confirmed more than 45 seconds ago|Checking membership/).first()).toBeVisible();
    expect(await main.innerText(), view).not.toMatch(content);
    await expect(main.locator('input, textarea, select')).toHaveCount(0);
    await clean(page, view + '/degraded');
    await page.clock.fastForward(LOADING_DELAY_MS);
  }
});

test('a 403 from the repository masks every view, with the session and the way back intact', async ({ page }) => {
  await stubApi(page);
  await page.route('**/api/v1/orgs/meridian/repos/monorepo/**', route => route.fulfill({
    status: 403, contentType: 'application/json', headers: { 'Cache-Control': 'no-store' },
    body: JSON.stringify({ error: 'forbidden', message: 'No.', request_id: 'stub-403' }),
  }));
  for (const [view, extra] of [['library', ''], ['skill', skillView], ['usage', '']]) {
    const at = '/' + view + query(extra);
    await page.goto(at);
    await settle(page, 'restricted');
    const main = page.locator('main');
    // A denial observed by any request is reported to the access controller, which masks every
    // view; the route's own restricted state is never reached. The session is untouched, so this
    // is NOT the login page: sending the operator to sign in would only return them to the same
    // forbidden address and deny again.
    await expect(main.getByText('Not available to your account').first()).toBeVisible();
    await expect(page).toHaveURL(new RegExp(view));
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toHaveCount(0);
    await expect(main.getByRole('button', { name: 'Open your organization' })).toBeVisible();
    await expect(main.getByRole('button', { name: 'Sign in again' })).toBeVisible();
    expect(await main.innerText(), view).not.toMatch(content);
    await expect(main.locator('input, textarea, select')).toHaveCount(0);
    await clean(page, view + '/403');
  }
  // And the way back actually leaves: the refused repository is dropped from the address.
  await page.getByRole('button', { name: 'Open your organization' }).click();
  await page.waitForURL(/\/import\?org=meridian&step=preview/);
});
