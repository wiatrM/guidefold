/**
 * Ścieżka właściciela wyłącznie z klawiatury, przez realne API.
 *
 * Odpowiednik `e2e/owner-keyboard.spec.ts`, który chodzi po stubie z `e2e/stub.ts`; tu import
 * pochodzi z zasiewu, a logowanie z dostawcy deweloperskiego.
 */
import { test, expect } from '@playwright/test';
import { anImportId, api, enter, repoBase, settled, seed, signIn, someSkills, tabTo, unique } from './live';

test('owner reaches import, library, skill and a decision with the keyboard only', async ({ page }) => {
  // Logowanie: dostawca jest przyciskiem, więc dochodzimy do niego Tabem i naciskamy Enter.
  // Brama sesji: adres panelu bez sesji ląduje na /login z celem powrotu w `?return=`.
  await page.goto(`/import?org=${seed.org}&repo=${seed.repo}`);
  await page.waitForURL(/\/login\?return=/);
  await settled(page);
  await enter(page, page.getByRole('button', { name: /Continue with (Google|GitHub)/ }).first());

  await page.locator('#subject').waitFor();
  await tabTo(page, page.locator('#subject'));
  await page.keyboard.type(seed.subject);
  await tabTo(page, page.locator('#email'));
  await page.keyboard.type(seed.email);
  await enter(page, page.getByRole('button', { name: 'Sign in' }));
  await page.waitForURL(/\/(import|library|proposals|usage|organization|map|skill)/);
  await settled(page);

  // Import: status zasianego importu, osiągnięty linkiem z listy.
  const importId = await anImportId(page);
  await page.goto(`/import?org=${seed.org}&repo=${seed.repo}&step=result`);
  await settled(page);
  await enter(page, page.getByRole('link', { name: 'Read this import' }).first());
  await settled(page);
  await expect(page.getByRole('heading', { name: 'Import result' })).toBeVisible();
  expect(new URL(page.url()).searchParams.get('import_id')).toBeTruthy();
  expect(importId.length).toBeGreaterThan(0);

  // Library: nawigacja, wyszukiwarka i przejście do skilla, wszystko z klawiatury.
  const skills = await someSkills(page);
  const chosen = skills[0];
  await enter(page, page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Library', exact: true }));
  await settled(page);
  await tabTo(page, page.getByLabel('Search name, description or path', { exact: true }));
  await page.keyboard.type(chosen.name);
  await enter(page, page.getByRole('button', { name: 'Apply filters', exact: true }));
  await settled(page);
  await enter(page, page.getByRole('link', { name: chosen.name, exact: true }).first());
  await settled(page);
  await expect(page.getByRole('heading', { name: chosen.name, level: 2 })).toBeVisible();

  // Źródło: dokładny link do rewizji, osiągnięty zakładką sekcji.
  await enter(page, page.getByRole('link', { name: 'Source & scope', exact: true }));
  await settled(page);
  const revision = await api<{ source: { url: string | null; path: string } }>(
    page, `${repoBase}/skills/${encodeURIComponent(chosen.skill_id)}/revisions/${chosen.revision_id}`);
  if (revision.source.url) {
    const href = await page.getByRole('link', { name: /Open exact source revision/ }).getAttribute('href');
    expect(href).toBe(revision.source.url);
  }

  // Przegląd: radio wybierane spacją, powód wpisywany, decyzja zapisywana Enterem.
  const drafts = await api<{ items: { proposal_id: string }[] }>(page, `${repoBase}/proposals?state=draft`);
  test.skip(drafts.items.length === 0, 'no draft proposal to review with the keyboard');
  await page.goto(`/proposals?org=${seed.org}&repo=${seed.repo}&proposal=${drafts.items[0].proposal_id}`);
  await settled(page);
  await tabTo(page, page.locator('input[name=decision][value=approve]'));
  await page.keyboard.press('Space');
  await tabTo(page, page.getByLabel('Reason for this decision', { exact: true }));
  await page.keyboard.type(unique('Reviewed the exact source, scope and revision with the keyboard'));
  await enter(page, page.getByRole('button', { name: 'Save decision', exact: true }));
  await expect(page.getByText(/Recorded: |Stale revision/).first()).toBeVisible({ timeout: 30000 });
});

test('focus lands in main on load, and the skip link is reachable and works', async ({ page }) => {
  await signIn(page, 'library');
  // Powłoka przenosi fokus do `#main` przy każdej nawigacji (app.tsx), więc użytkownik klawiatury
  // omija nawigację bez klikania. Link pomijania stoi przed `main` w DOM, więc dochodzi się do
  // niego wstecz; sprawdzamy, że istnieje i że naprawdę prowadzi do `#main`.
  await expect(page.locator('#main')).toBeFocused();
  const skip = page.getByRole('link', { name: 'Skip to content' });
  for (let step = 0; step < 40; step += 1) {
    if (await skip.evaluate(element => element === document.activeElement)) break;
    await page.keyboard.press('Shift+Tab');
  }
  await expect(skip).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Import', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
});
