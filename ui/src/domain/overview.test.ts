import {describe, expect, test} from 'vitest';
import type {ImportStatus, Installation, ProposalSummary, SkillSummary, Usage, UsageSkill} from '../api/decoders';
import {emptyExecutionMetrics} from '../api/decoders';
import {adapterRows, coverageOf, funnelSteps, hasObservations, helpedShare, latestImport, libraryBreakdown, nextActions, openQueueCount, proposalsByState, topScopes, topSkills} from './overview';

const NOW = Date.parse('2026-09-12T12:00:00Z');
const usageSkill = (id: string, over: Partial<UsageSkill> = {}): UsageSkill => ({
  skill_id: id, revision: 'r', card_revision: null, content_sha256: null, scope: 'atlas', owner: null, harness: null,
  exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0,
  exposures_expanded: 0, loads_unlinked: 0, feedback: null, helped_ratio: null, zero_loads: false, ...over,
});
const usage = (over: Partial<Usage> = {}): Usage => ({
  window: {from: '2026-08-13T00:00:00Z', to: '2026-09-12T00:00:00Z', watermark: null},
  coverage: {events_received: 120, dropped_reported: 0, oldest_lag_s: 30, task_ids_present: true},
  totals: {exposures: 100, loads_verified: 40, context_loaded: 30, context_unknown: 10, use_reported: 5, use_observed: 3, use_episodes: 7, exposures_expanded: 35, loads_unlinked: 5, feedback: null, metrics: emptyExecutionMetrics},
  skills: [], queue: [], health: null, ...over,
});

describe('coverageOf', () => {
  test('no report or no coverage block is Unknown, not None', () => {
    expect(coverageOf(null).state).toBe('unknown');
    expect(coverageOf(usage({coverage: null})).state).toBe('unknown');
  });
  test('zero events is None; drops or an hour of lag is Lagging; otherwise Live', () => {
    expect(coverageOf(usage({coverage: {events_received: 0, dropped_reported: 0, oldest_lag_s: null, task_ids_present: false}})).state).toBe('none');
    expect(coverageOf(usage({coverage: {events_received: 9, dropped_reported: 2, oldest_lag_s: 1, task_ids_present: true}})).label).toBe('Lagging');
    expect(coverageOf(usage({coverage: {events_received: 9, dropped_reported: 0, oldest_lag_s: 7200, task_ids_present: true}})).detail).toContain('lag 120 min');
    expect(coverageOf(usage()).state).toBe('live');
  });
});

describe('helpedShare', () => {
  test('no feedback or no helped-or-hindered assessment is null, never 0%', () => {
    expect(helpedShare(usage())).toBeNull();
    expect(helpedShare(usage({totals: {...usage().totals, feedback: {helped: 0, hindered: 0, mixed: 3, not_applicable: 0, unknown: 0, n: 3}}}))).toBeNull();
  });
  test('below the floor the label is counts; from the floor up a rounded percent', () => {
    const small = helpedShare(usage({totals: {...usage().totals, feedback: {helped: 3, hindered: 1, mixed: 0, not_applicable: 0, unknown: 0, n: 4}}}))!;
    expect(small.percent).toBeNull();
    expect(small.label).toBe('3 of 4');
    const big = helpedShare(usage({totals: {...usage().totals, feedback: {helped: 15, hindered: 5, mixed: 0, not_applicable: 0, unknown: 0, n: 20}}}))!;
    expect(big.label).toBe('75%');
  });
});

describe('funnelSteps and observations', () => {
  test('five steps from the totals, with unlinked and unknown carried as notes', () => {
    const steps = funnelSteps(usage());
    expect(steps.map(step => step.value)).toEqual([100, 35, 40, 30, 7]);
    expect(steps[1].note).toContain('5 unlinked');
    expect(steps[3].note).toBe('10 unknown');
  });
  test('an assessment without any delivery is still an observation', () => {
    const quiet = usage({totals: {...usage().totals, exposures: 0, loads_verified: 0, use_reported: 0, use_observed: 0, use_episodes: 0, feedback: {helped: 1, hindered: 0, mixed: 0, not_applicable: 0, unknown: 0, n: 1}}});
    expect(hasObservations(quiet)).toBe(true);
    expect(hasObservations(null)).toBe(false);
  });
});

describe('topSkills and queue', () => {
  test('ranks by value, keeps the total and counts recommendations over every row', () => {
    const report = usage({skills: [
      usageSkill('urn:a', {exposures: 60, exposures_expanded: 40, loads_verified: 40, helped_ratio: {numerator: 18, denominator: 20, small_sample: false}}),
      usageSkill('urn:b', {exposures: 5}),
      usageSkill('urn:c'),
    ]});
    const top = topSkills(report, 2);
    expect(top.rows.map(row => row.skill.skill_id)).toEqual(['urn:a', 'urn:b']);
    expect(top.total).toBe(3);
    expect(top.recommendations.archive_candidate).toBe(1);
  });
  test('decided queue items do not count as open', () => {
    const report = usage({queue: [
      {item_id: 'q1', skill_id: 'urn:a', revision: null, reason: 'zero_loads', since: null, evidence: null, decision: null},
      {item_id: 'q2', skill_id: 'urn:b', revision: null, reason: 'zero_loads', since: null, evidence: null, decision: {action: 'reviewed', reason: null, at: null}},
    ]});
    expect(openQueueCount(report)).toBe(1);
    expect(openQueueCount(null)).toBeNull();
  });
});

describe('library', () => {
  const skill = (name: string, status: SkillSummary['publication_status']): SkillSummary => ({
    skill_id: 'urn:' + name, name, description: '', scope: 'atlas', owner: null, source_layer: null, knowledge_layer: null, source_status: null,
    publication_status: status, path: name + '/SKILL.md', content_sha256: null, revision_id: null, card_revision: null, package_digest: null, commit: null, updated_at: null,
  });
  test('counts by publication state and says when the page was not the whole catalogue', () => {
    const breakdown = libraryBreakdown([skill('a', 'published'), skill('b', 'draft'), skill('c', 'needs_review'), skill('d', 'archived')], 'more');
    expect(breakdown).toEqual({published: 1, draft: 1, needsReview: 1, other: 1, total: 4, truncated: true});
  });
  test('top scopes drop zero counts and sort by count then name', () => {
    expect(topScopes([{value: 'b', count: 2}, {value: 'a', count: 2}, {value: 'z', count: 0}, {value: 'c', count: 9}], 2)).toEqual([{scope: 'c', count: 9}, {scope: 'a', count: 2}]);
  });
});

describe('pipeline', () => {
  const proposal = (state: ProposalSummary['state']): ProposalSummary => ({proposal_id: state, kind: 'extraction', state, scope: null, owner: null, target_skill_id: null, path: null, created_at: null});
  const installation = (name: string, last: string | null, harness = 'claude'): Installation => ({installation_id: name, name, repo_id: null, scopes: [], harness, last_seen_at: last, adapter_version: '1', capabilities: null, created_at: null, token: null});
  test('proposals by state keep every state in order, zeros included', () => {
    const rows = proposalsByState([proposal('draft'), proposal('draft'), proposal('published')]);
    expect(rows.map(row => row.count)).toEqual([2, 0, 0, 1, 0, 0]);
  });
  test('adapter rows: never seen, silent for days, or reporting with the usage lag', () => {
    const rows = adapterRows([installation('cli', null), installation('ide', '2026-09-09T12:00:00Z'), installation('bot', '2026-09-12T11:00:00Z')], [{harness: 'claude', adapter_version: null, capabilities: null, last_seen_at: null, lag_s: 4, dropped: null}], NOW);
    expect(rows.map(row => row.state)).toEqual(['never', 'stale', 'ok']);
    expect(rows[1].label).toBe('Silent 3 d');
    expect(rows[2].label).toBe('Reporting, lag 4 s');
  });
  test('latest import is the newest created_at', () => {
    const imp = (id: string, at: string): ImportStatus => ({import_id: id, state: 'ready', manifest_digest: null, commit: null, complete: true, counts: null, files: [], files_truncated: false, jobs: [], publication: null, created_at: at, updated_at: null});
    expect(latestImport([imp('old', '2026-09-01'), imp('new', '2026-09-10')])?.import_id).toBe('new');
    expect(latestImport([])).toBeNull();
  });
});

describe('nextActions', () => {
  const base = {role: 'owner' as const, me: null, usage: null, proposals: null, imports: null, installations: null, skillsTotal: 3, now: NOW};
  test('an owner sees the queue, drafts and an unpublished import as human-tone actions', () => {
    const report = usage({queue: [{item_id: 'q1', skill_id: 'urn:a', revision: null, reason: 'source_changed', since: null, evidence: null, decision: null}]});
    const imports: ImportStatus[] = [{import_id: 'i', state: 'ready', manifest_digest: null, commit: null, complete: true, counts: null, files: [], files_truncated: false, jobs: [], publication: {snapshot_id: null, state: 'none', error: null}, created_at: '2026-09-10', updated_at: null}];
    const actions = nextActions({...base, usage: report, proposals: [{proposal_id: 'p', kind: 'extraction', state: 'draft', scope: null, owner: null, target_skill_id: null, path: null, created_at: null}], imports});
    expect(actions.map(action => action.kind)).toEqual(['queue', 'proposals', 'publish']);
    expect(actions[0].title).toBe('1 skill needs your decision');
  });
  test('a member never gets owner work; with skills to read they get the rating prompt', () => {
    const report = usage({queue: [{item_id: 'q1', skill_id: 'urn:a', revision: null, reason: 'source_changed', since: null, evidence: null, decision: null}]});
    const actions = nextActions({...base, role: 'member', usage: report});
    expect(actions.map(action => action.kind)).toEqual(['rate']);
  });
  test('no installations is an owner action; every adapter silent is one action, not one per adapter', () => {
    expect(nextActions({...base, installations: []}).map(action => action.kind)).toEqual(['adapter']);
    const silent = nextActions({...base, installations: [
      {installation_id: 'a', name: 'a', repo_id: null, scopes: [], harness: 'claude', last_seen_at: null, adapter_version: null, capabilities: null, created_at: null, token: null},
      {installation_id: 'b', name: 'b', repo_id: null, scopes: [], harness: 'codex', last_seen_at: '2026-09-01T00:00:00Z', adapter_version: null, capabilities: null, created_at: null, token: null},
    ]});
    expect(silent).toHaveLength(1);
    expect(silent[0].detail).toBe('a: never seen; b: silent 11 d.');
  });
  test('nothing waiting is an empty list, not a filler row', () => {
    expect(nextActions({...base, usage: usage(), proposals: [], imports: [{import_id: 'i', state: 'ready', manifest_digest: null, commit: null, complete: true, counts: null, files: [], files_truncated: false, jobs: [], publication: {snapshot_id: 's', state: 'published', error: null}, created_at: null, updated_at: null}], installations: [{installation_id: 'a', name: 'a', repo_id: null, scopes: [], harness: 'claude', last_seen_at: '2026-09-12T11:00:00Z', adapter_version: null, capabilities: null, created_at: null, token: null}]})).toEqual([]);
  });
});
