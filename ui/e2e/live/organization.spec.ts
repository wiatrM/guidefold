/**
 * Organizacja: członkowie, instalacje i log audytu — trzy zakładki jednej trasy.
 */
import { test, expect } from '@playwright/test';
import { api, open, orgBase, seed, signIn } from './live';

test('the members tab lists the owner and offers the role control', async ({ page }) => {
  await signIn(page);
  await open(page, 'organization', '&tab=members');

  await expect(page.getByRole('heading', { name: 'Members', exact: true })).toBeVisible();
  const members = await api<{ items: { user_id: string; email: string; role: string }[] }>(page, `${orgBase}/members`);
  expect(members.items.length).toBeGreaterThan(0);
  const owner = members.items.find(member => member.role === 'owner') ?? members.items[0];

  const table = page.getByRole('region', { name: 'Members of this organization' });
  await expect(table).toBeVisible();
  // Komórka niesie e-mail i podpowiedź z nazwą, więc dopasowanie jest zawierające, nie dokładne.
  await expect(table.getByRole('rowheader', { name: new RegExp(owner.email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })).toBeVisible();
  await expect(page.getByLabel(`Role of ${owner.email}`)).toHaveValue(owner.role);
  await expect(page.getByRole('heading', { name: 'Invite a member' })).toBeVisible();
  await expect(page.getByLabel('E-mail address', { exact: true })).toBeVisible();
});

test('the integrations tab lists installations without ever showing a token', async ({ page }) => {
  await signIn(page);
  await open(page, 'organization', '&tab=integrations');

  await expect(page.getByRole('heading', { name: 'Installations' })).toBeVisible();
  const installations = await api<{ items: { installation_id: string; name: string; scopes: string[] }[] }>(page, `${orgBase}/installations`);
  if (installations.items.length > 0) {
    const table = page.getByRole('region', { name: 'Installations and adapter health' });
    await expect(table).toBeVisible();
    await expect(table.getByText(installations.items[0].name, { exact: true })).toBeVisible();
  } else {
    await expect(page.getByText('No installation')).toBeVisible();
  }
  // Sekret pokazywany jest raz, w odpowiedzi tworzącej; lista nigdy go nie niesie.
  for (const entry of installations.items as unknown as Record<string, unknown>[]) {
    expect(Object.keys(entry)).not.toContain('token');
  }
  await expect(page.getByRole('heading', { name: 'Create an installation' })).toBeVisible();
});

test('the audit tab shows every column of the recorded actions', async ({ page }) => {
  await signIn(page);
  await open(page, 'organization', '&tab=audit');

  await expect(page.getByRole('heading', { name: 'Audit log' })).toBeVisible();
  const audit = await api<{ items: { action: string; actor: string }[] }>(page, `${orgBase}/audit`);
  expect(audit.items.length, 'a seeded organisation must have audit rows').toBeGreaterThan(0);

  const table = page.getByRole('region', { name: 'Audit entries for this organization' });
  await expect(table).toBeVisible();
  for (const heading of ['At', 'Actor', 'Action', 'Entity', 'Revision', 'Request']) {
    await expect(table.getByRole('columnheader', { name: heading, exact: true })).toBeVisible();
  }
  await expect(table.getByRole('cell', { name: audit.items[0].action, exact: true }).first()).toBeVisible();
  expect(seed.org.length).toBeGreaterThan(0);
});
