/**
 * Widok Import na realnym imporcie z zasiewu: liczniki plików, stan, ślad pochodzenia i joby.
 */
import { test, expect } from '@playwright/test';
import { anImportId, api, open, repoBase, signIn } from './live';

test('the seeded import reads back with its counts, digest, commit and jobs', async ({ page }) => {
  await signIn(page);
  const importId = await anImportId(page);
  const status = await api<{
    state: string; commit: string | null; manifest_digest: string | null; complete: boolean;
    counts: { accepted: number; omitted: number; failed: number } | null;
    jobs: { job_id: string; kind: string; state: string }[];
  }>(page, `${repoBase}/imports/${importId}`);

  await open(page, 'import', `&step=result&import_id=${importId}`);

  await expect(page.getByRole('heading', { name: 'Import result' })).toBeVisible();
  for (const label of ['Accepted', 'Omitted', 'Failed']) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText(status.state, { exact: true }).first()).toBeVisible();

  // Ślad pochodzenia: to, co serwer trzyma, i to, co widzi właściciel, muszą być tym samym.
  for (const label of ['Import', 'Manifest digest', 'Commit', 'Manifest completeness']) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  if (status.manifest_digest) {
    await expect(page.getByText(status.manifest_digest, { exact: false }).first()).toBeVisible();
  }
  if (status.commit) {
    await expect(page.getByText(status.commit, { exact: false }).first()).toBeVisible();
  }
  await expect(page.getByText(status.complete ? 'Complete scan' : 'Partial scan')).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Jobs', exact: true })).toBeVisible();
  expect(status.jobs.length, 'a finalised import must have recorded jobs').toBeGreaterThan(0);
  const jobs = page.getByRole('region', { name: 'Jobs for this import' });
  await expect(jobs).toBeVisible();
  await expect(jobs.getByText(status.jobs[0].kind, { exact: true }).first()).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Publication' })).toBeVisible();
});

test('the imports list links the newest import into the status step', async ({ page }) => {
  await signIn(page);
  await open(page, 'import', '&step=result');
  await expect(page.getByRole('heading', { name: 'Imports', exact: true })).toBeVisible();
  const table = page.getByRole('region', { name: 'Imports for this repository' });
  await expect(table).toBeVisible();
  await table.getByRole('link', { name: 'Read this import' }).first().click();
  await expect(page).toHaveURL(/import_id=/);
});
