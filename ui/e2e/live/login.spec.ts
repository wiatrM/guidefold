/**
 * Logowanie przez dostawcę deweloperskiego i nagłówek złożony z `/me`.
 *
 * Dowodzi, że aplikacja stoi na realnym API: organizacja pochodzi z `/me.orgs`, a odznaka
 * `Local simulation` (wyłącznie tryb fixture) nie występuje.
 */
import { test, expect } from '@playwright/test';
import { api, open, orgBase, seed, signIn, query } from './live';

test('the dev provider signs the owner in and the header comes from /me', async ({ page }) => {
  await signIn(page, 'import', '&step=result');

  const me = await api<{ user: { email: string }; orgs: { slug: string; name: string; role: string }[]; csrf_token: string }>(page, '/api/v1/me');
  const membership = me.orgs.find(org => org.slug === seed.org);
  expect(membership, `/me.orgs has no ${seed.org}`).toBeTruthy();

  await expect(page.getByText(membership!.name, { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Owner · organization role')).toBeVisible();
  await expect(page.getByText(`${seed.org} / ${seed.repo}`, { exact: true })).toBeVisible();

  // Tryb fixture i tylko on rysuje tę odznakę; jej brak jest dowodem trybu API.
  await expect(page.getByText('Local simulation')).toHaveCount(0);
  await expect(page.getByText('Access unavailable')).toHaveCount(0);
  expect(me.csrf_token, 'a session without a CSRF token cannot mutate anything').toBeTruthy();
  expect(me.user.email).toBe(seed.email);
});

test('the seven views are reachable and each names itself', async ({ page }) => {
  await signIn(page);
  const titles: Record<string, string> = {
    import: 'Import repository skills', library: 'Skill library', map: 'Repository knowledge map',
    skill: 'Skill revision', proposals: 'Review a skill revision', usage: 'Usage & quality',
    organization: 'Organization',
  };
  for (const [view, heading] of Object.entries(titles)) {
    await open(page, view);
    await expect(page.getByRole('heading', { name: heading, level: 1 })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  }
});

test('an organisation the account does not belong to is restricted, not described', async ({ page }) => {
  await signIn(page);
  await page.goto(`/library?mode=api&org=not-a-member-of-this&repo=${seed.repo}`);
  await page.locator('main').waitFor();
  await expect(page.getByText('Organization unavailable')).toBeVisible();
  await expect(page.getByText('An organization in the URL is not authorization.')).toBeVisible();
});
