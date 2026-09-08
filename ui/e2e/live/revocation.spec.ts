/**
 * Odwołanie członkostwa: prywatny widok znika w drugiej, wciąż otwartej sesji.
 *
 * Pomiar jest zegarem ściennym, nie przyspieszonym: usunięcie następuje w kontekście
 * właściciela, a kontekst członka jest odpytywany aż zasłoni dane. Liczba w komunikacie
 * asercji to realne sekundy tego przebiegu, nie deklaracja SLA.
 *
 * Mechanizm po stronie aplikacji: `AccessController` odświeża `/me` co 25 s
 * (ACCESS_REFRESH_MS) i ujawnia dane tylko przez 45 s od potwierdzenia (ACCESS_TTL_MS);
 * 401/403 z dowolnego żądania natychmiast czyści cache i szkice.
 */
import { test, expect, type BrowserContext, type Page } from '@playwright/test';
import { seed, settled } from './live';

const MASK_DEADLINE_S = 60;

async function devSignIn(page: Page, subject: string, email: string, returnTo: string) {
  await page.goto(`/api/v1/auth/dev?return_to=${encodeURIComponent(returnTo)}`);
  await page.locator('#subject').fill(subject);
  await page.locator('#email').fill(email);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(url => !url.pathname.startsWith('/api/'));
}

async function csrfOf(page: Page): Promise<string> {
  const response = await page.request.get('/api/v1/me');
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}

/** Odpowiedź tworząca zaproszenie niesie `accept_url`; token jest jego przedostatnim segmentem. */
function invitationToken(invitation: { accept_url: string }): string {
  const segments = new URL(invitation.accept_url).pathname.split('/');
  const token = segments[segments.indexOf('invitations') + 1];
  expect(token, `no token in accept_url ${invitation.accept_url}`).toBeTruthy();
  return token;
}

async function mutate(page: Page, method: 'post' | 'delete', path: string, body?: unknown) {
  const csrf = await csrfOf(page);
  const headers: Record<string, string> = { 'X-CSRF-Token': csrf, 'Idempotency-Key': `live-${Date.now()}-${Math.random().toString(36).slice(2)}` };
  return method === 'post'
    ? page.request.post(path, { headers, data: body ?? {} })
    : page.request.delete(path, { headers });
}

test('a removed member stops seeing organisation data inside 60 seconds', async ({ browser }, testInfo) => {
  test.setTimeout(180000);
  const stamp = Date.now();
  const memberEmail = `revoked-${stamp}@acceptance.test`;
  const view = `/library?mode=api&org=${seed.org}&repo=${seed.repo}`;

  let ownerContext: BrowserContext | undefined;
  let memberContext: BrowserContext | undefined;
  try {
    ownerContext = await browser.newContext();
    memberContext = await browser.newContext();
    const owner = await ownerContext.newPage();
    const member = await memberContext.newPage();

    await devSignIn(owner, seed.subject, seed.email, view);
    await devSignIn(member, `revoked-${stamp}`, memberEmail, view);

    // Zaproszenie i jego przyjęcie: członek wchodzi normalną drogą, nie przez SQL.
    const invited = await mutate(owner, 'post', `/api/v1/orgs/${seed.org}/invitations`, { email: memberEmail, role: 'member' });
    expect(invited.status(), await invited.text()).toBeLessThan(300);
    const invitation = await invited.json();
    const accepted = await mutate(member, 'post', `/api/v1/invitations/${invitationToken(invitation)}/accept`);
    expect(accepted.status(), await accepted.text()).toBeLessThan(300);

    // Członek widzi prywatne dane.
    await member.goto(view);
    await settled(member);
    await expect(member.getByRole('heading', { name: 'Skill library', level: 1 })).toBeVisible();
    await expect(member.getByText(`${seed.org} / ${seed.repo}`, { exact: true })).toBeVisible();
    await expect(member.getByText('Access unavailable')).toHaveCount(0);
    await expect(member.getByText('Organization unavailable')).toHaveCount(0);

    const memberId = (await (await member.request.get('/api/v1/me')).json()).user.id as string;

    // Usunięcie w innej sesji. Od tej chwili liczymy realny czas.
    const removedAt = Date.now();
    const removed = await mutate(owner, 'delete', `/api/v1/orgs/${seed.org}/members/${memberId}`);
    expect(removed.status(), await removed.text()).toBeLessThan(300);

    const masked = member.getByText('Access unavailable')
      .or(member.getByText('Organization unavailable'))
      .or(member.getByText('Access not reconfirmed'))
      .first();
    await expect(masked).toBeVisible({ timeout: MASK_DEADLINE_S * 1000 });
    const elapsedS = (Date.now() - removedAt) / 1000;

    // Nic z organizacji nie zostało na ekranie.
    await expect(member.getByRole('region', { name: 'Skill summaries matching the current filters' })).toHaveCount(0);

    const measured = `wall-clock: the member's open tab masked organisation data ${elapsedS.toFixed(1)} s after DELETE /api/v1/orgs/${seed.org}/members/{user_id} (deadline ${MASK_DEADLINE_S} s, no virtual clock, no page reload)`;
    // eslint-disable-next-line no-console
    console.log(`[revocation] ${measured}`);
    await testInfo.attach('revocation-latency', { body: measured, contentType: 'text/plain' });
    expect(elapsedS, measured).toBeLessThan(MASK_DEADLINE_S);
  } finally {
    await memberContext?.close();
    await ownerContext?.close();
  }
});

test('the API denies a removed member on the very next request', async ({ browser }, testInfo) => {
  test.setTimeout(120000);
  const stamp = Date.now();
  const memberEmail = `denied-${stamp}@acceptance.test`;
  let ownerContext: BrowserContext | undefined;
  let memberContext: BrowserContext | undefined;
  try {
    ownerContext = await browser.newContext();
    memberContext = await browser.newContext();
    const owner = await ownerContext.newPage();
    const member = await memberContext.newPage();
    await devSignIn(owner, seed.subject, seed.email, '/import');
    await devSignIn(member, `denied-${stamp}`, memberEmail, '/import');

    const invitation = await (await mutate(owner, 'post', `/api/v1/orgs/${seed.org}/invitations`, { email: memberEmail, role: 'member' })).json();
    await mutate(member, 'post', `/api/v1/invitations/${invitationToken(invitation)}/accept`);

    const before = await member.request.get(`/api/v1/orgs/${seed.org}/repos/${seed.repo}/skills`);
    expect(before.status()).toBe(200);

    const memberId = (await (await member.request.get('/api/v1/me')).json()).user.id as string;
    const removedAt = Date.now();
    await mutate(owner, 'delete', `/api/v1/orgs/${seed.org}/members/${memberId}`);
    const after = await member.request.get(`/api/v1/orgs/${seed.org}/repos/${seed.repo}/skills`);
    const elapsedS = (Date.now() - removedAt) / 1000;

    expect(after.status(), `the API answered ${after.status()} after removal`).toBe(403);
    const body = await after.json();
    // 403, nigdy 404: istnienie organizacji nie może być wyroczna.
    expect(body.error).toBe('forbidden');
    expect(Object.keys(body).sort()).toEqual(['error', 'message', 'request_id'].filter(key => key in body).sort());

    const measured = `wall-clock: the API denied the removed member ${elapsedS.toFixed(2)} s after the DELETE, on the next request, with no cache window`;
    // eslint-disable-next-line no-console
    console.log(`[revocation-api] ${measured}`);
    await testInfo.attach('revocation-api-latency', { body: measured, contentType: 'text/plain' });
  } finally {
    await memberContext?.close();
    await ownerContext?.close();
  }
});
