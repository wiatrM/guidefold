/**
 * Organisation wizard (docs/ui/UX.md §3a, 2026-09-13 redesign) against the stub API. Each test
 * layers its own GitHub installations and repositories over `stubApi` with later `page.route`
 * handlers (Playwright matches the most recently registered route first), so e2e/stub.ts stays
 * untouched. Screenshots at 1280 and 390 land in qa/org-wizard/.
 */
import { test, expect, type Page } from '@playwright/test';
import { axeViolations, org, stubApi } from './stub';

const shots = 'qa/org-wizard/';
const installation = (over: Record<string, unknown> = {}) => ({
  installation_id: 501, account: 'meridian-data', account_type: 'organization', repositories: [],
  repository_selection: 'all', suspended: false, created_at: null, updated_at: null, linked_at: '2026-09-13T08:00:00Z',
  registered_repositories: 4, synced: true, sync_failed_at: null, sync_failure_reason: null, ...over,
});
const repo = (repo_id: string, over: Record<string, unknown> = {}) => ({
  repo_id, name: 'meridian-data/' + repo_id, git_host_url: 'https://github.com/meridian-data/' + repo_id, created_at: null,
  github_installation_id: 501, github_account: 'meridian-data', import_blocked_reason: null,
  last_import_state: null, last_import_error: null, last_import_at: null, ...over,
});
const repos = [
  repo('atlas'),
  repo('forge', { last_import_state: 'ready', last_import_at: '2026-09-12T10:00:00Z' }),
  repo('sandbox', { import_blocked_reason: 'guidefold_yaml_missing' }),
  repo('turnstile', { last_import_state: 'failed', last_import_error: 'fetch_timeout' }),
];

async function layer(page: Page, items: { installations: unknown[]; repos: unknown[] }) {
  const base = '/api/v1/orgs/' + org.slug;
  await page.route(url => url.pathname === base + '/github/installations', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { schema_version: 'mgmt-1', items: items.installations } }) : route.fallback());
  await page.route(url => url.pathname === base + '/repos', route => route.request().method() === 'GET'
    ? route.fulfill({ json: { items: items.repos, next_cursor: null } }) : route.fallback());
}
async function settle(page: Page) {
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
  // The shell focuses #main on every route change (app.tsx) and, with no pointer input yet, Chrome
  // paints its :focus-visible ring; a screenshot taken before any interaction would show that ring
  // as an orange frame around the page. Drop that programmatic focus so captures show the layout.
  // A pointer click on the empty site-header strip clears it the way a person would (verified: the
  // active element becomes <body> and #main no longer matches :focus-visible); blur() alone ran
  // before the shell's own focus effect and left the ring in place.
  await expect(page.locator('#main')).toBeFocused();
  await page.mouse.click(700, 20);
  await expect(page.locator('#main')).not.toBeFocused();
}

test('step 1 asks for a name only; the URL name is derived and creation continues to Connect GitHub', async ({ page }) => {
  await stubApi(page);
  let body: unknown = null;
  await page.route(url => url.pathname === '/api/v1/orgs', route => {
    if (route.request().method() !== 'POST') return route.fallback();
    body = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: { org_id: 'o-7', slug: 'acme-data', name: 'Acme Data', my_role: 'owner', created_at: null, counts: null } });
  });
  await page.goto('/import?step=organization');
  await settle(page);
  await expect(page.getByRole('heading', { level: 2, name: 'Organization', exact: true })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Import progress' })).toContainText('Step 1 of 3: Organization');
  await page.getByLabel('Name', { exact: true }).fill('Acme Data');
  await expect(page.getByText('acme-data', { exact: true })).toBeVisible();
  await expect(page.getByLabel('URL name')).toHaveCount(0);
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({ path: shots + 'step1-organization-' + width + '.png', fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  expect(await axeViolations(page)).toEqual([]);
  await page.getByRole('button', { name: /Create organization/ }).click();
  await expect.poll(() => body).toMatchObject({ name: 'Acme Data', slug: 'acme-data' });
  await expect(page).toHaveURL(/step=github/);
});

test('step 2 installs the GitHub App and names /import as the return address, never a sign-in', async ({ page }) => {
  await stubApi(page, 'empty');
  await layer(page, { installations: [], repos: [] });
  const logins: string[] = [];
  page.on('request', request => { if (request.url().includes('/auth/login')) logins.push(request.url()); });
  let startBody: { return_to?: string } | null = null;
  await page.route(url => url.pathname === '/api/v1/orgs/' + org.slug + '/github/installations/start', route => {
    startBody = route.request().postDataJSON();
    return route.fulfill({ json: { schema_version: 'mgmt-1', install_url: 'https://github.com/apps/guidefold-stub/installations/new?state=s' } });
  });
  await page.route('https://github.com/**', route => route.fulfill({ contentType: 'text/html', body: '<title>GitHub</title>' }));
  await page.goto('/import?org=' + org.slug + '&step=github');
  await settle(page);
  await expect(page.getByRole('heading', { level: 2, name: 'Connect GitHub' })).toBeVisible();
  await expect(page.getByText('Model key required')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Add one in Organization › Model keys' })).toHaveAttribute('href', '/organization?org=' + org.slug + '&tab=keys');
  await expect(page.getByText(/paste/i)).toHaveCount(0);
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({ path: shots + 'step2-github-' + width + '.png', fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  expect(await axeViolations(page)).toEqual([]);
  await page.getByRole('button', { name: 'Connect GitHub', exact: true }).click();
  await page.waitForURL(/github\.com\/apps\/guidefold-stub/);
  const returnTo = new URL((startBody as { return_to?: string } | null)?.return_to ?? '', 'http://x');
  expect(returnTo.pathname).toBe('/import');
  expect(returnTo.searchParams.get('step')).toBe('preview');
  expect(logins).toEqual([]);
});

test('step 3 lists repositories with one state each, filters them, and imports one row', async ({ page }) => {
  await stubApi(page);
  await layer(page, { installations: [installation(), installation({ installation_id: 502, account: 'ada', account_type: 'user', registered_repositories: 0, synced: false })], repos });
  let imported = '';
  await page.route(url => /\/api\/v1\/orgs\/[^/]+\/repos\/[^/]+\/github\/import$/.test(url.pathname), route => {
    imported = new URL(route.request().url()).pathname;
    return route.fulfill({ status: 202, json: { job_id: 'job-9' } });
  });
  await page.goto('/import?org=' + org.slug + '&step=preview');
  await settle(page);
  const list = page.getByRole('list', { name: 'Repositories' });
  await expect(list.getByRole('listitem')).toHaveCount(4);
  await expect(page.getByText('Model key set')).toBeVisible();
  // The second account is still syncing but has registered nothing: no "Syncing (0)" line above
  // a list that already shows the first account's repositories.
  await expect(page.getByText(/^Syncing/)).toHaveCount(0);
  const row = (name: string) => list.getByRole('listitem').filter({ hasText: 'meridian-data/' + name });
  await expect(row('atlas')).toContainText('Ready to import');
  await expect(row('forge')).toContainText('Imported');
  await expect(row('sandbox')).toContainText('No guidefold.yaml');
  await expect(row('turnstile')).toContainText('Import failed');
  await expect(row('turnstile')).toContainText('Reason: fetch_timeout.');
  await expect(page.getByLabel('GitHub account')).toBeVisible();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({ path: shots + 'step3-repositories-' + width + '.png', fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  expect(await axeViolations(page)).toEqual([]);

  await page.getByRole('button', { name: /^Imported/ }).click();
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(page).toHaveURL(/filter=imported/);
  await page.getByRole('button', { name: /^All/ }).click();
  await page.getByRole('textbox', { name: 'Search repositories' }).fill('atl');
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(page).toHaveURL(/q=atl/);
  await page.getByLabel('GitHub account').selectOption('501');
  await expect(page).toHaveURL(/account=501/);
  // Back undoes the account choice (a navigation) but keeps the search (typed, so replaced).
  await page.goBack();
  await expect(page.getByLabel('GitHub account')).toHaveValue('all');
  await expect(page.getByRole('textbox', { name: 'Search repositories' })).toHaveValue('atl');
  await page.getByLabel('GitHub account').selectOption('501');
  await expect(page.getByRole('link', { name: 'Missing a repository? Change GitHub App access' })).toHaveAttribute('href', 'https://github.com/organizations/meridian-data/settings/installations/501');
  await row('atlas').getByRole('button', { name: 'Import', exact: true }).click();
  await expect(page.getByText(/Import queued for meridian-data\/atlas/)).toBeVisible();
  expect(imported).toBe('/api/v1/orgs/' + org.slug + '/repos/atlas/github/import');
});

test('step 3 without any GitHub installation leads back to Connect GitHub', async ({ page }) => {
  await stubApi(page, 'empty');
  await layer(page, { installations: [], repos: [] });
  await page.goto('/import?org=' + org.slug + '&step=preview');
  await settle(page);
  await expect(page.getByRole('heading', { level: 3, name: 'Connect GitHub to import a repository' })).toBeVisible();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({ path: shots + 'step3-empty-' + width + '.png', fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  expect(await axeViolations(page)).toEqual([]);
  await page.getByRole('link', { name: 'Connect GitHub' }).click();
  await expect(page).toHaveURL(/step=github/);
});

test('a shared address restores the filter, search and account of a repository list', async ({ page }) => {
  await stubApi(page);
  await layer(page, { installations: [installation(), installation({ installation_id: 502, account: 'ada', account_type: 'user' })], repos });
  await page.goto('/import?org=' + org.slug + '&step=preview&filter=not_imported&q=turn&account=501');
  await settle(page);
  const list = page.getByRole('list', { name: 'Repositories' });
  await expect(list.getByRole('listitem')).toHaveCount(1);
  await expect(list).toContainText('meridian-data/turnstile');
  await expect(page.getByRole('textbox', { name: 'Search repositories' })).toHaveValue('turn');
  await expect(page.getByLabel('GitHub account')).toHaveValue('501');
});

test('the step header carries no second large tile: the page tile is the only one', async ({ page }) => {
  await stubApi(page);
  await layer(page, { installations: [installation()], repos });
  await page.goto('/import?org=' + org.slug + '&step=preview');
  await settle(page);
  await expect(page.locator('main [data-slot=icon-tile][data-size=lg], main [data-slot=icon-tile][data-size=xl]')).toHaveCount(1);
});
