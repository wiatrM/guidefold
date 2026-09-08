import { describe, expect, test, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiSkillRoute } from './CatalogRoutes';
import { ApiError } from '../api/client';
import type { Revision, SkillDetail } from '../api/decoders';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';

const detail: SkillDetail = {
  skill_id: 'urn:skill:meridian:atlas.identity:postgres-auth', name: 'postgres-auth',
  description: '[atlas.identity] Connect a service to the shared Postgres cluster.',
  scope: 'atlas.identity', owner: 'identity-team', source_layer: 'team', knowledge_layer: 'unclassified',
  source_status: 'active', publication_status: 'published', path: 'platforms/atlas/identity/postgres-auth/SKILL.md',
  content_sha256: 'sha-current', revision_id: 'rev-current', card_revision: 'card-current', package_digest: null, commit: 'c0ffee', updated_at: null,
  revisions: [
    { revision_id: 'rev-current', content_sha256: 'sha-current', card_revision: 'card-current', commit: 'c0ffee', import_id: 'im-1', created_at: '2026-09-01T09:00:00Z', source: 'import' },
    { revision_id: 'rev-old', content_sha256: 'sha-old', card_revision: null, commit: 'beef', import_id: 'im-0', created_at: '2026-08-01T09:00:00Z', source: 'import' },
  ],
};
const revision = (over: Partial<Revision> = {}): Revision => ({
  revision_id: 'rev-current', content_sha256: 'sha-current', card_revision: 'card-current', body: '# postgres-auth\n\nUse the shared role.',
  frontmatter: { name: 'postgres-auth' },
  source: { path: 'platforms/atlas/identity/postgres-auth/SKILL.md', commit: 'c0ffee', url: 'https://github.test/meridian/monorepo/blob/c0ffee/platforms/atlas/identity/postgres-auth/SKILL.md' },
  references: [{ path: 'schema.sql', sha256: 'sha-ref', size: 120, type: 'resource', required: true, available: true }],
  requires: ['urn:skill:meridian:atlas.identity:secrets'], refines: [],
  relations: [{ from: null, to: 'urn:skill:meridian:atlas.identity:secrets', type: 'requires', provenance: 'source', revision: null }],
  feedback: [{ judgment_id: 'j-1', verdict: 'helped', reason: 'Saved a lookup', source: 'adapter', task_id: 't-1', occurred_at: '2026-09-02T10:00:00Z' }],
  provenance: { origin: 'source', import_id: 'im-1', proposal_id: null },
  publication_status: 'published',
  ...over,
});
const source = (over = {}) => fakeSource({ getSkill: async () => detail, getRevision: async () => revision(), ...over });

describe('Skill route, hosted API, six states', () => {
  test('Empty: no selection sends the reader back to the library', () => {
    renderApi(ApiSkillRoute, fakeSource(), '');
    expect(screen.getByText('No skill selected')).toBeInTheDocument();
  });

  test('Loading: the summary is awaited before any body is claimed', () => {
    renderApi(ApiSkillRoute, fakeSource({ getSkill: () => new Promise(() => {}) }), 'skill=urn:a');
    expect(screen.getByText('Reading this skill')).toBeInTheDocument();
  });

  test('Partial: a missing required resource is named and blocks publication', async () => {
    renderApi(ApiSkillRoute, source({ getRevision: async () => revision({ references: [{ path: 'schema.sql', sha256: null, size: null, type: 'resource', required: true, available: false }] }) }), 'skill=urn:a');
    expect(await screen.findByText(/1 required package resources are missing/)).toBeInTheDocument();
  });

  test('Error: a missing revision is an error, never a newer body', async () => {
    const getRevision = vi.fn(async () => { throw new ApiError({ status: 404, code: 'revision_not_found', message: 'gone' }); });
    renderApi(ApiSkillRoute, source({ getRevision }), 'skill=urn:a&revision=rev-deleted');
    expect(await screen.findByText('Revision not available')).toBeInTheDocument();
    expect(screen.getByText('rev-deleted')).toBeInTheDocument();
    expect(screen.queryByText('Use the shared role.')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open the current revision' })).toBeInTheDocument();
  });

  test('Degraded: an unconfirmed membership blocks recording an assessment', async () => {
    renderApi(ApiSkillRoute, source(), 'skill=urn:a&tab=feedback', { access: { status: 'offline', me: null, checkedAt: 1 } });
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Record assessment' })).toBeDisabled();
  });

  test('Restricted: a denial shows no body', async () => {
    renderApi(ApiSkillRoute, fakeSource({ getSkill: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'no' }); } }), 'skill=urn:a');
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('postgres-auth')).not.toBeInTheDocument();
  });
});

describe('Skill route, revision, source and feedback', () => {
  test('the source link carries the exact host, file and commit', async () => {
    renderApi(ApiSkillRoute, source(), 'skill=urn:a&tab=source');
    const link = await screen.findByRole('link', { name: /Open exact source revision/ });
    expect(link).toHaveAttribute('href', 'https://github.test/meridian/monorepo/blob/c0ffee/platforms/atlas/identity/postgres-auth/SKILL.md');
  });

  test('a repository without a Git host shows the path instead of inventing a link', async () => {
    renderApi(ApiSkillRoute, source({ getRevision: async () => revision({ source: { path: 'a/SKILL.md', commit: 'c0ffee', url: null } }) }), 'skill=urn:a&tab=source');
    expect(await screen.findByText(/Source host not configured/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Open exact source revision/ })).not.toBeInTheDocument();
  });

  test('the exact SKILL.md download reports its bytes and declared SHA-256', async () => {
    const exact = '---\nname: postgres-auth\n---\nbody\n';
    const getRevisionRaw = vi.fn(async () => exact);
    const created: string[] = [];
    const originalCreate = URL.createObjectURL;
    URL.createObjectURL = vi.fn(() => { created.push('blob'); return 'blob:test'; }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as typeof URL.revokeObjectURL;
    try {
      renderApi(ApiSkillRoute, source({ getRevisionRaw }), 'skill=urn:a&tab=source');
      await userEvent.click(await screen.findByRole('button', { name: 'Download exact SKILL.md' }));
      expect(getRevisionRaw).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'urn:a', 'rev-current');
      expect(await screen.findByText('Downloaded ' + new TextEncoder().encode(exact).length + ' bytes. Declared SHA-256 sha-current.')).toBeInTheDocument();
      expect(created).toHaveLength(1);
    } finally { URL.createObjectURL = originalCreate; }
  });

  test('an inferred revision is marked Generated', async () => {
    renderApi(ApiSkillRoute, source({ getRevision: async () => revision({ provenance: { origin: 'inferred', import_id: null, proposal_id: 'p-1' } }) }), 'skill=urn:a');
    expect(await screen.findByText('Generated')).toBeInTheDocument();
    expect(screen.getByText(/inferred by a generator/)).toBeInTheDocument();
  });

  test('feedback posts a verdict with a reason and shows the judgment id', async () => {
    const sendFeedback = vi.fn(async () => ({ judgment_id: 'j-42' }));
    renderApi(ApiSkillRoute, source({ sendFeedback }), 'skill=urn:a&tab=feedback');
    await userEvent.click(await screen.findByRole('radio', { name: /Hindered/ }));
    await userEvent.type(screen.getByLabelText('What happened'), 'The role name is stale.');
    await userEvent.click(screen.getByRole('button', { name: 'Record assessment' }));
    expect(sendFeedback).toHaveBeenCalledWith(
      { org: 'meridian', repo: 'monorepo' }, 'urn:a', 'rev-current',
      { verdict: 'hindered', reason: 'The role name is stale.', task_id: undefined },
      expect.stringMatching(/^feedback:[0-9a-f]{8}$/),
    );
    expect(await screen.findByText(/Recorded as judgment j-42/)).toBeInTheDocument();
  });

  test('a member may record feedback', async () => {
    const sendFeedback = vi.fn(async () => ({ judgment_id: 'j-43' }));
    renderApi(ApiSkillRoute, source({ sendFeedback }), 'skill=urn:a&tab=feedback', { role: 'member' });
    await userEvent.type(await screen.findByLabelText('What happened'), 'Useful for the migration.');
    await userEvent.click(screen.getByRole('button', { name: 'Record assessment' }));
    expect(sendFeedback).toHaveBeenCalled();
  });

  test('a feedback failure keeps the typed reason', async () => {
    const sendFeedback = vi.fn(async () => { throw new ApiError({ status: 500, code: 'internal_error', message: 'no' }); });
    renderApi(ApiSkillRoute, source({ sendFeedback }), 'skill=urn:a&tab=feedback');
    await userEvent.type(await screen.findByLabelText('What happened'), 'Kept text');
    await userEvent.click(screen.getByRole('button', { name: 'Record assessment' }));
    expect(await screen.findByText(/was not recorded \(internal_error\)/)).toBeInTheDocument();
    expect(screen.getByLabelText('What happened')).toHaveValue('Kept text');
  });
});

describe('Skill route, identity and sections', () => {
  test('source status, source layer and knowledge layer are shown as the API states them, Unknown when absent', async () => {
    renderApi(ApiSkillRoute, source({ getSkill: async () => ({ ...detail, source_status: 'deprecated', knowledge_layer: null }) }), 'skill=urn:a');
    expect(await screen.findByText('deprecated')).toBeInTheDocument();
    const grid = screen.getByText('Knowledge layer').closest('dl')!;
    // Scope to the "Knowledge layer" row specifically: Provenance also renders
    // "Unknown" when absent, so a grid-wide query is ambiguous between the two.
    const knowledgeLayerRow = screen.getByText('Knowledge layer').closest('div')!;
    expect(within(knowledgeLayerRow).getByText('Unknown', { selector: 'dd' })).toBeInTheDocument();
    expect(within(grid).getByText('team')).toBeInTheDocument();
  });

  test('the publication badge tone follows the state and the label is always text', async () => {
    renderApi(ApiSkillRoute, source({ getSkill: async () => ({ ...detail, publication_status: 'needs_review' }) }), 'skill=urn:a');
    const badge = await screen.findByText('needs_review');
    expect(getComputedStyle(badge).color).toBe('var(--warning-ink)');
  });

  test('the section tabs are links; the current one carries aria-current and reads differently from a resting one', async () => {
    renderApi(ApiSkillRoute, source(), 'skill=urn:a&tab=content');
    const current = await screen.findByRole('link', { name: 'Content' });
    const resting = screen.getByRole('link', { name: 'Source & scope' });
    expect(current).toHaveAttribute('aria-current', 'page');
    expect(resting).not.toHaveAttribute('aria-current');
    expect(resting).toHaveAttribute('href', expect.stringContaining('tab=source'));
    expect(getComputedStyle(current).color).toBe('var(--system-ink)');
    expect(getComputedStyle(resting).color).not.toBe(getComputedStyle(current).color);
  });

  test('the Dependencies tab lists declared requires and refines as links, and names an empty list', async () => {
    renderApi(ApiSkillRoute, source({ getRevision: async () => revision({ refines: ['urn:skill:meridian:_root:postgres-production'] }) }), 'skill=urn:a&tab=dependencies');
    // `secrets` is listed under requires and again in the relations table, so two links exist.
    const links = await screen.findAllByRole('link', { name: 'urn:skill:meridian:atlas.identity:secrets' });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', expect.stringContaining('tab=content'));
    expect(screen.getByRole('link', { name: 'urn:skill:meridian:_root:postgres-production' })).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Other declared relations' })).toBeInTheDocument();
    expect(screen.queryByText('None declared in this revision.')).not.toBeInTheDocument();
  });
});
