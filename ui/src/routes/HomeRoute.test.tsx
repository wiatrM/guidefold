import {describe, expect, test} from 'vitest';
import {screen, within} from '@testing-library/react';
import {ApiHomeRoute} from './HomeRoute';
import {ApiError} from '../api/client';
import type {ImportStatus, Installation, ProposalSummary, SkillPage, Usage} from '../api/decoders';
import {emptyExecutionMetrics} from '../api/decoders';
import {fakeSource} from '../test/fakes';
import {renderApi} from '../test/apiRoute';

const emptyUsage: Usage = {
  window: {from: '2026-08-13T00:00:00Z', to: '2026-09-12T00:00:00Z', watermark: null},
  coverage: {events_received: 0, dropped_reported: 0, oldest_lag_s: null, task_ids_present: false},
  totals: {exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null, metrics: emptyExecutionMetrics},
  previous: null,
  skills: [], queue: [], health: null,
};
const usage: Usage = {
  ...emptyUsage,
  coverage: {events_received: 300, dropped_reported: 0, oldest_lag_s: 12, task_ids_present: true},
  totals: {exposures: 120, loads_verified: 44, context_loaded: 40, context_unknown: 4, use_reported: 11, use_observed: 7, use_episodes: 9, exposures_expanded: 38, loads_unlinked: 6, feedback: {helped: 18, hindered: 4, mixed: 1, not_applicable: 0, unknown: 0, n: 23}, metrics: emptyExecutionMetrics},
  previous: {
    window: {from: '2026-07-14T00:00:00Z', to: '2026-08-13T00:00:00Z'},
    totals: {exposures: 100, loads_verified: 40, context_loaded: 36, context_unknown: 4, use_reported: 9, use_observed: 6, use_episodes: 8, exposures_expanded: 34, loads_unlinked: 6, feedback: {helped: 15, hindered: 5, mixed: 1, not_applicable: 0, unknown: 0, n: 21}, metrics: emptyExecutionMetrics},
  },
  skills: [
    {skill_id: 'urn:skill:meridian:atlas.identity:postgres-auth', revision: 'rev-a', card_revision: null, content_sha256: null, scope: 'atlas.identity', owner: 'identity-team', harness: 'claude', exposures: 60, loads_verified: 30, context_loaded: 28, context_unknown: 2, use_reported: 6, use_observed: 4, use_episodes: 5, exposures_expanded: 30, loads_unlinked: 0, feedback: {helped: 18, hindered: 4, mixed: 1, not_applicable: 0, unknown: 0, n: 23}, helped_ratio: {numerator: 18, denominator: 22, small_sample: false}, zero_loads: false},
    {skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', revision: 'rev-b', card_revision: null, content_sha256: null, scope: 'forge.pipelines', owner: null, harness: null, exposures: 40, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null, helped_ratio: null, zero_loads: true},
  ],
  queue: [{item_id: 'q-1', skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', revision: 'rev-b', reason: 'zero_loads', since: '2026-09-01T00:00:00Z', evidence: null, decision: null}],
  health: {adapters: [{harness: 'claude', adapter_version: '0.4.1', capabilities: ['search'], last_seen_at: '2026-09-12T09:00:00Z', lag_s: 3, dropped: 0}]},
};
const skills: SkillPage = {
  items: ['a', 'b', 'c'].map((name, index) => ({skill_id: 'urn:' + name, name, description: '', scope: 'atlas', owner: null, source_layer: null, knowledge_layer: 'task' as const, source_status: null, publication_status: index === 2 ? 'draft' as const : 'published' as const, path: name + '/SKILL.md', content_sha256: null, revision_id: null, card_revision: null, package_digest: null, commit: null, updated_at: null})),
  next_cursor: null, snapshot_id: null, schema_version: null, filters: {},
};
const imports: ImportStatus[] = [{import_id: '80314462-3642-4a2a-9cee', state: 'ready', manifest_digest: null, commit: 'c0ffee', complete: true, counts: {files: 39, accepted: 38, omitted: 1, failed: 0, new_blobs: 39, reused_blobs: 0, skills: 26, documents: 12}, files: [], files_truncated: false, jobs: [], publication: {snapshot_id: 's-1', state: 'published', error: null}, created_at: '2026-09-12T09:00:00Z', updated_at: null}];
const proposals: ProposalSummary[] = [{proposal_id: 'p-1', kind: 'extraction', state: 'draft', scope: 'atlas', owner: null, target_skill_id: null, path: null, created_at: null, decision: null}];
const installations: Installation[] = [{installation_id: 'i-1', name: 'claude-code', repo_id: null, scopes: ['search'], harness: 'claude', last_seen_at: new Date().toISOString(), adapter_version: '0.4.1', capabilities: null, created_at: null, token: null}];

const source = (over: Parameters<typeof fakeSource>[0] = {}) => fakeSource({
  getUsage: async () => usage,
  listSkills: async () => skills,
  getMapLayers: async () => ({layers: [{layer: 'task', count: 2}, {layer: 'unclassified', count: 1}]}),
  getFacets: async () => ({field: 'scope', values: [{value: 'atlas', count: 2}, {value: 'forge', count: 1}], next_cursor: null}),
  listProposals: async () => ({items: proposals, next_cursor: null}),
  listImports: async () => imports,
  listInstallations: async () => installations,
  getAudit: async () => ({items: [{at: '2026-09-12T09:00:00Z', actor: 'principal:u1', action: 'import.create', entity: '80314462', revision: null, request_id: 'req-1'}], next_cursor: null}),
  ...over,
});

describe('Home route', () => {
  test('shows the four key numbers as counts and links each to its source view', async () => {
    renderApi(ApiHomeRoute, source());
    const kpis = await screen.findByRole('region', {name: 'Key numbers'});
    expect(within(kpis).getAllByText('Published skills').length).toBeGreaterThan(0);
    expect(within(kpis).getByText('2')).toBeInTheDocument();
    expect(within(kpis).getByText('1 draft · 0 needs review')).toBeInTheDocument();
    expect(within(kpis).getByText('120')).toBeInTheDocument();
    expect(within(kpis).getByText('82%')).toBeInTheDocument();
    expect(within(kpis).getByRole('link', {name: /Published skills/})).toHaveAttribute('href', expect.stringContaining('status=published'));
  });

  test('1.3.0: trend badges compare against usage.previous.totals; loads gets an inline delta', async () => {
    renderApi(ApiHomeRoute, source());
    const kpis = await screen.findByRole('region', {name: 'Key numbers'});
    expect(within(kpis).getByText('+20%')).toBeInTheDocument(); // exposures 120 vs previous 100
    // Helped share is a difference in percentage points, never a relative percent of a percent:
    // 75% -> 82% is "+7 pp" (a reader would misread "+9%" as nine points, not seven).
    expect(within(kpis).getByText('+7 pp')).toBeInTheDocument();
    expect(within(kpis).getByText(/44 verified loads \(\+10% from the equal-length window before\)/)).toBeInTheDocument();
    // Needs review has no previous-window concept at all: always "No previous window".
    expect(within(kpis).getAllByText('No previous window').length).toBeGreaterThan(0);
  });

  test('no previous window is "No previous window" everywhere, never a fake percent or point delta', async () => {
    renderApi(ApiHomeRoute, source({getUsage: async () => ({...usage, previous: null})}));
    const kpis = await screen.findByRole('region', {name: 'Key numbers'});
    expect(within(kpis).queryByText(/^[+-]\d+\s?(%|pp)$/)).not.toBeInTheDocument();
    expect(within(kpis).getAllByText('No previous window').length).toBeGreaterThan(0);
    expect(screen.getByText(/No previous window was reported for this one, so no trend is shown\./)).toBeInTheDocument();
  });

  test('a previous window of exactly zero exposures is not Unknown: growth from it reads "new"', async () => {
    const grewFromZero: Usage = {...usage, totals: {...usage.totals, exposures: 40}, previous: {...usage.previous!, totals: {...usage.previous!.totals, exposures: 0}}};
    renderApi(ApiHomeRoute, source({getUsage: async () => grewFromZero}));
    const kpis = await screen.findByRole('region', {name: 'Key numbers'});
    expect(within(kpis).getByText('new')).toBeInTheDocument();
  });

  test('zero exposures in both windows reads "no change", not Unknown', async () => {
    const stayedAtZero: Usage = {...usage, totals: {...usage.totals, exposures: 0}, previous: {...usage.previous!, totals: {...usage.previous!.totals, exposures: 0}}};
    renderApi(ApiHomeRoute, source({getUsage: async () => stayedAtZero}));
    const kpis = await screen.findByRole('region', {name: 'Key numbers'});
    expect(within(kpis).getByText('no change')).toBeInTheDocument();
  });

  test('an owner sees the queue and the draft proposal as next actions, in that order', async () => {
    renderApi(ApiHomeRoute, source());
    const list = await screen.findByRole('list', {name: 'Next actions'});
    const items = within(list).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('1 skill needs your decision');
    expect(items[1]).toHaveTextContent('1 proposal waits for a decision');
    expect(within(items[0]).getByRole('link')).toHaveAttribute('href', expect.stringContaining('/usage'));
  });

  test('a member gets no owner work but reads their own scoped audit log (1.3.0)', async () => {
    renderApi(ApiHomeRoute, source(), '', {role: 'member'});
    const list = await screen.findByRole('list', {name: 'Next actions'});
    expect(within(list).queryByText(/needs your decision/)).not.toBeInTheDocument();
    expect(within(list).getByText('Rate a skill you used')).toBeInTheDocument();
    expect(await screen.findByText('Recent activity')).toBeInTheDocument();
    expect(screen.getByText('Your actions')).toBeInTheDocument();
    // The eyebrow and the card description both say whose activity this is, in different words.
    expect(screen.getByText('Last entries of your own actions in this organization')).toBeInTheDocument();
    expect(screen.queryByText('Last entries of the organization audit log')).not.toBeInTheDocument();
  });

  test('an owner reads the whole organization audit log, worded accordingly', async () => {
    renderApi(ApiHomeRoute, source());
    expect(await screen.findByText('Recent activity')).toBeInTheDocument();
    expect(screen.getByText('Organization audit')).toBeInTheDocument();
    expect(screen.getByText('Last entries of the organization audit log')).toBeInTheDocument();
    expect(screen.queryByText('Last entries of your own actions in this organization')).not.toBeInTheDocument();
  });

  test('"Your decisions" folds away when nothing I decided is in this repository', async () => {
    renderApi(ApiHomeRoute, source());
    await screen.findByRole('region', {name: 'Key numbers'});
    expect(screen.queryByText('Your decisions')).not.toBeInTheDocument();
  });

  test('"Your decisions" lists proposals and queue items I decided, newest first (1.3.0)', async () => {
    const decidedProposals: ProposalSummary[] = [
      {proposal_id: 'p-1', kind: 'extraction', state: 'approved_for_export', scope: 'atlas', owner: null, target_skill_id: 'urn:skill:meridian:atlas:demo', path: null, created_at: null, decision: {decision: 'approve', actor: 'u1', at: '2026-09-10T00:00:00Z'}},
      {proposal_id: 'p-2', kind: 'extraction', state: 'rejected', scope: 'atlas', owner: null, target_skill_id: 'urn:skill:meridian:atlas:other', path: null, created_at: null, decision: {decision: 'reject', actor: 'someone-else', at: '2026-09-12T00:00:00Z'}},
    ];
    const decidedUsage: Usage = {...usage, queue: [{...usage.queue[0], decision: {action: 'reviewed', reason: 'ok', at: '2026-09-11T00:00:00Z', actor: 'u1'}}]};
    renderApi(ApiHomeRoute, source({listProposals: async () => ({items: decidedProposals, next_cursor: null}), getUsage: async () => decidedUsage}));
    expect(await screen.findByText('Your decisions')).toBeInTheDocument();
    // p-2 was decided by someone else, so only two of the three decided rows are mine.
    expect(screen.getByText('2 decisions you recorded')).toBeInTheDocument();
    const list = screen.getByRole('list', {name: 'Your most recent decisions'});
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    // The queue decision (2026-09-11) is newer than the proposal decision (2026-09-10).
    expect(items[0]).toHaveTextContent('pipeline-testing');
    expect(items[1]).toHaveTextContent('demo');
  });

  test('top skills carry the four gates as text badges and the recommendation counts', async () => {
    renderApi(ApiHomeRoute, source());
    const table = await screen.findByRole('region', {name: 'Top skills with their four gates'});
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('postgres-auth');
    expect(rows[0]).toHaveTextContent('Promote up');
    expect(rows[1]).toHaveTextContent('Review');
    expect(rows[1]).toHaveTextContent('Published but never loaded');
    expect(screen.getByRole('list', {name: 'Recommendations over every observed skill'})).toHaveTextContent('Promote up1');
  });

  test('no telemetry is one compact state with the adapter action, and no chart or rate', async () => {
    renderApi(ApiHomeRoute, source({getUsage: async () => emptyUsage, listProposals: async () => ({items: [], next_cursor: null})}));
    expect(await screen.findByText('No telemetry in the last 30d')).toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByRole('img', {name: /Delivery funnel/})).not.toBeInTheDocument();
    expect(screen.getByText('No adapter events')).toBeInTheDocument();
    expect(screen.getByText('Unknown', {selector: '[data-slot=statistic] dd, dd'})).toBeInTheDocument();
  });

  test('the window comes from the address and both usage links keep it', async () => {
    renderApi(ApiHomeRoute, source(), '?window=7d');
    expect(await screen.findByRole('link', {name: '7d'})).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('link', {name: /Open in Usage/})).toHaveAttribute('href', expect.stringContaining('window=7d'));
    expect(screen.getAllByText('Exposures, 7d').length).toBeGreaterThan(0);
  });

  test('one failed block is a partial notice, not a broken page', async () => {
    renderApi(ApiHomeRoute, source({listProposals: async () => { throw new ApiError({status: 503, code: 'unavailable', message: 'down'}); }}));
    expect(await screen.findByText(/1 block could not be read/)).toBeInTheDocument();
    expect(screen.getByText('Proposals could not be read.')).toBeInTheDocument();
    expect(screen.getByRole('region', {name: 'Key numbers'})).toBeInTheDocument();
  });

  test('no repository is the one next step, not eight empty cards', async () => {
    renderApi(ApiHomeRoute, source(), '', {repo: null});
    expect(await screen.findByRole('heading', {level: 2, name: 'Choose a repository'})).toBeInTheDocument();
    expect(screen.queryByText('Published skills')).not.toBeInTheDocument();
  });
});
