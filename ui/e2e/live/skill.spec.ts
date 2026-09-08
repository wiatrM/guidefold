/**
 * Widok Skill: dokładne bajty rewizji i link do dokładnego źródła.
 *
 * "Dokładne" jest tu sprawdzalne: pobrany plik jest hashowany i porównywany z deklarowanym
 * `content_sha256`, a nie tylko oglądany.
 */
import { test, expect } from '@playwright/test';
import { api, open, repoBase, seed, sha256Hex, signIn, someSkills } from './live';

test('the raw download is the exact revision, and its SHA-256 is the declared one', async ({ page }) => {
  await signIn(page);
  const skills = await someSkills(page);
  const chosen = skills.find(skill => skill.content_sha256) ?? skills[0];

  await open(page, 'library');
  await page.getByRole('link', { name: chosen.name, exact: true }).first().click();
  await expect(page).toHaveURL(/\/skill\?/);
  await expect(page.getByRole('heading', { name: chosen.name, level: 2 })).toBeVisible();

  await page.getByRole('link', { name: 'Source & scope', exact: true }).click();
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download exact SKILL.md' }).click();
  const download = await pending;
  const file = await download.path();
  expect(file, 'the download produced no file').toBeTruthy();
  const fs = await import('node:fs/promises');
  const bytes = await fs.readFile(file!);
  const digest = await sha256Hex(bytes);

  const declared = chosen.content_sha256 ?? (await api<{ content_sha256: string }>(page, `${repoBase}/skills/${encodeURIComponent(chosen.skill_id)}/revisions/${chosen.revision_id}`)).content_sha256;
  expect(digest, 'the downloaded bytes are not the revision the page declares').toBe(declared);
  await expect(page.getByText(`Downloaded ${bytes.length} bytes.`, { exact: false })).toBeVisible();
});

test('the source link points at the exact host, file and commit', async ({ page }) => {
  await signIn(page);
  const skills = await someSkills(page);
  const chosen = skills[0];
  const revisionId = chosen.revision_id;
  const revision = await api<{ source: { path: string; commit: string | null; url: string | null } }>(
    page, `${repoBase}/skills/${encodeURIComponent(chosen.skill_id)}/revisions/${revisionId}`);

  await open(page, 'skill', `&skill=${encodeURIComponent(chosen.skill_id)}&revision=${revisionId}&tab=source&from=library`);

  expect(revision.source.url, 'the seeded repository must carry a git_host_url').toBeTruthy();
  const link = page.getByRole('link', { name: /Open exact source revision/ });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', revision.source.url!);
  const href = (await link.getAttribute('href'))!;
  expect(href).toContain(revision.source.path);
  if (revision.source.commit) expect(href).toContain(revision.source.commit);
  if (seed.gitHostUrl) expect(href.startsWith(seed.gitHostUrl)).toBe(true);
  await expect(link).toHaveAttribute('rel', /noopener/);
});

test('a revision that does not exist is an error, never a newer body', async ({ page }) => {
  await signIn(page);
  const skills = await someSkills(page);
  const chosen = skills[0];
  const absent = 'f'.repeat(64);

  await open(page, 'skill', `&skill=${encodeURIComponent(chosen.skill_id)}&revision=${absent}&tab=content&from=library`);

  await expect(page.getByText('Revision not available')).toBeVisible();
  await expect(page.getByText('A newer revision is never shown in its place', { exact: false })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Revisions stored for this skill' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open the current revision' })).toBeVisible();
});
