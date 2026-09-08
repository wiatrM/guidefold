import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, test, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiProposalsRoute } from './ReviewRoutes';
import { ApiError } from '../api/client';
import type { ExportPayload, ProposalDetail, ProposalList, Publication, Snapshot } from '../api/decoders';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';

const list: ProposalList = {
  items: [{ proposal_id: 'p-1', kind: 'extraction', state: 'draft', scope: 'atlas.identity', owner: 'identity-team', target_skill_id: 'urn:a', path: 'platforms/atlas/SKILL.md', created_at: null }],
  next_cursor: null,
};
const detail = (over: Partial<ProposalDetail> = {}): ProposalDetail => ({
  proposal_id: 'p-1', kind: 'extraction', state: 'draft', scope: 'atlas.identity', owner: 'identity-team',
  target_skill_id: 'urn:a', target_revision_id: 'rev-1',
  sources: [{ path: 'platforms/atlas/README.md', sha256: 'sha-src', commit: 'c0ffee', lines: [10, 40] }],
  recipe: { version: 'det-1', generator: 'deterministic', model: null },
  candidate: { path: 'platforms/atlas/SKILL.md', body: '# postgres-auth\n\nUse the shared role.\n', sha256: 'sha-cand', frontmatter: {} },
  source_body: '# postgres-auth\n\nUse the old role.\n',
  provenance: [
    { field: 'description', origin: 'source', source_ref: { path: 'README.md', line: 12 }, needs_confirmation: false },
    { field: 'requires', origin: 'inferred', source_ref: null, needs_confirmation: true },
  ],
  relations: [{ type: 'derived_from', to: 'urn:a' }],
  decision: null, expected_revision: 'rev-1', created_at: null,
  cost: { calls: 2, tokens_in: 900, tokens_out: 300, usd_certain: 0.0123, usd_uncertain: 0 },
  ...over,
});
const exported: ExportPayload = {
  export_id: 'ex-9', proposal_id: 'p-1', state: 'awaiting_git', base_commit: 'c0ffee',
  files: [{ path: 'platforms/atlas/SKILL.md', sha256: 'sha-cand', content: '# postgres-auth\n' }],
  patch: '--- a\n+++ b\n',
};
const snapshot = (over: Partial<Snapshot> = {}): Snapshot => ({
  publication_id: 'pub-2', snapshot_id: 'snap-2', state: 'active', active: true,
  import_id: 'im-2', job_id: 'j-2', commit: 'c0ffee', n_skills: 27, builder_sha256: 'sha-b',
  validation: { ok: true, findings: [] }, error: null, activated_at: null, created_at: null, ...over,
});
const snapshots: Snapshot[] = [
  snapshot(),
  snapshot({ publication_id: 'pub-1', snapshot_id: 'snap-1', state: 'superseded', active: false, import_id: 'im-1', job_id: 'j-1', commit: 'beef', n_skills: 26 }),
];
const base = (over = {}) => fakeSource({
  listProposals: async () => list,
  getProposal: async () => detail(),
  listSnapshots: async () => snapshots,
  ...over,
});

describe('Proposals route, hosted API, six states', () => {
  test('Empty: no candidate is a valid result', async () => {
    renderApi(ApiProposalsRoute, fakeSource({ listProposals: async () => ({ items: [], next_cursor: null }) }));
    expect(await screen.findByText('No proposals to review')).toBeInTheDocument();
  });

  test('Loading: the queue is awaited', () => {
    renderApi(ApiProposalsRoute, fakeSource({ listProposals: () => new Promise(() => {}) }));
    expect(screen.getByText('Reading proposals')).toBeInTheDocument();
  });

  test('Partial: fields without a source fragment are marked as needing confirmation', async () => {
    renderApi(ApiProposalsRoute, base(), 'proposal=p-1');
    expect(await screen.findByText(/1 fields have no exact source fragment/)).toBeInTheDocument();
    expect(screen.getByText('Needs confirmation')).toBeInTheDocument();
  });

  test('Error: a refused decision keeps the reason and saves nothing', async () => {
    const decideProposal = vi.fn(async () => { throw new ApiError({ status: 422, code: 'invalid_candidate_change', message: 'no' }); });
    renderApi(ApiProposalsRoute, base({ decideProposal }), 'proposal=p-1');
    await userEvent.type(await screen.findByLabelText('Reason for this decision'), 'Scope checked.');
    await userEvent.click(screen.getByRole('button', { name: 'Save decision' }));
    expect(await screen.findByText(/refused \(invalid_candidate_change\)/)).toBeInTheDocument();
    expect(screen.getByLabelText('Reason for this decision')).toHaveValue('Scope checked.');
  });

  test('Degraded: an unconfirmed membership blocks the decision but keeps the diff readable', async () => {
    renderApi(ApiProposalsRoute, base(), 'proposal=p-1', { access: { status: 'offline', me: null, checkedAt: 1 } });
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save decision' })).toBeDisabled();
    expect(screen.getByText('Source to candidate')).toBeInTheDocument();
  });

  test('Restricted: a denial shows no source or candidate', async () => {
    renderApi(ApiProposalsRoute, fakeSource({ getProposal: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'no' }); } }), 'proposal=p-1');
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('Use the old role.')).not.toBeInTheDocument();
  });
});

describe('Proposals route, decision, conflict and export', () => {
  test('the queue filters round-trip through the URL', async () => {
    const { ctx } = renderApi(ApiProposalsRoute, base(), 'state=draft&kind=extraction&scope=atlas.identity');
    expect(await screen.findByLabelText('State')).toHaveValue('draft');
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    expect(ctx.go).toHaveBeenCalledWith('proposals', { state: 'draft', kind: 'extraction', scope: 'atlas.identity', cursor: null });
  });

  test('an approval carries the expected revision and one stable idempotency key', async () => {
    const decideProposal = vi.fn(async () => ({ proposal_id: 'p-1', state: 'approved_for_export' as const, revision_id: 'rev-2', expected_revision: 'rev-2' }));
    renderApi(ApiProposalsRoute, base({ decideProposal }), 'proposal=p-1');
    await userEvent.type(await screen.findByLabelText('Reason for this decision'), 'Matches the source.');
    await userEvent.click(screen.getByRole('button', { name: 'Save decision' }));
    await waitFor(() => expect(decideProposal).toHaveBeenCalled());
    const [, proposalId, input, key] = decideProposal.mock.calls[0] as unknown as [unknown, string, Record<string, unknown>, string];
    expect(proposalId).toBe('p-1');
    expect(input).toMatchObject({ decision: 'approve', reason: 'Matches the source.', expected_revision: 'rev-1' });
    expect(key).toMatch(/^decide:[0-9a-f]{8}$/);
    // The same unchanged draft replays under the same key instead of creating a second decision.
    await userEvent.click(screen.getByRole('button', { name: 'Save decision' }));
    await waitFor(() => expect(decideProposal).toHaveBeenCalledTimes(2));
    expect((decideProposal.mock.calls[1] as unknown as [unknown, string, unknown, string])[3]).toBe(key);
  });

  test('an edited candidate is sent as the body of the human revision', async () => {
    const decideProposal = vi.fn(async () => ({ proposal_id: 'p-1', state: 'approved_for_export' as const, revision_id: 'rev-2', expected_revision: 'rev-2' }));
    renderApi(ApiProposalsRoute, base({ decideProposal }), 'proposal=p-1');
    await userEvent.click(await screen.findByRole('radio', { name: /Approve an edited candidate/ }));
    const editor = screen.getByLabelText('Candidate body');
    await userEvent.clear(editor);
    await userEvent.type(editor, 'edited body');
    await userEvent.type(screen.getByLabelText('Reason for this decision'), 'Fixed the role name.');
    await userEvent.click(screen.getByRole('button', { name: 'Save decision' }));
    await waitFor(() => expect(decideProposal).toHaveBeenCalled());
    expect((decideProposal.mock.calls[0] as unknown as [unknown, string, Record<string, unknown>])[2]).toMatchObject({ decision: 'edit', candidate_body: 'edited body' });
  });

  test('409 stale_revision shows the current revision, keeps the text and requires a re-read', async () => {
    let calls = 0;
    const decideProposal = vi.fn(async () => {
      calls += 1;
      throw new ApiError({ status: 409, code: 'stale_revision', message: 'moved', details: { current_revision: 'rev-9' } });
    });
    const getProposal = vi.fn(async () => detail());
    renderApi(ApiProposalsRoute, base({ decideProposal, getProposal }), 'proposal=p-1');
    await userEvent.type(await screen.findByLabelText('Reason for this decision'), 'Read the source.');
    await userEvent.click(screen.getByRole('button', { name: 'Save decision' }));
    expect(await screen.findByText(/The source is now at revision rev-9/)).toBeInTheDocument();
    expect(screen.getByLabelText('Reason for this decision')).toHaveValue('Read the source.');
    expect(screen.getByRole('button', { name: 'Save decision' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Re-read the source' }));
    await waitFor(() => expect(getProposal).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: 'Save decision' })).toBeEnabled();
    expect(screen.getByLabelText('Reason for this decision')).toHaveValue('Read the source.');
    expect(calls).toBe(1);
  });

  test('export shows the files, the patch and the CLI apply command, then awaiting_git and published', async () => {
    let publicationState: Publication = { state: 'awaiting_git', published_revision_id: null, import_id: null, snapshot_id: null };
    const getProposalPublication = vi.fn(async () => publicationState);
    const exportProposal = vi.fn(async () => exported);
    URL.createObjectURL = vi.fn(() => 'blob:test') as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as typeof URL.revokeObjectURL;
    renderApi(ApiProposalsRoute, base({
      getProposal: async () => detail({ state: 'approved_for_export' }),
      exportProposal, getProposalPublication,
    }), 'proposal=p-1');
    await userEvent.click(await screen.findByRole('button', { name: 'Create export' }));
    expect(await screen.findByText('guidefold proposals apply ex-9 --write')).toBeInTheDocument();
    expect(screen.getAllByText('platforms/atlas/SKILL.md').length).toBeGreaterThan(1);
    expect(await screen.findByText(/Waiting for your Git review/)).toBeInTheDocument();
    expect(screen.getAllByText('awaiting_git').length).toBeGreaterThan(0);
    publicationState = { state: 'published', published_revision_id: 'rev-2', import_id: 'im-3', snapshot_id: 'snap-3' };
    await waitFor(() => expect(screen.getByText(/a snapshot was activated/)).toBeInTheDocument(), { timeout: 5000 });
  });

  test('a member sees the read-only notice and cannot decide, export or roll back', async () => {
    renderApi(ApiProposalsRoute, base(), 'proposal=p-1', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save decision' })).toBeDisabled();
    expect(screen.queryByText('Snapshots')).not.toBeInTheDocument();
  });

  test('an owner rolls back a snapshot only after giving a reason, and the reason is sent', async () => {
    const activateSnapshot = vi.fn(async () => snapshot({ ...snapshots[1], active: true, state: 'active' }));
    renderApi(ApiProposalsRoute, base({ activateSnapshot }), 'proposal=p-1');
    await userEvent.click(await screen.findByRole('button', { name: 'Roll back to this' }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm rollback' }));
    expect(await screen.findByText(/Give the reason for this rollback/)).toBeInTheDocument();
    expect(activateSnapshot).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText('Reason for this rollback'), 'Bad snapshot');
    await userEvent.click(screen.getByRole('button', { name: 'Confirm rollback' }));
    // §4.4 requires the reason in the request; collecting it and dropping it would be a 400.
    await waitFor(() => expect(activateSnapshot).toHaveBeenCalledWith(
      { org: 'meridian', repo: 'monorepo' }, 'snap-1', 'Bad snapshot', expect.stringMatching(/^activate:[0-9a-f]{8}$/),
    ));
  });

  test('a publication that failed states the finding, and offers no rollback without a snapshot', async () => {
    const failed = snapshot({
      publication_id: 'pub-3', snapshot_id: null, state: 'failed', active: false,
      error: 'missing_dependency', validation: { ok: false, findings: ['atlas.identity requires forge.pipelines, which is not published'] },
    });
    renderApi(ApiProposalsRoute, base({ listSnapshots: async () => [snapshots[0], failed] }), 'proposal=p-1');
    expect(await screen.findByText(/Failed: atlas.identity requires forge.pipelines, which is not published/)).toBeInTheDocument();
    expect(screen.getByText('No snapshot built')).toBeInTheDocument();
    expect(screen.getByText('Nothing to roll back to')).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: 'Roll back to this' })).toHaveLength(0);
  });

  test('an owner queues a publication for a named import', async () => {
    const publish = vi.fn(async () => ({ job_id: 'job-7' }));
    renderApi(ApiProposalsRoute, base({ publish }), 'proposal=p-1');
    await userEvent.type(await screen.findByLabelText('Publish an import'), 'im-3');
    await userEvent.click(screen.getByRole('button', { name: 'Queue publication' }));
    await waitFor(() => expect(publish).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, 'im-3', expect.any(String)));
    expect(await screen.findByText(/Publication job job-7 was queued/)).toBeInTheDocument();
  });
});

describe('Proposals route, detail presentation', () => {
  test('the lifecycle names four stages; only the current one carries aria-current and the human tone', async () => {
    renderApi(ApiProposalsRoute, base(), 'proposal=p-1');
    const lifecycle = await screen.findByRole('list', { name: 'Publication lifecycle' });
    const items = within(lifecycle).getAllByRole('listitem');
    expect(items.map(item => item.textContent)).toEqual(['draft', 'approved_for_export', 'awaiting_git', 'published']);
    expect(items[0]).toHaveAttribute('aria-current', 'step');
    expect(items[1]).not.toHaveAttribute('aria-current');
    expect(getComputedStyle(within(items[0]).getByText('draft')).color).toBe('var(--human-ink)');
    expect(getComputedStyle(within(items[1]).getByText('approved_for_export')).color).not.toBe('var(--human-ink)');
  });

  test('the candidate body preview scrolls instead of dumping the full body onto the page', async () => {
    renderApi(ApiProposalsRoute, base(), 'proposal=p-1');
    const summary = await screen.findByText('Read the candidate body');
    const preview = summary.parentElement!.querySelector('div')!;
    expect(getComputedStyle(preview).maxHeight).toBe('var(--raw-max-height)');
    expect(getComputedStyle(preview).overflow).toBe('auto');
  });

  test('the queue is one row per proposal with its kind, state and a link into the detail', async () => {
    renderApi(ApiProposalsRoute, base());
    const link = await screen.findByRole('link', { name: 'p-1' });
    expect(link).toHaveAttribute('href', expect.stringContaining('proposal=p-1'));
    const row = link.closest('tr')!;
    expect(within(row).getByText('extraction')).toBeInTheDocument();
    expect(within(row).getByText('draft')).toBeInTheDocument();
    expect(within(row).getByText('platforms/atlas/SKILL.md')).toBeInTheDocument();
  });

  test('the decision choice cards declare a hover treatment', () => {
    // jsdom does not compute :hover pseudo-class styles, so this reads the authored CSS
    // directly rather than simulating a hover and inspecting getComputedStyle.
    const css = readFileSync(resolve(process.cwd(), 'src/routes/ReviewRoutes.module.css'), 'utf8');
    expect(css).toMatch(/\.choice:hover\s*\{[^}]*background:\s*var\(--graphite-900\)/);
  });
});
