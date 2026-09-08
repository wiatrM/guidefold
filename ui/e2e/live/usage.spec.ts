/**
 * Usage: kolejka właściciela przyjmuje decyzję i pokazuje ją zamiast pola wyboru.
 *
 * Powód jest unikalny na przebieg, bo klient wyprowadza `Idempotency-Key` z treści mutacji —
 * ten sam tekst powtórzyłby poprzednią operację zamiast wykonać nową.
 */
import { test, expect } from '@playwright/test';
import { api, open, orgBase, repoBase, signIn, unique } from './live';

interface QueueItem { item_id: string; skill_id: string; reason: string; decision: { action: string } | null }

test('the owner queue records a decision and closes the item', async ({ page }) => {
  await signIn(page);
  const usage = await api<{ queue: QueueItem[] }>(page, `${repoBase}/usage`);
  const open_ = usage.queue.filter(item => !item.decision);
  test.skip(open_.length === 0, 'this repository has no open review item to decide on');
  const item = open_[0];

  await open(page, 'usage');
  await expect(page.getByRole('heading', { name: 'Needs review' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Skills that need an owner decision' })).toBeVisible();

  // Selektor atrybutowy, nie `#id`: identyfikatory pozycji to UUID-y, a te mogą zaczynać się cyfrą.
  await page.locator(`[id="queue-action-${item.item_id}"]`).selectOption('reviewed');
  await page.locator(`[id="queue-reason-${item.item_id}"]`).fill(unique('Reviewed the source and kept the skill'));
  await page.getByRole('button', { name: 'Record decision', exact: true }).first().click();

  // Zamknięta pozycja znika z „Needs review": kolejka jest listą otwartych spraw, nie archiwum.
  // Trwałość decyzji potwierdza log audytu, a nie zniknięcie wiersza samo w sobie.
  await expect.poll(async () => {
    const after = await api<{ queue: QueueItem[] }>(page, `${repoBase}/usage`);
    const row = after.queue.find(entry => entry.item_id === item.item_id);
    return row ? (row.decision?.action ?? 'open') : 'closed';
  }, { timeout: 20000, message: 'the queue item stayed open after Record decision' })
    .toMatch(/^(closed|reviewed)$/);

  const audit = await api<{ items: { action: string; entity: string | null }[] }>(page, `${orgBase}/audit`);
  const recorded = audit.items.find(entry => entry.action.startsWith('usage.queue'));
  expect(recorded, 'no audit row records the owner decision').toBeTruthy();
});

test('unknown stays unknown: the report never prints a rate it cannot support', async ({ page }) => {
  await signIn(page);
  await open(page, 'usage');
  await expect(page.getByRole('heading', { name: 'Observation context' })).toBeVisible();
  for (const label of ['Exposed', 'Loaded', 'Context confirmed', 'Applied · reported / observed', 'Helped']) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  const report = await api<{ skills: { helped_ratio: { small_sample: boolean; numerator: number; denominator: number } | null }[] }>(page, `${repoBase}/usage`);
  const rated = report.skills.filter(row => row.helped_ratio);
  for (const row of rated) {
    // Poniżej progu wynik jest podawany jako licznik i mianownik, nigdy jako procent.
    if (row.helped_ratio!.small_sample) {
      await expect(page.getByText(`${row.helped_ratio!.numerator} of ${row.helped_ratio!.denominator}`).first()).toBeVisible();
    }
  }
  if (rated.length === 0) {
    await expect(page.getByText('Unknown').first()).toBeVisible();
  }
});
