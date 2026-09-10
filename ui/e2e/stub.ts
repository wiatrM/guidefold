/**
 * A stub management API served by `page.route`, shared by every browser spec that does not run
 * against the real service (`e2e/live/` does). The JSON is small inline sample data in the shapes
 * `docs/API-CONTRACT.md` declares; it proves the wiring of the seven hosted views, not the API.
 *
 * `scenario` bends the same routes into one of the six non-ready states (UX §7) so the state
 * matrix and the accessibility run exercise what the product shows when the API is empty, slow,
 * incomplete, failing, unconfirmed or refusing.
 */
import { expect, type Locator, type Page, type Route } from '@playwright/test';
import path from 'node:path';

export type Scenario = 'ready' | 'empty' | 'loading' | 'partial' | 'error' | 'degraded' | 'restricted';

export const org = { org_id: 'o-1', slug: 'meridian', name: 'Meridian Data' };
export const repoId = 'monorepo';
export const commit = '88e404561a9f6994cd870743bf858b9b0a616126';
export const gitHost = 'https://github.example.test/meridian/monorepo';
export const repoBase = '/orgs/' + org.slug + '/repos/' + repoId;
/** Delay for the loading scenario: long enough for every assertion, short enough not to leak. */
export const LOADING_DELAY_MS = 15000;

export interface StubSkill {
  id: string; name: string; scope: string; owner: string; layer: string; status: string;
  path: string; revision: string; description: string; body: string; requires: string[]; refines: string[];
}
const skill = (name: string, scope: string, owner: string, over: Partial<StubSkill> = {}): StubSkill => ({
  id: 'urn:skill:meridian:' + scope + ':' + name, name, scope, owner, layer: 'team', status: 'active',
  path: (scope === '_root' || scope === '_index' ? '.agents/skills/' : 'platforms/' + scope.split('.').join('/') + '/.agents/skills/') + name + '/SKILL.md',
  revision: 'sha-' + name, description: '[' + scope + '] ' + name.replace(/-/g, ' ') + '.', body: '# ' + name + '\n\nOne paragraph of guidance.\n',
  requires: [], refines: [], ...over,
});
export const nodes = [
  { id: '_root', owner: 'platform-engineering', paths: ['**'] },
  { id: 'atlas.identity', owner: 'identity-team', paths: ['platforms/atlas/identity/**'] },
  { id: 'atlas.identity.turnstile', owner: 'turnstile-team', paths: ['platforms/atlas/identity/turnstile/**'] },
  { id: 'forge.ontology', owner: 'ontology-team', paths: ['platforms/forge/ontology/**'] },
];
export const skills: StubSkill[] = [
  skill('adr-process', '_root', 'platform-engineering', { layer: 'org' }),
  skill('postgres-production', '_root', 'platform-engineering', { layer: 'org' }),
  skill('monorepo-conventions', '_root', 'platform-engineering', { layer: 'org' }),
  skill('rbac-policies', 'atlas.identity', 'identity-team', { layer: 'platform' }),
  skill('secrets', 'atlas.identity', 'identity-team', { layer: 'platform' }),
  skill('legacy-session-auth', 'atlas.identity', 'identity-team', { status: 'deprecated' }),
  skill('postgres-auth', 'atlas.identity.turnstile', 'turnstile-team', {
    description: '[atlas/identity/turnstile] Add or change authorization checks in the turnstile service.',
    body: '# Postgres-backed authorization in turnstile\n\n## When to use\n- change the auth middleware\n- alter the principals or decision_cache tables\n\n## Decision cache\nCache each allow decision for 30 seconds; never cache a deny.\n',
    requires: ['urn:skill:meridian:atlas.identity:rbac-policies', 'urn:skill:meridian:_root:postgres-production'],
    refines: ['urn:skill:meridian:_root:postgres-production'],
  }),
  skill('turnstile-oncall-runbook', 'atlas.identity.turnstile', 'turnstile-team'),
  skill('object-type-migrations', 'forge.ontology', 'ontology-team'),
  // A scope no node declares: the map names it as unmapped instead of hiding it.
  skill('hierarchy-index', '_index', 'platform-engineering', { layer: 'Unclassified' }),
];
export const chosen = skills.find(item => item.name === 'postgres-auth') as StubSkill;
export const raw = (item: StubSkill) => '---\nname: ' + item.name + '\nmetadata:\n  scope: ' + item.scope + '\n---\n' + item.body;
export const sourceUrl = (item: StubSkill) => gitHost + '/blob/' + commit + '/' + item.path;

const summary = (item: StubSkill) => ({
  skill_id: item.id, name: item.name, description: item.description,
  scope: item.scope, owner: item.owner, source_layer: item.layer,
  knowledge_layer: 'unclassified', source_status: item.status,
  publication_status: 'published', path: item.path,
  content_sha256: item.revision, revision_id: item.revision,
  package_digest: null, commit, updated_at: null,
});
const revisionOf = (item: StubSkill, scenario: Scenario) => ({
  revision_id: item.revision, content_sha256: item.revision, body: item.body,
  frontmatter: { name: item.name },
  source: { path: item.path, commit, url: sourceUrl(item) },
  references: scenario === 'partial'
    ? [{ path: 'schema.sql', sha256: null, size: null, type: 'resource', required: true, available: false }]
    : [],
  requires: item.requires, refines: item.refines,
  relations: item.requires.map(to => ({ from: item.id, to, type: 'requires', provenance: 'source', revision: null })),
  feedback: [],
  provenance: { origin: 'source', import_id: 'im-1', proposal_id: null },
  publication_status: 'published',
});
const counted = (pick: (item: StubSkill) => string) => {
  const counts = new Map<string, number>();
  for (const item of skills) counts.set(pick(item), (counts.get(pick(item)) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([value, count]) => ({ value, count }));
};
const facetValues = (field: string) => counted(
  field === 'owner' ? item => item.owner
    : field === 'layer' ? item => item.layer
      : field === 'status' ? item => item.status
        : item => item.scope,
);

export interface StubState { proposalState: string; publicationCalls: number; queueDecided: boolean; linkSuggested: boolean; generated: boolean; meCalls: number }

const importPlan = () => ({
  groups: [{
    group_id: 'g-1', kind: 'extraction', scope: chosen.scope, owner: chosen.owner,
    inputs: [chosen.path], n_inputs: 1, estimated_tokens: 500, estimated_calls: 1,
  }],
  limits: { max_files: 20, max_bytes: 1048576, max_groups: 5, max_proposals_per_group: 5, max_neighbours: 10, max_tokens: 1000, max_calls: 10, max_usd: 5 },
  estimated_usd_max: 0.75,
  estimated_calls: 1,
  groups_skipped: {},
  generator: { name: 'none', configured: false, generator: 'none', version: 'det-1', model: null },
});

export const usageReport = (scenario: Scenario, state: StubState) => scenario === 'empty' ? {
  window: { from: '2026-08-31T00:00:00Z', to: '2026-09-06T00:00:00Z', watermark: '2026-09-06T00:00:00Z' },
  coverage: { events_received: 0, dropped_reported: 0, oldest_lag_s: null, task_ids_present: false },
  totals: { exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, feedback: null },
  skills: [], queue: [], health: null,
} : {
  window: { from: '2026-08-31T00:00:00Z', to: '2026-09-06T00:00:00Z', watermark: '2026-09-06T00:00:00Z' },
  coverage: { events_received: 210, dropped_reported: scenario === 'partial' ? 9 : 0, oldest_lag_s: 4, task_ids_present: true },
  totals: {
    exposures: 40, loads_verified: 18, context_loaded: 16, context_unknown: 2,
    use_reported: 5, use_observed: 3, use_episodes: 4,
    feedback: { helped: 12, hindered: 4, mixed: 2, not_applicable: 0, unknown: 1, n: 19 },
    metrics: {
      tasks_started: 8, tasks_finished: 8, tasks_succeeded: 6, tasks_failed: 1, tasks_unknown: 1,
      harness_errors: 1, search_requests: 14, search_results: 42, search_errors: 1,
      use_requests: 9, ask_count: 2, input_tokens: 1200, output_tokens: 500, tool_calls: 18,
      latency_ms: 2400, latency_samples: 8, tasks_observed: true, cost_observed: true,
    },
  },
  skills: [
    { skill_id: chosen.id, revision: chosen.revision, exposures: 12, loads_verified: 6, context_loaded: 6, use_reported: 2, use_observed: 1, feedback: null, helped_ratio: { numerator: 2, denominator: 4, small_sample: true }, zero_loads: false },
    { skill_id: skills[1].id, revision: skills[1].revision, exposures: 8, loads_verified: 0, context_loaded: 0, use_reported: 0, use_observed: 0, feedback: null, helped_ratio: null, zero_loads: true },
  ],
  queue: state.queueDecided
    ? [{ item_id: 'q-1', skill_id: skills[1].id, revision: skills[1].revision, reason: 'zero_loads', since: '2026-09-01T00:00:00Z', evidence: { exposures: 8 }, decision: { action: 'reviewed', reason: 'Checked in Git.', at: '2026-09-06T10:00:00Z' } }]
    : [{ item_id: 'q-1', skill_id: skills[1].id, revision: skills[1].revision, reason: 'zero_loads', since: '2026-09-01T00:00:00Z', evidence: { exposures: 8 }, decision: null }],
  health: { adapters: [{ harness: 'claude', adapter_version: '0.4.1', capabilities: ['search', 'use'], last_seen_at: '2026-09-06T09:00:00Z', lag_s: 4, dropped: 0 }] },
};

export async function stubApi(page: Page, scenario: Scenario = 'ready'): Promise<StubState> {
  const state: StubState = { proposalState: 'draft', publicationCalls: 0, queueDecided: false, linkSuggested: false, generated: false, meCalls: 0 };
  const listed = scenario === 'empty' ? [] : skills;
  const proposal = () => ({
    proposal_id: 'p-1', kind: 'enrichment', state: state.proposalState,
    scope: chosen.scope, owner: chosen.owner, target_skill_id: chosen.id, target_revision_id: chosen.revision,
    sources: [{ path: chosen.path, sha256: chosen.revision, commit, lines: [1, 20] }],
    recipe: { version: 'det-1', generator: 'deterministic', model: null },
    candidate: { path: chosen.path, body: chosen.body + '\nAdded by the deterministic generator.\n', sha256: 'sha-candidate', frontmatter: {} },
    source_body: chosen.body,
    provenance: [
      { field: 'description', origin: 'source', source_ref: { path: chosen.path }, needs_confirmation: false },
      ...(scenario === 'partial' ? [{ field: 'steps', origin: 'inferred', source_ref: null, needs_confirmation: true }] : []),
    ],
    relations: [{ type: 'derived_from', to: chosen.id }],
    decision: null, expected_revision: chosen.revision, created_at: null,
    cost: { calls: 1, tokens_in: 800, tokens_out: 200, usd_certain: 0.004, usd_uncertain: 0 },
  });

  await page.route('**/api/v1/**', async (route: Route) => {
    const url = new URL(route.request().url());
    const at = decodeURIComponent(url.pathname).replace('/api/v1', '');
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status, contentType: 'application/json', headers: { 'Cache-Control': 'no-store', 'X-Request-Id': 'stub-1' },
      body: JSON.stringify(body),
    });
    const text = (body: string, type: string) => route.fulfill({
      status: 200, contentType: type, headers: { 'Cache-Control': 'no-store', 'X-Request-Id': 'stub-1' }, body,
    });
    const failure = (status: number, error: string, message: string) => json({ error, message, request_id: 'stub-1' }, status);

    // Identity and sign-in are always answered: the scenarios describe the organisation's data,
    // not the session, except `restricted`, whose account belongs to another organisation.
    if (at === '/me') {
      state.meCalls += 1;
      if (scenario === 'degraded' && state.meCalls > 1) return failure(503, 'unavailable', 'The identity service did not answer.');
      return json({
        user: { id: 'u-1', email: 'ada@meridian.test', name: 'Ada' },
        identities: [{ provider: 'github', created_at: null }],
        orgs: scenario === 'restricted'
          ? [{ org_id: 'o-9', slug: 'apex', name: 'Apex Holdings', role: 'member' }]
          : [{ org_id: org.org_id, slug: org.slug, name: org.name, role: 'owner' }],
        csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 },
        link_suggestions: state.linkSuggested ? [{ provider: 'google' }] : [],
      });
    }
    if (at === '/me/identities/link/start' && method === 'POST') return json({ login_url: '/api/v1/link-confirm/google' });
    if (at === '/link-confirm/google') return text('Linked.', 'text/plain');
    if (at === '/auth/providers') return json({
      mode: 'workos',
      providers: [
        { id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' },
        { id: 'github', label: 'GitHub', login_url: '/api/v1/auth/login/github' },
      ],
    });
    // The provider round trip: the real API redirects to the provider and back; the stub sends
    // the browser straight to `return_to`, the address the app asked to come back to.
    if (at.startsWith('/auth/login/')) return route.fulfill({ status: 302, headers: { Location: url.searchParams.get('return_to') ?? '/import' } });

    // Everything below belongs to an organisation or a repository and follows the scenario.
    if (scenario === 'error') return failure(500, 'internal', 'The stub is failing on purpose.');
    if (scenario === 'loading' && method === 'GET') await new Promise(resolve => setTimeout(resolve, LOADING_DELAY_MS));

    if (at === '/orgs') return json({ items: [{ ...org, my_role: 'owner', created_at: null, counts: { members: 1, repos: 1 } }] });
    if (at === '/orgs/' + org.slug) return json({ ...org, my_role: 'owner', created_at: null, counts: { members: 1, repos: 1 } });
    if (at === '/orgs/' + org.slug + '/members') return json({ items: scenario === 'empty' ? [] : [{ user_id: 'u-1', email: 'ada@meridian.test', name: 'Ada', role: 'owner', joined_at: null }], next_cursor: null });
    if (at === '/orgs/' + org.slug + '/installations') return json({ items: [], next_cursor: null });
    if (at === '/orgs/' + org.slug + '/audit') {
      if (scenario === 'empty') return json({ items: [], next_cursor: null });
      const cursor = url.searchParams.get('cursor');
      if (!cursor) return json({
        items: [{ at: '2026-09-05T12:00:00Z', actor: 'principal:u-1', action: 'member.invite', entity: 'urn:member:bob', revision: null, request_id: 'req-1' }],
        next_cursor: 'page-2',
      });
      return json({
        items: [{ at: '2026-09-06T08:00:00Z', actor: 'principal:u-1', action: 'repo.create', entity: repoId, revision: null, request_id: 'req-2' }],
        next_cursor: null,
      });
    }
    if (at === '/orgs/' + org.slug + '/repos') return json({ items: scenario === 'empty' ? [] : [{ repo_id: repoId, name: null, git_host_url: gitHost, created_at: null }], next_cursor: null });

    if (at === repoBase + '/imports') return json({ items: scenario === 'empty' ? [] : [{ import_id: 'im-1', state: scenario === 'partial' ? 'partial' : 'ready', commit, created_at: '2026-09-06T09:00:00Z' }], next_cursor: null });
    if (at === repoBase + '/imports/im-1/plan') return json(importPlan());
    if (at === repoBase + '/imports/im-1/proposals:generate' && method === 'POST') {
      state.generated = true;
      return json({ job_ids: ['j-gen-1'], plan: importPlan() });
    }
    if (at.startsWith(repoBase + '/imports/')) {
      const partial = scenario === 'partial';
      return json({
        import_id: 'im-1', state: partial ? 'partial' : 'ready', manifest_digest: commit, commit, complete: !partial,
        counts: { files: skills.length, accepted: partial ? skills.length - 2 : skills.length, omitted: partial ? 2 : 0, failed: 0, new_blobs: 0, reused_blobs: skills.length, skills: skills.length, documents: 0 },
        files: skills.slice(0, 3).map(item => ({ path: item.path, sha256: item.revision, size: item.body.length, kind: 'skill', status: 'accepted', reason: null, skill_id: item.id })),
        files_truncated: partial,
        jobs: [
          { job_id: 'j-1', kind: 'import.parse', state: 'done', attempts: 1, generation: 1, error: null, cost: null, started_at: null, finished_at: null },
          ...(state.generated ? [{ job_id: 'j-gen-1', kind: 'proposal.generate', state: 'skipped', attempts: 1, generation: 1, error: 'llm_not_configured', cost: null, started_at: null, finished_at: null }] : []),
        ],
        publication: { snapshot_id: 'snap-1', state: 'published', error: null },
        updated_at: null,
      });
    }

    if (at === repoBase + '/skills/facets') return json({ field: url.searchParams.get('field'), values: scenario === 'empty' ? [] : facetValues(url.searchParams.get('field') ?? 'scope'), next_cursor: null });
    if (at === repoBase + '/skills/facets/lookup') {
      const field = url.searchParams.get('field') ?? 'scope';
      const value = url.searchParams.get('value') ?? '';
      const count = facetValues(field).find(entry => entry.value === value)?.count ?? 0;
      return json({ field, value, count, available: count > 0 });
    }
    if (at === repoBase + '/skills') {
      const q = (url.searchParams.get('q') ?? '').toLowerCase();
      const scope = url.searchParams.get('scope');
      const owner = url.searchParams.get('owner');
      const items = listed.filter(item => (!q || item.name.includes(q) || item.description.toLowerCase().includes(q)) && (!scope || item.scope === scope) && (!owner || item.owner === owner));
      return json({ items: items.map(summary), next_cursor: null, snapshot_id: 'snap-1', schema_version: 'mgmt-1', filters: {} });
    }
    const revisionMatch = /^\/skills\/(.+)\/revisions\/([^/]+)(\/raw)?$/.exec(at.slice(repoBase.length));
    if (revisionMatch) {
      const item = skills.find(entry => entry.id === revisionMatch[1]);
      if (!item || revisionMatch[2] !== item.revision) return failure(404, 'revision_not_found', 'No such revision.');
      return revisionMatch[3] ? text(raw(item), 'text/markdown') : json(revisionOf(item, scenario));
    }
    if (/\/skills\/.+\/revisions\/[^/]+\/feedback$/.test(at) && method === 'POST') return json({ judgment_id: 'j-9', skill_id: chosen.id, revision: chosen.revision, verdict: 'helped', reason: 'ok', source: 'ui', task_id: null, occurred_at: null });
    if (at.startsWith(repoBase + '/skills/')) {
      const id = at.slice((repoBase + '/skills/').length);
      const item = skills.find(entry => entry.id === id);
      if (!item) return failure(404, 'skill_not_found', 'No such skill.');
      return json({ ...summary(item), revisions: [{ revision_id: item.revision, content_sha256: item.revision, commit, import_id: 'im-1', created_at: null, source: 'import' }] });
    }

    if (at === repoBase + '/map/repository') {
      if (scenario === 'empty') return json({ path: url.searchParams.get('path') ?? '', children: [], next_cursor: null });
      const prefix = url.searchParams.get('path') ? url.searchParams.get('path') + '/' : '';
      const children = new Map<string, { name: string; path: string; kind: string; skill_id: string | null; count: number | null }>();
      for (const item of skills) {
        if (!item.path.startsWith(prefix)) continue;
        const rest = item.path.slice(prefix.length);
        const cut = rest.indexOf('/');
        const name = cut === -1 ? rest : rest.slice(0, cut);
        const leaf = cut === -1;
        children.set(name, leaf
          ? { name, path: item.path, kind: 'skill', skill_id: item.id, count: null }
          : { name, path: prefix + name, kind: 'directory', skill_id: null, count: (children.get(name)?.count ?? 0) + 1 });
      }
      return json({ path: url.searchParams.get('path') ?? '', children: [...children.values()], next_cursor: null });
    }
    if (at === repoBase + '/map/scopes') {
      const scope = url.searchParams.get('scope');
      const node = nodes.find(entry => entry.id === scope);
      return json({
        scope: node ? { id: node.id, owner: node.owner, paths: node.paths, parent: null } : null,
        children: scenario === 'empty' ? [] : nodes.map(entry => ({ id: entry.id, owner: entry.owner, skills: listed.filter(item => item.scope === entry.id).length })),
        skills: listed.filter(item => !scope || item.scope === scope).slice(0, 5).map(item => ({ skill_id: item.id, name: item.name })),
        unmapped: listed.filter(item => !nodes.some(entry => entry.id === item.scope)).map(item => ({ skill_id: item.id, name: item.name })),
      });
    }
    if (at === repoBase + '/map/layers') return json({ layers: scenario === 'empty' ? [] : [{ layer: 'unclassified', count: skills.length }] });
    if (at === repoBase + '/map/relations') return json({
      items: chosen.requires.map(to => ({ from: chosen.id, to, type: 'requires', provenance: 'source', revision: null })),
      next_cursor: null, truncated: scenario === 'partial',
    });
    if (at.startsWith(repoBase + '/modules/')) {
      const scope = at.slice((repoBase + '/modules/').length);
      const inScope = listed.filter(item => item.scope === scope);
      return json({ scope, owner: inScope[0]?.owner ?? null, skills: inScope.map(summary), reading_order: inScope.map(item => item.id), shared: [], documents: [] });
    }

    if (at === repoBase + '/proposals') return json({
      items: scenario === 'empty' ? [] : [{ proposal_id: 'p-1', kind: 'enrichment', state: state.proposalState, scope: chosen.scope, owner: chosen.owner, target_skill_id: chosen.id, path: chosen.path, created_at: null }],
      next_cursor: null,
    });
    if (at === repoBase + '/proposals/p-1/decision' && method === 'POST') {
      state.proposalState = 'approved_for_export';
      return json({ proposal_id: 'p-1', state: 'approved_for_export', revision_id: 'rev-human', expected_revision: 'rev-human' });
    }
    if (at === repoBase + '/proposals/p-1/export' && method === 'POST') {
      state.proposalState = 'awaiting_git';
      return json({
        export_id: 'ex-1', proposal_id: 'p-1', state: 'awaiting_git', base_commit: commit,
        files: [{ path: chosen.path, sha256: 'sha-candidate', content: raw(chosen) }],
        patch: '--- a/' + chosen.path + '\n+++ b/' + chosen.path + '\n',
      });
    }
    if (at === repoBase + '/proposals/p-1/publication') {
      state.publicationCalls += 1;
      return json({ state: 'awaiting_git', published_revision_id: null, import_id: null, snapshot_id: null });
    }
    if (at === repoBase + '/proposals/p-1') return scenario === 'empty' ? failure(404, 'proposal_not_found', 'No such proposal.') : json(proposal());
    if (at === repoBase + '/snapshots') return json({
      items: scenario === 'empty' ? [] : [{
        publication_id: 'pub-1', snapshot_id: 'snap-1', state: 'active', active: true,
        import_id: 'im-1', job_id: 'j-publish-1', commit, n_skills: skills.length,
        builder_sha256: 'sha-builder', validation: { ok: true, findings: [] }, error: null,
        activated_at: null, created_at: '2026-09-06T09:00:00Z',
      }],
      next_cursor: null,
    });

    if (at === repoBase + '/usage/export') return text('skill_id,exposures\n' + chosen.id + ',12\n', 'text/csv');
    if (at.startsWith(repoBase + '/usage/queue/') && method === 'POST') {
      state.queueDecided = true;
      return json({ item_id: 'q-1' });
    }
    if (at === repoBase + '/usage') return json(usageReport(scenario, state));

    return failure(404, 'not_found', 'The stub has no route for ' + at);
  });
  return state;
}

export const query = (extra = '') => '?org=' + org.slug + '&repo=' + repoId + extra;

/** Opens a view and waits until every panel has finished its first read. */
export async function open(page: Page, view: string, extra = '') {
  await page.goto('/' + view + query(extra));
  await page.locator('main').waitFor();
  // Several panels may load at once, so wait for the count to reach zero rather than one element.
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
}

export async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let step = 0; step < 200; step += 1) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Target is not reachable through Tab: ' + await target.evaluate(element => element.outerHTML.slice(0, 120)));
}

export async function enter(page: Page, target: Locator) {
  await tabTo(page, target);
  await page.keyboard.press('Enter');
}

export async function axeViolations(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await page.addScriptTag({ path: path.resolve('node_modules/axe-core/axe.min.js') });
  return page.evaluate(async () => {
    const result = await (window as unknown as { axe: { run: (root: Document, options: unknown) => Promise<{ violations: { id: string; nodes: { target: string[] }[] }[] }> } })
      .axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
    return result.violations.map(violation => ({ id: violation.id, nodes: violation.nodes.map(node => node.target) }));
  });
}

export const noHorizontalScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
