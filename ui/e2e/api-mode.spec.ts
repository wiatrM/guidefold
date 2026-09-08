/**
 * API mode against a stub management API served by page.route.
 *
 * The JSON here is derived from the public Meridian fixture (27 skills) so the shapes are real
 * without a running Go service. It proves the wiring of the seven hosted views, not the API.
 */
import { test, expect, type Page, type Locator, type Route } from '@playwright/test';
import path from 'node:path';
import fixture from '../src/data/fixture.json' with { type: 'json' };

type Skill = typeof fixture.skills[number];
const skills = fixture.skills as Skill[];
const chosen = skills.find(skill => skill.name === 'postgres-auth') as Skill;
const gitHost = 'https://github.example.test/meridian/monorepo';
const sourceUrl = (skill: Skill) => gitHost + '/blob/' + fixture.commit + '/' + skill.path;

const summary = (skill: Skill) => ({
  skill_id: skill.id, name: skill.name, description: skill.description,
  scope: skill.scope, owner: skill.owner, source_layer: skill.sourceLayer,
  knowledge_layer: 'unclassified', source_status: skill.sourceStatus,
  publication_status: 'published', path: skill.path,
  content_sha256: skill.revision, revision_id: skill.revision,
  package_digest: null, commit: fixture.commit, updated_at: null,
});
const revisionOf = (skill: Skill) => ({
  revision_id: skill.revision, content_sha256: skill.revision, body: skill.body,
  frontmatter: { name: skill.name },
  source: { path: skill.path, commit: fixture.commit, url: sourceUrl(skill) },
  references: skill.references.map(reference => ({ path: reference, sha256: null, size: null, type: 'reference', required: false, available: true })),
  requires: skill.requires, refines: skill.refines,
  relations: skill.requires.map(to => ({ from: skill.id, to, type: 'requires', provenance: 'source', revision: null })),
  feedback: [],
  provenance: { origin: 'source', import_id: 'im-1', proposal_id: null },
  publication_status: 'published',
});
const counted = (pick: (skill: Skill) => string) => {
  const counts = new Map<string, number>();
  for (const skill of skills) counts.set(pick(skill), (counts.get(pick(skill)) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([value, count]) => ({ value, count }));
};
const facetValues = (field: string) => counted(
  field === 'owner' ? skill => skill.owner
    : field === 'layer' ? skill => skill.sourceLayer
      : field === 'status' ? skill => skill.sourceStatus
        : skill => skill.scope,
);

interface StubState { proposalState: string; publicationCalls: number; queueDecided: boolean; linkSuggested: boolean; generated: boolean }

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

async function stubApi(page: Page): Promise<StubState> {
  const state: StubState = { proposalState: 'draft', publicationCalls: 0, queueDecided: false, linkSuggested: false, generated: false };
  const proposal = () => ({
    proposal_id: 'p-1', kind: 'enrichment', state: state.proposalState,
    scope: chosen.scope, owner: chosen.owner, target_skill_id: chosen.id, target_revision_id: chosen.revision,
    sources: [{ path: chosen.path, sha256: chosen.revision, commit: fixture.commit, lines: [1, 20] }],
    recipe: { version: 'det-1', generator: 'deterministic', model: null },
    candidate: { path: chosen.path, body: chosen.body + '\n\nAdded by the deterministic generator.\n', sha256: 'sha-candidate', frontmatter: {} },
    source_body: chosen.body,
    provenance: [
      { field: 'description', origin: 'source', source_ref: { path: chosen.path }, needs_confirmation: false },
      { field: 'steps', origin: 'inferred', source_ref: null, needs_confirmation: true },
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
    const repo = '/orgs/meridian/repos/monorepo';

    if (at === '/me') return json({
      user: { id: 'u-1', email: 'ada@meridian.test', name: 'Ada' },
      identities: [{ provider: 'github', created_at: null }],
      orgs: [{ org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', role: 'owner' }],
      csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 },
      link_suggestions: state.linkSuggested ? [{ provider: 'google' }] : [],
    });
    if (at === '/me/identities/link/start' && method === 'POST') return json({ login_url: '/api/v1/link-confirm/google' });
    if (at === '/link-confirm/google') return text('Linked.', 'text/plain');
    if (at === '/auth/providers') return json({
      mode: 'workos',
      providers: [
        { id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' },
        { id: 'github', label: 'GitHub', login_url: '/api/v1/auth/login/github' },
      ],
    });
    if (at === '/orgs') return json({ orgs: [{ org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', my_role: 'owner', created_at: null, counts: { members: 1, repos: 1 } }] });
    if (at === '/orgs/meridian') return json({ org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', my_role: 'owner', created_at: null, counts: { members: 1, repos: 1 } });
    if (at === '/orgs/meridian/members') return json({ items: [{ user_id: 'u-1', email: 'ada@meridian.test', name: 'Ada', role: 'owner', joined_at: null }], next_cursor: null });
    if (at === '/orgs/meridian/installations') return json({ items: [], next_cursor: null });
    if (at === '/orgs/meridian/audit') {
      const cursor = url.searchParams.get('cursor');
      if (!cursor) return json({
        items: [{ at: '2026-09-05T12:00:00Z', actor: 'principal:u-1', action: 'member.invite', entity: 'urn:member:bob', revision: null, request_id: 'req-1' }],
        next_cursor: 'page-2',
      });
      return json({
        items: [{ at: '2026-09-06T08:00:00Z', actor: 'principal:u-1', action: 'repo.create', entity: 'monorepo', revision: null, request_id: 'req-2' }],
        next_cursor: null,
      });
    }
    if (at === repo + '/repos' || at === '/orgs/meridian/repos') return json({ items: [{ repo_id: 'monorepo', name: 'monorepo', git_host_url: gitHost, created_at: null, created: false }], next_cursor: null });
    if (at === repo + '/imports') return json({
      items: [{
        import_id: 'im-1', state: 'ready', manifest_digest: fixture.commit, commit: fixture.commit, complete: true,
        counts: { files: skills.length, accepted: skills.length, omitted: 0, failed: 0, new_blobs: 0, reused_blobs: skills.length, skills: skills.length, documents: 0 },
        files: [], files_truncated: true, jobs: [], publication: { snapshot_id: 'snap-1', state: 'published', error: null },
        created_at: null, updated_at: null,
      }],
      next_cursor: null,
    });
    if (at === repo + '/imports/im-1/plan') return json(importPlan());
    if (at === repo + '/imports/im-1/proposals:generate' && method === 'POST') {
      state.generated = true;
      return json({ job_ids: ['j-gen-1'], plan: importPlan() });
    }
    if (at.startsWith(repo + '/imports/')) return json({
      import_id: 'im-1', state: 'ready', manifest_digest: fixture.commit, commit: fixture.commit, complete: true,
      counts: { files: skills.length, accepted: skills.length, omitted: 0, failed: 0, new_blobs: 0, reused_blobs: skills.length, skills: skills.length, documents: 0 },
      files: skills.slice(0, 3).map(skill => ({ path: skill.path, sha256: skill.revision, size: skill.bytes, kind: 'skill', status: 'accepted', reason: null, skill_id: skill.id })),
      jobs: [
        { job_id: 'j-1', kind: 'import.parse', state: 'done', attempts: 1, generation: 1, error: null, cost: null, started_at: null, finished_at: null },
        ...(state.generated ? [{ job_id: 'j-gen-1', kind: 'proposal.generate', state: 'skipped', attempts: 1, generation: 1, error: 'llm_not_configured', cost: null, started_at: null, finished_at: null }] : []),
      ],
      publication: { snapshot_id: 'snap-1', state: 'published', error: null },
      created_at: null, updated_at: null,
    });

    if (at === repo + '/skills/facets') return json({ field: url.searchParams.get('field') ?? 'scope', values: facetValues(url.searchParams.get('field') ?? 'scope'), next_cursor: null });
    if (at === repo + '/skills/facets/lookup') {
      const field = url.searchParams.get('field') ?? 'scope';
      const value = url.searchParams.get('value') ?? '';
      const found = facetValues(field).find(entry => entry.value === value);
      return json({ field, value, count: found?.count ?? 0, available: Boolean(found) });
    }
    if (at === repo + '/skills') {
      const scope = url.searchParams.get('scope');
      const query = (url.searchParams.get('q') ?? '').toLowerCase();
      const matched = skills.filter(skill => (!scope || skill.scope === scope) && (!query || skill.name.toLowerCase().includes(query)));
      return json({
        items: matched.map(summary), next_cursor: null, snapshot_id: 'snap-1', schema_version: 'mgmt-1',
        filters: scope ? { scope: { value: scope, available: skills.some(skill => skill.scope === scope) } } : {},
      });
    }
    if (at.includes('/revisions/') && at.endsWith('/raw')) return text(chosen.raw, 'text/markdown');
    if (at.includes('/revisions/')) {
      const requested = at.split('/revisions/')[1];
      const skill = skills.find(item => item.revision === requested);
      if (method === 'POST') return json({ judgment_id: 'judgment-1' });
      if (!skill) return json({ error: 'revision_not_found', message: 'No such revision.', request_id: 'stub-1' }, 404);
      return json(revisionOf(skill));
    }
    if (at.startsWith(repo + '/skills/')) {
      const id = at.slice((repo + '/skills/').length);
      const skill = skills.find(item => item.id === id);
      if (!skill) return json({ error: 'skill_not_found', message: 'No such skill.', request_id: 'stub-1' }, 404);
      return json({ ...summary(skill), revisions: [{ revision_id: skill.revision, content_sha256: skill.revision, commit: fixture.commit, import_id: 'im-1', created_at: null, source: 'import' }] });
    }

    if (at === repo + '/map/repository') {
      const prefix = url.searchParams.get('path') ? (url.searchParams.get('path') as string) + '/' : '';
      const children = new Map<string, { name: string; path: string; kind: string; skill_id: string | null; count: number }>();
      for (const skill of skills) {
        if (!skill.path.startsWith(prefix)) continue;
        const rest = skill.path.slice(prefix.length);
        const cut = rest.indexOf('/');
        const name = cut === -1 ? rest : rest.slice(0, cut);
        const entry = children.get(name) ?? { name, path: prefix + name, kind: cut === -1 ? 'skill' : 'dir', skill_id: cut === -1 ? skill.id : null, count: 0 };
        entry.count += 1;
        children.set(name, entry);
      }
      return json({ path: url.searchParams.get('path') ?? '', children: [...children.values()], next_cursor: null });
    }
    if (at === repo + '/map/scopes') {
      const scope = url.searchParams.get('scope');
      const node = fixture.nodes.find(entry => entry.id === scope);
      return json({
        scope: node ? { id: node.id, owner: node.owner, paths: node.paths, parent: null } : null,
        children: fixture.nodes.slice(0, 5).map(entry => ({ id: entry.id, owner: entry.owner, skills: skills.filter(skill => skill.scope === entry.id).length })),
        skills: skills.filter(skill => !scope || skill.scope === scope).slice(0, 5).map(skill => ({ skill_id: skill.id, name: skill.name })),
        unmapped: skills.filter(skill => !fixture.nodes.some(entry => entry.id === skill.scope)).map(skill => ({ skill_id: skill.id, name: skill.name })),
      });
    }
    if (at === repo + '/map/layers') return json({ layers: [{ layer: 'unclassified', count: skills.length }] });
    if (at === repo + '/map/relations') return json({
      items: chosen.requires.map(to => ({ from: chosen.id, to, type: 'requires', provenance: 'source', revision: null })),
      next_cursor: null, truncated: false,
    });
    if (at.startsWith(repo + '/modules/')) {
      const scope = at.slice((repo + '/modules/').length);
      const inScope = skills.filter(skill => skill.scope === scope);
      return json({
        scope, owner: inScope[0]?.owner ?? null, skills: inScope.map(summary),
        reading_order: inScope.map(skill => skill.id), shared: [], documents: [],
      });
    }

    if (at === repo + '/proposals') return json({
      items: [{ proposal_id: 'p-1', kind: 'enrichment', state: state.proposalState, scope: chosen.scope, owner: chosen.owner, target_skill_id: chosen.id, path: chosen.path, created_at: null }],
      next_cursor: null,
    });
    if (at === repo + '/proposals/p-1/decision' && method === 'POST') {
      state.proposalState = 'approved_for_export';
      return json({ proposal_id: 'p-1', state: 'approved_for_export', revision_id: 'rev-human', expected_revision: 'rev-human' });
    }
    if (at === repo + '/proposals/p-1/export' && method === 'POST') {
      state.proposalState = 'awaiting_git';
      return json({
        export_id: 'ex-1', proposal_id: 'p-1', state: 'awaiting_git', base_commit: fixture.commit,
        files: [{ path: chosen.path, sha256: 'sha-candidate', content: chosen.raw }],
        patch: '--- a/' + chosen.path + '\n+++ b/' + chosen.path + '\n',
      });
    }
    if (at === repo + '/proposals/p-1/publication') {
      state.publicationCalls += 1;
      return json({ state: 'awaiting_git', published_revision_id: null, import_id: null, snapshot_id: null });
    }
    if (at === repo + '/proposals/p-1') return json(proposal());
    if (at === repo + '/snapshots') return json({
      items: [{
        publication_id: 'pub-1', snapshot_id: 'snap-1', state: 'active', active: true,
        import_id: 'im-1', job_id: 'j-publish-1', commit: fixture.commit, n_skills: skills.length,
        builder_sha256: 'sha-builder', validation: { ok: true, findings: [] }, error: null,
        activated_at: null, created_at: '2026-09-06T09:00:00Z',
      }],
      next_cursor: null,
    });

    if (at === repo + '/usage/export') return text('skill_id,exposures\n' + chosen.id + ',12\n', 'text/csv');
    if (at.startsWith(repo + '/usage/queue/') && method === 'POST') {
      state.queueDecided = true;
      return json({ item_id: 'q-1' });
    }
    if (at === repo + '/usage') return json({
      window: { from: '2026-08-31T00:00:00Z', to: '2026-09-06T00:00:00Z', watermark: '2026-09-06T00:00:00Z' },
      coverage: { events_received: 210, dropped_reported: 0, oldest_lag_s: 4, task_ids_present: true },
      totals: { exposures: 40, loads_verified: 18, context_loaded: 16, context_unknown: 2, use_reported: 5, use_observed: 3, use_episodes: 4, feedback: null },
      skills: [
        { skill_id: chosen.id, revision: chosen.revision, exposures: 12, loads_verified: 6, context_loaded: 6, use_reported: 2, use_observed: 1, feedback: null, helped_ratio: { numerator: 2, denominator: 4, small_sample: true }, zero_loads: false },
        { skill_id: skills[1].id, revision: skills[1].revision, exposures: 8, loads_verified: 0, context_loaded: 0, use_reported: 0, use_observed: 0, feedback: null, helped_ratio: null, zero_loads: true },
      ],
      queue: state.queueDecided
        ? [{ item_id: 'q-1', skill_id: skills[1].id, revision: skills[1].revision, reason: 'zero_loads', since: '2026-09-01T00:00:00Z', evidence: { exposures: 8 }, decision: { action: 'reviewed', reason: 'Checked in Git.', at: '2026-09-06T10:00:00Z' } }]
        : [{ item_id: 'q-1', skill_id: skills[1].id, revision: skills[1].revision, reason: 'zero_loads', since: '2026-09-01T00:00:00Z', evidence: { exposures: 8 }, decision: null }],
      health: { adapters: [{ harness: 'claude', adapter_version: '0.4.1', capabilities: ['search', 'use'], last_seen_at: '2026-09-06T09:00:00Z', lag_s: 4, dropped: 0 }] },
    });

    return json({ error: 'not_found', message: 'The stub has no route for ' + at, request_id: 'stub-1' }, 404);
  });
  return state;
}

const query = (extra = '') => '?mode=api&org=meridian&repo=monorepo' + extra;
async function open(page: Page, view: string, extra = '') {
  await page.goto('/' + view + query(extra));
  await page.locator('main').waitFor();
  // Several panels may load at once, so wait for the count to reach zero rather than one element.
  await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
}
async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let step = 0; step < 200; step += 1) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Target is not reachable through Tab');
}
async function axeViolations(page: Page) {
  await page.addScriptTag({ path: path.resolve('node_modules/axe-core/axe.min.js') });
  return page.evaluate(async () => {
    const result = await (window as unknown as { axe: { run: (root: Document, options: unknown) => Promise<{ violations: { id: string; nodes: { target: string[] }[] }[] }> } })
      .axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
    return result.violations.map(violation => ({ id: violation.id, nodes: violation.nodes.map(node => node.target) }));
  });
}

test('sign-in providers and the organisation come from the API', async ({ page }) => {
  await stubApi(page);
  await page.goto('/import?mode=api&step=login');
  await expect(page.getByRole('button', { name: /Continue with GitHub/ })).toBeVisible();
  await expect(page.getByText('Meridian Data')).toBeVisible();
  await expect(page.getByText('Local simulation')).toHaveCount(0);
});

test('library filters, cursor context and the skill link survive the URL', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library');
  await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();
  await page.getByLabel('Scope', { exact: true }).selectOption(chosen.scope);
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect(page).toHaveURL(new RegExp('scope=' + encodeURIComponent(chosen.scope)));
  await expect(page.getByRole('link', { name: chosen.name, exact: true })).toBeVisible();
});

test('an unavailable filter value is named and never widened to All', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library', '&scope=not-a-scope');
  await expect(page.getByText(/This snapshot has no value not-a-scope/)).toBeVisible();
  const field = page.getByLabel('Scope', { exact: true });
  await expect(field).toHaveValue('not-a-scope');
  await expect(field).toHaveAttribute('aria-invalid', 'true');
  await expect(field.locator('option:checked')).toHaveText('Not available in this snapshot: not-a-scope');
});

test('the skill view links the exact host, file and commit', async ({ page }) => {
  await stubApi(page);
  await open(page, 'skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision + '&tab=source');
  const link = page.getByRole('link', { name: /Open exact source revision/ });
  await expect(link).toHaveAttribute('href', sourceUrl(chosen));
});

test('a revision that does not exist is an error, never a newer body', async ({ page }) => {
  await stubApi(page);
  await open(page, 'skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + 'f'.repeat(64));
  await expect(page.getByText('Revision not available')).toBeVisible();
  await expect(page.getByText(chosen.body.split('\n')[0])).toHaveCount(0);
});

test('owner reaches library, skill, decision and export with the keyboard only', async ({ page }) => {
  await stubApi(page);
  await open(page, 'library');
  await tabTo(page, page.getByLabel('Search name, description or path', { exact: true }));
  await page.keyboard.type(chosen.name);
  await tabTo(page, page.getByRole('button', { name: 'Apply filters', exact: true }));
  await page.keyboard.press('Enter');
  await tabTo(page, page.getByRole('link', { name: chosen.name, exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText('Immutable revision')).toBeVisible();

  await open(page, 'proposals', '&proposal=p-1');
  await tabTo(page, page.getByLabel('Reason for this decision', { exact: true }));
  await page.keyboard.type('Read the source and the scope before approving.');
  await tabTo(page, page.getByRole('button', { name: 'Save decision', exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText(/Recorded: approved_for_export/)).toBeVisible();

  await tabTo(page, page.getByRole('button', { name: 'Create export', exact: true }));
  await page.keyboard.press('Enter');
  await expect(page.getByText('guidefold proposals apply ex-1 --write')).toBeVisible();
  await expect(page.getByText(/Waiting for your Git review/)).toBeVisible();
});

test('the usage queue records an owner decision and keeps Unknown out of zero', async ({ page }) => {
  await stubApi(page);
  await open(page, 'usage');
  await expect(page.getByText('Exposed but never loaded').first()).toBeVisible();
  await expect(page.getByText('2 of 4')).toBeVisible();
  await expect(page.getByText('Small sample; no rate is reported below 20 assessments.')).toBeVisible();
  await page.getByLabel('Reason', { exact: true }).fill('Checked in Git.');
  await page.getByRole('button', { name: 'Record decision', exact: true }).click();
  await expect(page.getByText('Reviewed, no change needed')).toBeVisible();
});

test('the plan is read before generation, and a job skipped for lack of a generator reads as honest, not failed', async ({ page }) => {
  await stubApi(page);
  await open(page, 'import', '&step=result&import_id=im-1');
  await expect(page.getByText('Groups and inputs (1)')).toBeVisible();
  await expect(page.getByText('No generator configured')).toBeVisible();
  await page.getByRole('button', { name: 'Generate proposals' }).click();
  await expect(page.getByText('Generation started')).toBeVisible();
  await expect(page.getByText('j-gen-1')).toBeVisible();
  await expect(page.getByText(/No generator is configured on this API\. This is not a failure/)).toBeVisible();
});

test('the audit tab pages through entries with a cursor and shows every column', async ({ page }) => {
  await stubApi(page);
  await open(page, 'organization', '&tab=audit');
  await expect(page.getByRole('cell', { name: 'member.invite' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'req-1' })).toBeVisible();
  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByRole('cell', { name: 'repo.create' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'req-2' })).toBeVisible();
});

test('a link suggestion is never auto-linked: the operator action redirects to the real confirmation URL', async ({ page }) => {
  const state = await stubApi(page);
  state.linkSuggested = true;
  await open(page, 'organization');
  await expect(page.getByText('Another sign-in method uses this e-mail.')).toBeVisible();
  await tabTo(page, page.getByRole('button', { name: 'Link google' }));
  await Promise.all([page.waitForURL('**/link-confirm/google'), page.keyboard.press('Enter')]);
  await expect(page.getByText('Linked.')).toBeVisible();
});

const apiViews: [string, string, string?][] = [
  ['import', '&step=result&import_id=im-1'],
  ['library', ''],
  ['map', '&tab=scopes&scope=' + encodeURIComponent(fixture.nodes[0].id)],
  ['skill', '&skill=' + encodeURIComponent(chosen.id) + '&revision=' + chosen.revision],
  ['proposals', '&proposal=p-1'],
  ['usage', ''],
  ['organization', ''],
  ['organization', '&tab=audit', 'organization, audit tab'],
];
for (const [view, extra, label] of apiViews) {
  test('axe finds no violation on ' + (label ?? view) + ' in API mode', async ({ page }) => {
    await stubApi(page);
    await open(page, view, extra);
    await page.evaluate(() => document.fonts.ready);
    expect(await axeViolations(page), view).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), view).toBe(true);
  });
}
