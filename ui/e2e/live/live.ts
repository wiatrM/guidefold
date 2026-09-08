/**
 * Wspólne pomocniki dla zestawu "live": ta sama aplikacja co w trybie fixture, ale przez
 * realne hostowane API (Go + Postgres) pod tym samym pochodzeniem, przez proxy `pnpm dev`.
 *
 * Identyfikatory zasiewu przychodzą ze zmiennych `GUIDEFOLD_E2E_*` (JSON z
 * `python3 tools/dev/stack.py seed`). Czego nie podano, spec odkrywa w czasie działania przez
 * `/api/v1/**` w kontekście strony — nigdy przez wpisany na sztywno identyfikator.
 */
import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';

export const seed = {
  api: process.env.GUIDEFOLD_E2E_API ?? 'http://127.0.0.1:8765',
  org: process.env.GUIDEFOLD_E2E_ORG ?? 'acme',
  repo: process.env.GUIDEFOLD_E2E_REPO ?? 'meridian',
  email: process.env.GUIDEFOLD_E2E_EMAIL ?? 'owner@example.test',
  subject: process.env.GUIDEFOLD_E2E_SUBJECT ?? 'seed-owner',
  importId: process.env.GUIDEFOLD_E2E_IMPORT_ID ?? '',
  proposalId: process.env.GUIDEFOLD_E2E_PROPOSAL_ID ?? '',
  skillId: process.env.GUIDEFOLD_E2E_SKILL_ID ?? '',
  commit: process.env.GUIDEFOLD_E2E_COMMIT ?? '',
  gitHostUrl: process.env.GUIDEFOLD_E2E_GIT_HOST_URL ?? '',
  // Zasiany checkout i jego poświadczenia CLI. Obecne tylko wtedy, gdy przebieg dostał je
  // z `stack.py seed`; bez nich spec, który musi realnie przesunąć źródło, jawnie się pomija.
  tree: process.env.GUIDEFOLD_E2E_TREE ?? '',
  cliHome: process.env.GUIDEFOLD_E2E_CLI_HOME ?? '',
  tokenFile: process.env.GUIDEFOLD_E2E_TOKEN_FILE ?? '',
};

/** Prefiks każdej trasy zakresowanej repozytorium. */
export const repoBase = `/api/v1/orgs/${seed.org}/repos/${seed.repo}`;
export const orgBase = `/api/v1/orgs/${seed.org}`;

/** Kanoniczny query trybu API. `mode=api` jest czytany raz, przy starcie aplikacji. */
export const query = (extra = '') => `?mode=api&org=${seed.org}&repo=${seed.repo}${extra}`;

/**
 * Przesunięcie źródła tak, jak robi to człowiek: dopisek do SKILL.md, commit i `guidefold
 * sync` wysyłanym skryptem. Nie podrabiamy rewizji w bazie — propozycja ma stać się
 * nieaktualna z tego samego powodu, z którego staje się nieaktualna u klienta.
 *
 * Zwraca `false`, gdy przebieg nie dostał zasianego checkoutu; wołający ma się wtedy jawnie
 * pominąć, a nie udawać, że zmierzył 409.
 */
export async function moveTheSource(note: string, relativePath: string): Promise<boolean> {
  if (!seed.tree || !seed.cliHome || !seed.tokenFile) return false;
  const { execFileSync } = await import('node:child_process');
  const fs = await import('node:fs');
  const nodePath = await import('node:path');

  const cli = nodePath.resolve(process.cwd(), '..', 'skills', 'guidefold', 'scripts', 'guidefold');
  const file = nodePath.join(seed.tree, relativePath);
  if (!fs.existsSync(cli) || !fs.existsSync(file)) return false;
  // Serwer porównuje `expected_revision` z bieżącą rewizją *docelowego* skilla propozycji,
  // więc przesunięty musi być dokładnie ten plik, a nie dowolny inny w drzewie.
  fs.appendFileSync(file, `\n\n${note}\n`);

  const git = (...args: string[]) => execFileSync('git', args, { cwd: seed.tree, encoding: 'utf8' });
  git('add', '-A');
  git('-c', 'user.name=live', '-c', 'user.email=live@example.test', 'commit', '-q', '-m', note);

  execFileSync('python3', [cli, 'sync', '--wait', '--json'], {
    cwd: seed.tree,
    encoding: 'utf8',
    timeout: 300000,
    env: {
      ...process.env,
      HOME: seed.cliHome,
      XDG_CONFIG_HOME: nodePath.join(seed.cliHome, '.config'),
      GUIDEFOLD_CREDENTIALS: nodePath.join(seed.cliHome, 'credentials.json'),
      GUIDEFOLD_API: seed.api,
      GUIDEFOLD_ORG: seed.org,
      GUIDEFOLD_REPO_ID: seed.repo,
      GUIDEFOLD_TOKEN: fs.readFileSync(seed.tokenFile, 'utf8').trim(),
    },
  });
  return true;
}

export async function signIn(page: Page, view = 'import', extra = '') {
  const returnTo = `/${view}${query(extra)}`;
  await page.goto(`/api/v1/auth/dev?return_to=${encodeURIComponent(returnTo)}`);
  await page.locator('#subject').fill(seed.subject);
  await page.locator('#email').fill(seed.email);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(url => url.pathname === `/${view}`);
  await settled(page);
}

/**
 * Otwarcie widoku w zalogowanej sesji. Nigdy `networkidle`: heartbeat dostępu (1 s) i pollery
 * importu/publikacji (2 s) nie pozwalają sieci ucichnąć.
 */
export async function open(page: Page, view: string, extra = '') {
  await page.goto(`/${view}${query(extra)}`);
  await settled(page);
}

/** Kilka paneli ładuje się naraz, więc czekamy aż licznik zejdzie do zera. */
export async function settled(page: Page) {
  await page.locator('main').waitFor();
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0, { timeout: 30000 });
}

export async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let step = 0; step < 200; step += 1) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error(`Target is not reachable through Tab: ${await target.evaluate(el => el.outerHTML.slice(0, 120))}`);
}

export async function enter(page: Page, target: Locator) {
  await tabTo(page, target);
  await page.keyboard.press('Enter');
}

export async function axeViolations(page: Page) {
  const path = await import('node:path');
  await page.addScriptTag({ path: path.resolve('node_modules/axe-core/axe.min.js') });
  return page.evaluate(async () => {
    const runner = (window as unknown as {
      axe: { run: (root: Document, options: unknown) => Promise<{ violations: { id: string; nodes: { target: string[] }[] }[] }> };
    }).axe;
    const result = await runner.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
    return result.violations.map(violation => ({ id: violation.id, nodes: violation.nodes.map(node => node.target) }));
  });
}

/**
 * Odczyt z API w sesji przeglądarki (cookie `gf_session` jest HttpOnly, więc żądanie musi
 * pochodzić z tego samego kontekstu co strona).
 */
export async function api<T = Record<string, unknown>>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.status(), `${path}: ${await response.text()}`).toBe(200);
  return response.json() as Promise<T>;
}

/** Pierwszy identyfikator importu: z zasiewu albo z listy repozytorium. */
export async function anImportId(page: Page): Promise<string> {
  if (seed.importId) return seed.importId;
  const list = await api<{ items: { import_id: string }[] }>(page, `${repoBase}/imports`);
  expect(list.items.length, 'the seeded repository has no import').toBeGreaterThan(0);
  return list.items[0].import_id;
}

export interface SkillSummary {
  skill_id: string; name: string; scope: string; owner: string | null;
  path: string; revision_id: string | null; content_sha256: string | null; commit: string | null;
}

export async function someSkills(page: Page): Promise<SkillSummary[]> {
  const list = await api<{ items: SkillSummary[] }>(page, `${repoBase}/skills?limit=100`);
  expect(list.items.length, 'the seeded repository has no skills').toBeGreaterThan(0);
  return list.items;
}

/** Unikalny tekst na przebieg: klient wyprowadza `Idempotency-Key` z treści mutacji. */
export const unique = (what: string) => `${what} (acceptance run ${Date.now()})`;

export async function sha256Hex(bytes: Buffer | Uint8Array): Promise<string> {
  const crypto = await import('node:crypto');
  return crypto.createHash('sha256').update(bytes).digest('hex');
}
