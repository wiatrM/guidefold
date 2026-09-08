/**
 * Przegląd propozycji: decyzja właściciela, odmowa przy przesuniętym źródle (409) i eksport.
 *
 * `stale_revision` jest wywoływane przez UI, nie przez podrobione żądanie: formularz trzyma
 * `expected_revision` odczytany przy wejściu, a źródło przesuwa się w tle.
 */
import { test, expect, type Page } from '@playwright/test';
import { anImportId, api, moveTheSource, open, repoBase, settled, signIn, unique } from './live';

interface ProposalRow { proposal_id: string; state: string; kind: string; path: string }

/** Propozycja w stanie `draft`: z zasiewu, z listy, albo wygenerowana przez sam UI. */
async function aDraftProposal(page: Page): Promise<ProposalRow> {
  const listed = await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals?state=draft`);
  if (listed.items.length > 0) return listed.items[0];

  const importId = await anImportId(page);
  await open(page, 'import', `&step=result&import_id=${importId}`);
  await expect(page.getByRole('heading', { name: 'Generate proposals' })).toBeVisible();
  await page.getByRole('button', { name: 'Generate proposals', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Generation started' })).toBeVisible();

  await expect.poll(async () => {
    const again = await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals?state=draft`);
    return again.items.length;
  }, { timeout: 60000, message: 'the deterministic generator wrote no draft proposal' }).toBeGreaterThan(0);
  const again = await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals?state=draft`);
  return again.items[0];
}

test('a stale source refuses the decision, keeps the text, and the re-read decision is recorded', async ({ page }) => {
  await signIn(page);
  const proposal = await aDraftProposal(page);

  await open(page, 'proposals', `&proposal=${proposal.proposal_id}`);
  await expect(page.getByRole('heading', { name: 'Decision' })).toBeVisible();
  await expect(page.getByText('Expected revision')).toBeVisible();

  const reason = unique('Read the source, the scope and the revision before approving');
  await page.locator('input[name=decision][value=approve]').check();
  await page.getByLabel('Reason for this decision', { exact: true }).fill(reason);

  // Formularz trzyma już `expected_revision` odczytany przy wejściu. Teraz źródło naprawdę
  // się przesuwa — commit i `guidefold sync` — więc odmowa jest wymuszona, nie przypadkowa.
  const moved = await moveTheSource(`acceptance: move the source under proposal ${proposal.proposal_id}`, proposal.path);
  test.skip(!moved, 'no seeded checkout (GUIDEFOLD_E2E_TREE/CLI_HOME/TOKEN_FILE) to move the source with');

  await page.getByRole('button', { name: 'Save decision', exact: true }).click();
  await expect(page.getByText('Stale revision')).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('The source changed since this candidate was generated. Your text is kept, but the decision was not saved.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Re-read the source' })).toBeVisible();
  // Powód nie został wyczyszczony: praca recenzenta nie ginie przy odmowie.
  await expect(page.getByLabel('Reason for this decision', { exact: true })).toHaveValue(reason);
  const refused = await api<{ state: string }>(page, `${repoBase}/proposals/${proposal.proposal_id}`);
  expect(refused.state, 'a refused decision must not move the proposal').toBe('draft');

  // Ponowny odczyt i ta sama decyzja: teraz przechodzi.
  await page.getByRole('button', { name: 'Re-read the source' }).click();
  await settled(page);
  await page.locator('input[name=decision][value=approve]').check();
  await page.getByLabel('Reason for this decision', { exact: true }).fill(unique('Re-read the source and approved'));
  await page.getByRole('button', { name: 'Save decision', exact: true }).click();
  await expect(page.getByText(/Recorded: (approved_for_export|awaiting_git)/).first()).toBeVisible({ timeout: 30000 });

  const after = await api<{ state: string }>(page, `${repoBase}/proposals/${proposal.proposal_id}`);
  expect(['approved_for_export', 'awaiting_git']).toContain(after.state);
});

test('export writes files and a patch, and says it is not publication', async ({ page }) => {
  await signIn(page);
  const approved = await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals?state=approved_for_export`);
  const proposal = approved.items[0] ?? (await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals?state=awaiting_git`)).items[0];
  test.skip(!proposal, 'no approved proposal to export in this repository');

  await open(page, 'proposals', `&proposal=${proposal.proposal_id}`);
  await expect(page.getByRole('heading', { name: 'Export', exact: true })).toBeVisible();
  await expect(page.getByText('Export writes nothing to Git. It returns the exact files and a patch for you to apply and review in your own repository.')).toBeVisible();

  const button = page.locator('#export-patch');
  if (await button.count() > 0) {
    await button.click();
  }
  await expect(page.getByRole('region', { name: 'Files in this export' })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('Apply it from your checkout:')).toBeVisible();
  await expect(page.getByText(/guidefold proposals apply .* --write/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download patch' })).toBeVisible();

  // Eksport nie jest publikacją: panel publikacji nadal czeka na Git.
  await expect(page.getByRole('heading', { name: 'Publication' })).toBeVisible();
  await expect(page.getByText('Waiting for your Git review, merge and the next import. Nothing here is published yet.')).toBeVisible();
});

test('the queue lists candidates with their kind, state and target file', async ({ page }) => {
  await signIn(page);
  await open(page, 'proposals');
  const list = await api<{ items: ProposalRow[] }>(page, `${repoBase}/proposals`);
  if (list.items.length === 0) {
    await expect(page.getByText('No proposals to review')).toBeVisible();
    return;
  }
  const table = page.getByRole('region', { name: 'Proposals in this repository' });
  await expect(table).toBeVisible();
  await expect(table.getByRole('link', { name: list.items[0].proposal_id })).toBeVisible();
  await expect(page.getByLabel('State', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Kind', { exact: true })).toBeVisible();
});
