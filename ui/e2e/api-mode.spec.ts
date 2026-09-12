/**
 * The seven hosted views against the stub management API in `e2e/stub.ts`.
 *
 * Each test proves the wiring of a view (URL state, contract fields, keyboard reach, a mutation's
 * idempotency and its honest outcome), not the API itself; `e2e/live/` runs the same app against
 * the real service.
 */
import { test, expect } from '@playwright/test';
import { axeViolations, chosen, nodes, noHorizontalScroll, open, sourceUrl, stubApi, tabTo } from './stub';

test('an unauthenticated management route lands on the login page outside the shell', async ({ page }) => {
  const state = await stubApi(page);
  state.signedOut = true;
  await page.goto('/proposals?state=open');
  await expect(page).toHaveURL(/\/login\?return=%2Fproposals%3Fstate%3Dopen/);
  await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Continue with GitHub/ })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toHaveCount(0);
});

test('the organisation comes from the API once the session is confirmed', async ({ page }) => {
  await stubApi(page);
  await page.goto('/import');
  await expect(page.getByText('Meridian Data')).toBeVisible();
  // Sign-in is not a step of the wizard any more.
  await expect(page.getByRole('button', { name: /Continue with GitHub/ })).toHaveCount(0);
});

test('library filters, cursor context and the skill link survive the URL', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library');
  await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();
  await page.getByLabel('Scope', { exact: true }).selectOption(chosen.scope);
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect(page).toHaveURL(new RegExp('scope=' + encodeURIComponent(chosen.scope)));
  await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();
});

test('an unavailable filter value is named and never widened to All', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library', '&scope=not-a-scope');
  await expect(page.getByText(/This snapshot has no value not-a-scope/)).toBeVisible();
  const field = page.getByLabel('Scope', { exact: true });
  await expect(field).toHaveValue('not-a-scope');
  await expect(field).toHaveAttribute('aria-invalid', 'true');
  await expect(field.locator('option:checked')).toHaveText('Not available in this snapshot: not-a-scope');
});

test('the skill view links the exact host, file and commit', async ({ page }) => {
  await stubApi(page);
  await open(page, 'skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision + '&tab=source');
  const link = page.getByRole('link', { name: /Open exact source revision/ });
  await expect(link).toHaveAttribute('href', sourceUrl(chosen));
});

test('a revision that does not exist is an error, never a newer body', async ({ page }) => {
  await stubApi(page);
  await open(page, 'skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + 'f'.repeat(64));
  await expect(page.getByText('Revision not available')).toBeVisible();
  await expect(page.getByText(chosen.body.split('\n')[0])).toHaveCount(0);
});

test('owner reaches library, skill, decision and export with the keyboard only', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library');
  await tabTo(page, page.getByLabel('Search name, description or path', { exact: true }));
  await page.keyboard.type(chosen.name);
  await tabTo(page, page.getByRole('button', { name: 'Apply filters', exact: true }));
  await page.keyboard.press('Enter');
  await tabTo(page, page.getByRole('link', { name: chosen.name, exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText('Immutable revision')).toBeVisible();

  await open(page, 'proposals', '&proposal=p-1');
  await tabTo(page, page.getByLabel('Reason for this decision', { exact: true }));
  await page.keyboard.type('Read the source and the scope before approving.');
  await tabTo(page, page.getByRole('button', { name: 'Save decision', exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText(/Recorded: approved_for_export/)).toBeVisible();

  await tabTo(page, page.getByRole('button', { name: 'Create export', exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText('guidefold proposals apply ex-1 --write')).toBeVisible();
  await expect(page.getByText(/Waiting for your Git review/)).toBeVisible();
});

test('the usage queue records an owner decision and keeps Unknown out of zero', async ({ page }) => {
  await stubApi(page);
  await open(page, 'usage');
  await expect(page.getByText('Exposed but never loaded').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Delivery and outcome per skill' }).getByText('2 of 4')).toBeVisible();
  await expect(page.getByText('Small sample; no rate is reported below 20 assessments.')).toBeVisible();
  await page.getByLabel('Reason', { exact: true }).fill('Checked in Git.');
  await page.getByRole('button', { name: 'Record decision', exact: true }).click();
  await expect(page.getByText('Reviewed, no change needed')).toBeVisible();
});

test('the plan is read before generation, and a job skipped for lack of a generator reads as honest, not failed', async ({ page }) => {
  await stubApi(page);
  await open(page, 'import', '&step=result&import_id=im-1');
  await expect(page.getByText('Groups and inputs (1)')).toBeVisible();
  await expect(page.getByText('No generator configured')).toBeVisible();
  await page.getByRole('button', { name: 'Generate proposals' }).click();
  await expect(page.getByText('Generation started')).toBeVisible();
  await expect(page.getByText('j-gen-1')).toBeVisible();
  await expect(page.getByText(/No generator is configured on this API\. This is not a failure/)).toBeVisible();
});

test('the audit tab pages through entries with a cursor and shows every column', async ({ page }) => {
  await stubApi(page);
  await open(page, 'organization', '&tab=audit');
  await expect(page.getByRole('cell', { name: 'member.invite' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'req-1' })).toBeVisible();
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByRole('cell', { name: 'repo.create' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'req-2' })).toBeVisible();
});

test('a member reads only their own scoped audit rows (1.3.0, §4.1), on the Organization Audit tab and Overview "Your actions", with no owner-only control in sight', async ({ page }) => {
  await stubApi(page, 'ready', 'member');

  await open(page, 'organization', '&tab=audit');
  await expect(page.getByText('Member access is read only here. Import and organization changes require an owner.')).toBeVisible();
  await expect(page.getByText('Your own actions')).toBeVisible();
  await expect(page.getByText('Owner', { exact: true })).not.toBeVisible();
  await expect(page.getByRole('cell', { name: 'member.invite' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'req-1' })).toBeVisible();
  // req-2 belongs to a different principal (`principal:u-2`); the server never sends it to this
  // member, so it is not merely hidden by the client — it was never in the response to page through.
  await expect(page.getByRole('cell', { name: 'repo.create' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Next page' })).toHaveCount(0);

  await open(page, 'home');
  await expect(page.getByText('Recent activity')).toBeVisible();
  await expect(page.getByText('Your actions', { exact: true })).toBeVisible();
  await expect(page.getByText('Last entries of your own actions in this organization')).toBeVisible();
  await expect(page.getByText('Organization audit')).not.toBeVisible();
  await expect(page.getByRole('cell', { name: 'member.invite' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'repo.create' })).toHaveCount(0);
});

test('a link suggestion is never auto-linked: the operator action redirects to the real confirmation URL', async ({ page }) => {
  const state = await stubApi(page);
  state.linkSuggested = true;
  await open(page, 'organization');
  await expect(page.getByText('Another sign-in method uses this e-mail.')).toBeVisible();
  await tabTo(page, page.getByRole('button', { name: 'Link google' }));
  await Promise.all([page.waitForURL('**/link-confirm/google'), page.keyboard.press('Enter')]);
  await expect(page.getByText('Linked.')).toBeVisible();
});

const apiViews: [string, string, string?][] = [
  ['import', '&step=result&import_id=im-1'],
  ['library', ''],
  ['map', '&tab=scopes&scope=' + encodeURIComponent(nodes[0].id)],
  ['skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision],
  ['proposals', '&proposal=p-1'],
  ['usage', ''],
  ['organization', ''],
  ['organization', '&tab=audit', 'organization, audit tab'],
];
test('axe finds no violation on the login page, at 390 as well as 1280', async ({ page }) => {
  const state = await stubApi(page);
  state.signedOut = true;
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 720 });
    await page.goto('/login');
    await page.getByRole('button', { name: /Continue with/ }).first().waitFor();
    expect(await axeViolations(page), 'login/' + width).toEqual([]);
    expect(await noHorizontalScroll(page), 'login/' + width).toBe(true);
  }
});

for (const [view, extra, label] of apiViews) {
  test('axe finds no violation on ' + (label ?? view), async ({ page }) => {
    await stubApi(page);
    await open(page, view, extra);
    expect(await axeViolations(page), view).toEqual([]);
    expect(await noHorizontalScroll(page), view).toBe(true);
  });
}
