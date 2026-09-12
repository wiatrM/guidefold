import { describe, expect, test } from 'vitest';
import * as d from './decoders';

const decode = <T>(value: unknown, decoder: d.Decoder<T>) => d.decode(value, decoder);

/** One row of `GET {repo_base}/snapshots` exactly as the service writes it (review/publication.go). */
const snapshotRow = () => ({
  publication_id: 'pub-1', snapshot_id: 'sn1', state: 'active', active: true,
  import_id: 'im1', job_id: 'j1', commit: 'c', n_skills: 27, builder_sha256: 'b',
  validation: { ok: true, findings: [] }, error: null,
  activated_at: '2026-09-06T10:00:00Z', created_at: '2026-09-06T09:00:00Z',
});

describe('decoders accept the contract payloads', () => {
  test('Me carries identity, memberships, csrf and the access window', () => {
    const value = decode({
      user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
      identities: [{ provider: 'github', created_at: '2026-09-01T10:00:00Z' }],
      orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' }],
      csrf_token: 'csrf-1',
      access: { checked_at: '2026-09-06T10:00:00Z', valid_for_s: 45 },
      unexpected_field: 'ignored',
    }, d.me);
    expect(value.orgs[0].role).toBe('owner');
    expect(value.access.valid_for_s).toBe(45);
    expect(value.link_suggestions).toEqual([]);
  });

  test('AuthProviders and DeviceApproval', () => {
    expect(decode({ mode: 'workos', providers: [{ id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' }] }, d.authProviders).providers).toHaveLength(1);
    expect(decode({ user_code: 'ABCD-1234', state: 'approved', expires_at: null }, d.deviceApproval).state).toBe('approved');
  });

  test('Org list accepts a bare array and the real GET /api/v1/orgs envelope', () => {
    // The envelope key is `items` (services/search/internal/identity/orgs.go's
    // handleListOrgs), not `orgs` -- that name belongs only to the unrelated field
    // embedded in the Me response (see the "Me decodes..." test below).
    const bare = decode([{ org_id: 'o1', slug: 'meridian', name: 'Meridian', my_role: 'owner' }], d.orgList);
    const wrapped = decode({ items: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian' }], schema_version: 'mgmt-1' }, d.orgList);
    expect(bare[0].my_role).toBe('owner');
    expect(wrapped[0].my_role).toBeNull();
  });

  test('Member, Invitation, Installation and Repo', () => {
    expect(decode({ user_id: 'u1', email: 'a@b.c', name: null, role: 'member', joined_at: null }, d.member).role).toBe('member');
    expect(decode({ invitation_id: 'i1', accept_url: 'https://app/invitations/tok/accept', expires_at: '2026-09-13T00:00:00Z' }, d.invitation).accept_url).toContain('/accept');
    const installation = decode({ installation_id: 'k1', name: 'ci', scopes: ['search', 'use'], last_seen_at: null, adapter_version: null, capabilities: null }, d.installation);
    expect(installation.capabilities).toBeNull();
    expect(installation.token).toBeNull();
    expect(decode({ repo_id: 'monorepo' }, d.repo).git_host_url).toBeNull();
    // `created` tells a registration apart from a repository that already existed (§4.2).
    expect(decode({ repo_id: 'monorepo', created: true }, d.repo).created).toBe(true);
    expect(decode({ repo_id: 'monorepo' }, d.repo).created).toBe(false);
  });

  test('ImportCreated and ImportStatus with files, jobs and publication', () => {
    expect(decode({ import_id: 'im1', state: 'created', missing_blobs: ['a'.repeat(64)], limits: { max_blob_bytes: 8388608, max_total_bytes: 104857600, max_files: 100000 } }, d.importCreated).limits?.max_files).toBe(100000);
    const status = decode({
      import_id: 'im1', state: 'partial', manifest_digest: 'digest', commit: null, complete: true,
      counts: { files: 3, accepted: 2, omitted: 0, failed: 1, new_blobs: 1, reused_blobs: 2, skills: 2, documents: 0 },
      files: [
        { path: 'a/SKILL.md', sha256: 'x', size: 10, kind: 'skill', status: 'accepted' },
        { path: 'b/SKILL.md', sha256: 'y', size: 10, kind: 'skill', status: 'failed', reason: 'frontmatter_invalid' },
      ],
      jobs: [{ job_id: 'j1', kind: 'import.parse', state: 'done', attempts: 1, generation: 2, cost: { calls: 0, tokens_in: 0, tokens_out: 0, usd_certain: 0, usd_uncertain: 0 } }],
      publication: { snapshot_id: null, state: 'none' },
      created_at: '2026-09-06T10:00:00Z', updated_at: '2026-09-06T10:00:05Z',
    }, d.importStatus);
    expect(status.state).toBe('partial');
    expect(status.files.map(file => file.status)).toEqual(['accepted', 'failed']);
    expect(status.jobs[0].state).toBe('done');
    expect(status.publication?.state).toBe('none');
    // The list endpoint sends `files: []` with `files_truncated: true`; absent means "not truncated".
    expect(status.files_truncated).toBe(false);
    expect(decode({ import_id: 'im1', state: 'ready', files: [], files_truncated: true }, d.importStatus).files_truncated).toBe(true);
  });

  test('ImportPlan carries the fields the operator decides on before spending (§5.2)', () => {
    const plan = decode({
      groups: [{
        group_id: 'g1', kind: 'extraction', scope: 'atlas.identity', owner: 'identity-team',
        inputs: ['a/SKILL.md', 'b/SKILL.md'], n_inputs: 2, estimated_tokens: 1200, estimated_calls: 2,
      }],
      limits: { max_files: 20, max_bytes: 1048576, max_groups: 5, max_proposals_per_group: 5, max_neighbours: 10, max_tokens: 24000, max_calls: 15, max_usd: 5 },
      groups_skipped: { extraction: 3 }, estimated_calls: 2, estimated_usd_max: 5,
      generator: { name: 'openai', configured: true, generator: 'openai', version: 'v3', model: 'gpt-x' },
    }, d.importPlan);
    expect(plan.groups[0].scope).toBe('atlas.identity');
    expect(plan.groups[0].owner).toBe('identity-team');
    expect(plan.groups[0].n_inputs).toBe(2);
    expect(plan.groups[0].estimated_calls).toBe(2);
    expect(plan.estimated_calls).toBe(2);
    expect(plan.groups_skipped).toEqual({ extraction: 3 });
    expect(plan.limits.max_files).toBe(20);
    expect(plan.limits.max_bytes).toBe(1048576);
    expect(plan.generator.generator).toBe('openai');
    expect(plan.generator.version).toBe('v3');
    expect(plan.generator.model).toBe('gpt-x');
  });

  test('SkillSummary, SkillPage filters.available, Facets and FacetLookup', () => {
    const page = decode({
      items: [{
        skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', name: 'pipeline-testing', description: '[forge.pipelines] test',
        scope: 'forge.pipelines', owner: 'pipelines-team', source_layer: 'team', knowledge_layer: 'unclassified',
        source_status: 'active', publication_status: 'draft', path: 'platforms/forge/SKILL.md',
        content_sha256: 'sha', revision_id: 'rev', package_digest: null, commit: 'c', updated_at: null,
      }],
      next_cursor: null, snapshot_id: 'snap-1', schema_version: 'mgmt-1',
      filters: { scope: { value: 'missing-value', available: false } },
    }, d.skillPage);
    expect(page.filters.scope.available).toBe(false);
    expect(page.items[0].publication_status).toBe('draft');
    expect(decode({ field: 'scope', values: [{ value: 'forge', count: 3 }], next_cursor: null }, d.facets).values[0].count).toBe(3);
    expect(decode({ field: 'scope', value: 'nope', count: 0, available: false }, d.facetLookup).available).toBe(false);
  });

  test('SkillDetail revisions and a full Revision', () => {
    const summary = {
      skill_id: 's1', name: 'n', description: '', scope: 'a', owner: 'o', source_layer: 'team',
      knowledge_layer: 'task', source_status: 'active', publication_status: 'published', path: 'p',
      content_sha256: 'sha', revision_id: 'r1', package_digest: null, commit: 'c', updated_at: null,
    };
    const detail = decode({ ...summary, card_revision: 'card-1', revisions: [{ revision_id: 'r1', content_sha256: 'sha', card_revision: 'card-1', commit: 'c', import_id: 'im1', created_at: null, source: 'import' }] }, d.skillDetail);
    expect(detail.revisions[0].source).toBe('import');
    // §5.3: the card revision is what the delivery path and adapter telemetry name.
    expect(detail.card_revision).toBe('card-1');
    expect(detail.revisions[0].card_revision).toBe('card-1');
    // A summary from a server that has not published this skill yet carries no card revision,
    // and an absent field is null rather than a decode failure.
    expect(decode(summary, d.skillSummary).card_revision).toBeNull();
    const revision = decode({
      revision_id: 'r1', content_sha256: 'sha', card_revision: 'card-1', body: '# body',
      frontmatter: { name: 'n' },
      source: { path: 'p', commit: 'c', url: null },
      references: [{ path: 'references/a.md', sha256: 's', size: 4, type: 'reference', required: true, available: true }],
      requires: ['urn:skill:a:b:c'], refines: [],
      relations: [{ from: 's1', to: 's2', type: 'requires', provenance: 'parsed', revision: 'r1' }],
      feedback: [{ judgment_id: 'j1', verdict: 'helped', reason: null, source: 'human', task_id: null, occurred_at: null }],
      provenance: { origin: 'source', import_id: 'im1', proposal_id: null },
      publication_status: 'published',
    }, d.revision);
    expect(revision.references[0].required).toBe(true);
    expect(revision.relations[0].type).toBe('requires');
  });

  test('Map, relations and module page', () => {
    expect(decode({ path: '', children: [{ name: 'platforms', path: 'platforms', kind: 'dir', count: 12 }], next_cursor: null }, d.mapRepository).children[0].kind).toBe('dir');
    expect(decode({ scope: { id: 'forge', owner: 'o', paths: ['platforms/forge'], parent: null }, children: [], skills: [], unmapped: [] }, d.mapScopes).scope?.paths).toEqual(['platforms/forge']);
    expect(decode({ layers: [{ layer: 'atomic', count: 4 }] }, d.mapLayers).layers[0].layer).toBe('atomic');
    expect(decode({ items: [{ from: 'a', to: 'b', type: 'derived_from', provenance: 'inferred', revision: 'r' }], next_cursor: null, truncated: true }, d.relations).truncated).toBe(true);
    expect(decode({ scope: 'forge', owner: 'o', skills: [], reading_order: [], shared: [], documents: [{ path: 'AGENTS.md', kind: 'document' }] }, d.modulePage).documents[0].path).toBe('AGENTS.md');
  });

  test('Proposals, decision, export, publication and snapshots', () => {
    expect(decode({ items: [{ proposal_id: 'p1', kind: 'extraction', state: 'draft', scope: 'a', owner: 'o', target_skill_id: null, path: 'x', created_at: null }], next_cursor: null }, d.proposalList).items[0].kind).toBe('extraction');
    const detail = decode({
      proposal_id: 'p1', kind: 'consolidation', state: 'draft', scope: 'a', owner: 'o',
      target_skill_id: null, target_revision_id: null,
      sources: [{ path: 'doc.md', sha256: 's', commit: 'c', lines: [1, 20] }],
      recipe: { version: 'det-1', generator: 'deterministic', model: null },
      candidate: { path: 'new/SKILL.md', body: '# x', sha256: 's', frontmatter: null },
      source_body: '# old',
      provenance: [{ field: 'steps', origin: 'inferred', source_ref: { path: 'doc.md' }, needs_confirmation: true }],
      relations: [{ type: 'derived_from', to: 's2' }],
      decision: null, expected_revision: 'rev-1', created_at: null, cost: null,
    }, d.proposalDetail);
    expect(detail.provenance[0].needs_confirmation).toBe(true);
    expect(decode({ proposal_id: 'p1', state: 'approved_for_export', revision_id: 'r2', expected_revision: 'r2' }, d.decisionResult).state).toBe('approved_for_export');
    const exported = decode({ export_id: 'e1', proposal_id: 'p1', state: 'awaiting_git', base_commit: 'c', files: [{ path: 'a/SKILL.md', sha256: 's', content: 'x' }], patch: '--- a' }, d.exportPayload);
    expect(exported.files[0].content).toBe('x');
    expect(exported.proposal_id).toBe('p1');
    expect(exported.state).toBe('awaiting_git');
    expect(decode({ state: 'published', published_revision_id: 'r2', import_id: 'im2', snapshot_id: 'sn1' }, d.publication).state).toBe('published');
    expect(decode([snapshotRow()], d.snapshotList)[0].active).toBe(true);
  });

  test('a publication without a snapshot and a failed validation both decode (§5.4)', () => {
    const rows = decode({
      items: [
        snapshotRow(),
        { ...snapshotRow(), publication_id: 'pub-2', snapshot_id: null, state: 'building', active: false, validation: null },
        {
          ...snapshotRow(), publication_id: 'pub-3', snapshot_id: null, state: 'failed', active: false,
          error: 'missing_dependency', validation: { ok: false, findings: ['urn:skill:meridian:a:b requires an unknown skill'] },
        },
      ],
    }, d.snapshotList);
    expect(rows.map(row => row.publication_id)).toEqual(['pub-1', 'pub-2', 'pub-3']);
    expect(rows[1].snapshot_id).toBeNull();
    expect(rows[1].state).toBe('building');
    expect(rows[2].validation?.findings).toEqual(['urn:skill:meridian:a:b requires an unknown skill']);
    expect(rows[2].error).toBe('missing_dependency');
  });

  test('the activate response is the {snapshot} envelope, not a bare Snapshot (§4.4)', () => {
    const activated = decode(
      { schema_version: 'mgmt-1', org_id: 'o1', repo_id: 'monorepo', snapshot: { ...snapshotRow(), active: true } },
      d.field('snapshot', d.snapshot),
    );
    expect(activated.snapshot_id).toBe('sn1');
    expect(activated.active).toBe(true);
  });

  test('Usage keeps helped_ratio nullable and small_sample explicit', () => {
    const value = decode({
      window: { from: '2026-08-01', to: '2026-09-01', watermark: null },
      coverage: { events_received: 100, dropped_reported: 0, oldest_lag_s: 3, task_ids_present: true },
      totals: { exposures: 10, loads_verified: 4, context_loaded: 2, context_unknown: 8, use_reported: 1, use_observed: 0, use_episodes: 1, feedback: { helped: 1, hindered: 0, mixed: 0, not_applicable: 0, unknown: 3, n: 4 } },
      skills: [
        {
          skill_id: 's1', revision: 'r1', scope: 'atlas.identity', owner: 'identity-team', harness: 'claude',
          content_sha256: 'sha-1',
          exposures: 5, loads_verified: 2, context_loaded: 1, context_unknown: 1, use_reported: 1, use_observed: 0,
          use_episodes: 1, feedback: null, helped_ratio: null, zero_loads: false,
        },
        { skill_id: 's2', revision: 'r1', exposures: 5, loads_verified: 0, context_loaded: 0, use_reported: 0, use_observed: 0, feedback: null, helped_ratio: { numerator: 2, denominator: 3, small_sample: true }, zero_loads: true },
      ],
      queue: [{ item_id: 'q1', skill_id: 's2', revision: 'r1', reason: 'zero_loads', since: null, evidence: null, decision: null }],
      health: { adapters: [{ harness: 'claude', adapter_version: null, capabilities: null, last_seen_at: null, lag_s: null, dropped: null }] },
    }, d.usage);
    expect(value.skills[0].helped_ratio).toBeNull();
    expect(value.skills[1].helped_ratio?.small_sample).toBe(true);
    expect(value.health?.adapters[0].adapter_version).toBeNull();
    // §5.5: the per-skill row carries its own scope, owner, harness and both unknown-safe counters.
    expect(value.skills[0].scope).toBe('atlas.identity');
    // §5.5: one revision has three names; a row the catalogue does not know keeps them null
    // rather than repeating the key it was counted under.
    expect(value.skills[0].card_revision).toBeNull();
    expect(value.skills[0].content_sha256).toBe('sha-1');
    expect(value.skills[1].content_sha256).toBeNull();
    expect(value.skills[0].owner).toBe('identity-team');
    expect(value.skills[0].harness).toBe('claude');
    expect(value.skills[0].context_unknown).toBe(1);
    expect(value.skills[0].use_episodes).toBe(1);
    expect(value.skills[1].harness).toBeNull();
    // §5.5: `previous` is absent from this payload, not merely omitted from the assertions.
    expect(value.previous).toBeNull();
  });

  test('Usage.previous (1.3.0) carries the same totals shape over the prior window', () => {
    const withPrevious = decode({
      window: { from: '2026-08-01', to: '2026-09-01', watermark: null },
      coverage: null,
      totals: { exposures: 20, loads_verified: 8, context_loaded: 6, context_unknown: 2, use_reported: 2, use_observed: 1, use_episodes: 2, feedback: null },
      previous: {
        window: { from: '2026-07-01', to: '2026-08-01' },
        totals: { exposures: 10, loads_verified: 4, context_loaded: 2, context_unknown: 2, use_reported: 1, use_observed: 0, use_episodes: 1, feedback: { helped: 2, hindered: 1, mixed: 0, not_applicable: 0, unknown: 0, n: 3 } },
      },
      skills: [], queue: [], health: null,
    }, d.usage);
    expect(withPrevious.previous?.window).toEqual({ from: '2026-07-01', to: '2026-08-01' });
    expect(withPrevious.previous?.totals.exposures).toBe(10);
    expect(withPrevious.previous?.totals.feedback?.helped).toBe(2);
    // The carried metrics default keeps the same empty shape as the current window's.
    expect(withPrevious.previous?.totals.metrics.tasks_started).toBe(0);
    const withoutPrevious = decode({ window: {}, coverage: null, totals: {}, skills: [], queue: [], health: null }, d.usage);
    expect(withoutPrevious.previous).toBeNull();
  });
});

describe('decoders reject malformed payloads', () => {
  test('a wrong type names the failing path', () => {
    expect(() => decode({ user: { id: 1, email: 'a', name: null }, identities: [], orgs: [], csrf_token: null, access: null }, d.me))
      .toThrowError(/user\.id: expected string, received number/);
  });
  test('a missing required field fails instead of defaulting', () => {
    expect(() => decode({ slug: 'meridian', name: 'Meridian' }, d.org)).toThrowError(d.DecodeError);
    expect(() => decode({ import_id: 'im1', files: 'none' }, d.importStatus)).toThrowError(/files: expected array/);
  });
  test('an array where an object is required fails', () => {
    expect(() => decode([], d.skillPage)).toThrowError(/expected object, received array/);
  });
  test('an unknown enum value is a contract break, an absent one takes the default', () => {
    expect(() => decode({ import_id: 'im1', state: 'invented' }, d.importStatus)).toThrowError(/state: expected one of/);
    expect(decode({ import_id: 'im1' }, d.importStatus).state).toBe('queued');
    expect(() => decode({ field: 'scope', values: [{ value: 1, count: 1 }], next_cursor: null }, d.facets)).toThrowError(/values\[0\]\.value/);
  });
  test('Usage.previous.totals is required once `previous` is present: missing or malformed fails, never Unknown-as-zero', () => {
    const base = { window: {}, coverage: null, totals: {}, skills: [], queue: [], health: null };
    // `previous` present but `totals` entirely absent.
    expect(() => decode({ ...base, previous: { window: { from: '2026-07-01', to: '2026-08-01' } } }, d.usage))
      .toThrowError(/previous\.totals: expected object/);
    // `previous.totals` present but not an object.
    expect(() => decode({ ...base, previous: { window: { from: '2026-07-01', to: '2026-08-01' }, totals: 'none' } }, d.usage))
      .toThrowError(/previous\.totals: expected object/);
    // No `previous` at all still decodes to null, not a decode error.
    expect(decode(base, d.usage).previous).toBeNull();
  });
});

describe('decoders match the closed domains of API-CONTRACT §5', () => {
  test('an import may be uploading between created and queued (§5.2, §6)', () => {
    expect(decode({ import_id: 'im1', state: 'uploading' }, d.importStatus).state).toBe('uploading');
    expect(decode({ import_id: 'im1', state: 'uploading', missing_blobs: ['sha1'] }, d.importCreated).state).toBe('uploading');
    expect(d.importStates).toEqual(['created', 'uploading', 'queued', 'parsing', 'ready', 'partial', 'failed', 'cancelled']);
  });

  test('an import file kind stays inside skill|document|config|resource', () => {
    expect(decode({ import_id: 'im1', files: [{ path: 'a', sha256: null, size: null, kind: 'config', status: 'accepted', reason: null, skill_id: null }] }, d.importStatus).files[0].kind).toBe('config');
    expect(() => decode({ import_id: 'im1', files: [{ path: 'a', kind: 'binary' }] }, d.importStatus)).toThrowError(/kind: expected one of/);
  });

  test('a relation type is never coerced: an unknown edge must not become requires', () => {
    expect(decode({ items: [{ from: 'a', to: 'b', type: 'conflicts_with', provenance: null, revision: null }], next_cursor: null, truncated: false }, d.relations).items[0].type).toBe('conflicts_with');
    expect(() => decode({ items: [{ from: 'a', to: 'b', type: 'related_to' }], next_cursor: null, truncated: false }, d.relations)).toThrowError(/type: expected one of/);
  });

  test('knowledge layer is the contract domain, not free text', () => {
    const summary = { skill_id: 'urn:a', name: 'a', description: '', scope: 's', owner: null, source_layer: null, source_status: null, publication_status: 'draft', path: 'p', content_sha256: null, revision_id: null, package_digest: null, commit: null, updated_at: null };
    expect(decode({ items: [{ ...summary, knowledge_layer: 'task' }], next_cursor: null, snapshot_id: null, schema_version: null, filters: {} }, d.skillPage).items[0].knowledge_layer).toBe('task');
    expect(decode({ items: [{ ...summary, knowledge_layer: null }], next_cursor: null, snapshot_id: null, schema_version: null, filters: {} }, d.skillPage).items[0].knowledge_layer).toBeNull();
    expect(() => decode({ items: [{ ...summary, knowledge_layer: 'Unclassified' }], next_cursor: null, snapshot_id: null, schema_version: null, filters: {} }, d.skillPage)).toThrowError(/knowledge_layer: expected one of/);
  });

  test('provenance origin, feedback verdict and revision source are closed domains', () => {
    const revision = {
      revision_id: 'r1', content_sha256: null, body: null, frontmatter: null, source: null,
      references: [], requires: [], refines: [], relations: [], publication_status: 'draft',
      feedback: [{ judgment_id: 'j1', verdict: 'not_applicable', reason: null, source: null, task_id: null, occurred_at: null }],
      provenance: { origin: 'inferred', import_id: null, proposal_id: null },
    };
    expect(decode(revision, d.revision).provenance?.origin).toBe('inferred');
    expect(decode(revision, d.revision).feedback[0].verdict).toBe('not_applicable');
    expect(() => decode({ ...revision, provenance: { origin: 'guessed', import_id: null, proposal_id: null } }, d.revision)).toThrowError(/origin: expected one of/);
    expect(() => decode({ skill_id: 'urn:a', name: 'a', description: '', scope: 's', owner: null, source_layer: null, knowledge_layer: null, source_status: null, publication_status: 'draft', path: 'p', content_sha256: null, revision_id: null, package_digest: null, commit: null, updated_at: null, revisions: [{ revision_id: 'r1', content_sha256: null, commit: null, import_id: null, created_at: null, source: 'guess' }] }, d.skillDetail)).toThrowError(/source: expected one of/);
  });

  test('an owner queue item keeps its own reason, action and 1.3.0 actor', () => {
    const usage = { window: {}, coverage: null, totals: {}, skills: [], health: null, queue: [{ item_id: 'q1', skill_id: 's1', revision: null, reason: 'source_removed', since: null, evidence: null, decision: { action: 'fixed_in_git', reason: 'r', at: null, actor: 'u1' } }] };
    expect(decode(usage, d.usage).queue[0].reason).toBe('source_removed');
    expect(decode(usage, d.usage).queue[0].decision?.action).toBe('fixed_in_git');
    expect(decode(usage, d.usage).queue[0].decision?.actor).toBe('u1');
    // A worker-written decision carries no actor: absent stays null, not an empty string.
    const workerUsage = { ...usage, queue: [{ ...usage.queue[0], decision: { action: 'fixed_in_git', reason: 'r', at: null, actor: null } }] };
    expect(decode(workerUsage, d.usage).queue[0].decision?.actor).toBeNull();
    expect(() => decode({ ...usage, queue: [{ item_id: 'q1', skill_id: 's1', reason: 'looked_odd' }] }, d.usage)).toThrowError(/reason: expected one of/);
  });

  test('a proposal kind, decision and relation follow §5.4', () => {
    const detail = {
      proposal_id: 'p1', kind: 'consolidation', state: 'draft', scope: null, owner: null, target_skill_id: null, target_revision_id: null,
      sources: [], recipe: null, candidate: { path: 'a', body: '', sha256: null, frontmatter: null }, source_body: null,
      provenance: [{ field: 'description', origin: 'human', source_ref: null, needs_confirmation: false }],
      relations: [{ type: 'derived_from', to: 'urn:a' }],
      decision: { decision: 'edit', reason: null, at: null, actor: null },
      expected_revision: null, created_at: null, cost: null,
    };
    expect(decode(detail, d.proposalDetail).kind).toBe('consolidation');
    expect(decode(detail, d.proposalDetail).decision?.decision).toBe('edit');
    expect(() => decode({ ...detail, decision: { decision: 'maybe', reason: null, at: null, actor: null } }, d.proposalDetail)).toThrowError(/decision: expected one of/);
  });

  test('ProposalDetail.decision reads actor_user_id, the wire key §5.4 actually sends', () => {
    const detail = {
      proposal_id: 'p1', kind: 'extraction', state: 'draft', scope: null, owner: null, target_skill_id: null, target_revision_id: null,
      sources: [], recipe: null, candidate: { path: 'a', body: '', sha256: null, frontmatter: null }, source_body: null,
      provenance: [], relations: [],
      decision: { decision_id: 'd1', decision: 'approve', reason: 'ok', actor_user_id: 'u1', expected_revision: 'rev-1', result_revision_id: 'rev-2', at: '2026-09-06T10:00:00Z' },
      expected_revision: 'rev-1', created_at: null, cost: null,
    };
    const value = decode(detail, d.proposalDetail);
    expect(value.decision?.actor).toBe('u1');
    expect(value.decision?.reason).toBe('ok');
    // A payload that already sends the short key (matching ProposalSummary) still decodes.
    const shortKey = { ...detail, decision: { ...detail.decision, actor_user_id: undefined, actor: 'u2' } };
    expect(decode(shortKey, d.proposalDetail).decision?.actor).toBe('u2');
    // Neither key present is Unknown (null), never an empty string.
    const noActor = { ...detail, decision: { ...detail.decision, actor_user_id: undefined } };
    expect(decode(noActor, d.proposalDetail).decision?.actor).toBeNull();
    // `actor ?? actor_user_id`: an explicit `actor: null` still falls through to actor_user_id,
    // not just an absent `actor` key — a known actor must never read as Unknown.
    const explicitNullActor = { ...detail, decision: { ...detail.decision, actor: null, actor_user_id: 'u1' } };
    expect(decode(explicitNullActor, d.proposalDetail).decision?.actor).toBe('u1');
  });

  test('ProposalSummary.decision (1.3.0) is null until decided, then carries decision/actor/at', () => {
    const undecided = decode({ items: [{ proposal_id: 'p1', kind: 'extraction', state: 'draft', scope: null, owner: null, target_skill_id: null, path: null, created_at: null }], next_cursor: null }, d.proposalList);
    expect(undecided.items[0].decision).toBeNull();
    const decided = decode({ items: [{ proposal_id: 'p1', kind: 'extraction', state: 'approved_for_export', scope: null, owner: null, target_skill_id: null, path: null, created_at: null, decision: { decision: 'approve', actor: 'u1', at: '2026-09-06T10:00:00Z' } }], next_cursor: null }, d.proposalList);
    expect(decided.items[0].decision).toEqual({ decision: 'approve', actor: 'u1', at: '2026-09-06T10:00:00Z' });
  });

  test('FeedbackEntry.actor (1.3.0) names the UI principal; null for an adapter-sourced judgment', () => {
    const revision = {
      revision_id: 'r1', content_sha256: null, body: null, frontmatter: null, source: null,
      references: [], requires: [], refines: [], relations: [], publication_status: 'draft',
      feedback: [
        { judgment_id: 'j1', verdict: 'helped', reason: null, source: 'ui', task_id: null, occurred_at: null, actor: 'u1' },
        { judgment_id: 'j2', verdict: 'helped', reason: null, source: 'adapter', task_id: null, occurred_at: null, actor: null },
      ],
      provenance: null,
    };
    const value = decode(revision, d.revision);
    expect(value.feedback[0].actor).toBe('u1');
    expect(value.feedback[1].actor).toBeNull();
  });

  test('an auth provider id is google or github (§5.1)', () => {
    expect(decode({ mode: 'dev', providers: [{ id: 'github', label: 'GitHub', login_url: '/x' }] }, d.authProviders).providers[0].id).toBe('github');
    expect(() => decode({ mode: 'dev', providers: [{ id: 'okta', label: 'Okta', login_url: '/x' }] }, d.authProviders)).toThrowError(/id: expected one of/);
  });

  // Contract §4.8/§4.9/§5.5a (ADR-0045, ADR-0046, changelog 1.6.0): `model` and `preferred` on
  // the credential, `summary` on the run and `phase`/`skills`/`proposals` on the target are all
  // new, required fields. A server that has not shipped them must fail loudly here, not render a
  // false zero or blank — that is the whole point of leaving them undecorated (no `fallback`).
  test('a model credential carries model and preferred, and a response missing either fails loudly', () => {
    const value = { provider: 'openrouter', name: 'default', last4: '9f2a', model: 'gpt-5.6', preferred: true, created_at: null, created_by: null };
    expect(decode(value, d.orgCredential).model).toBe('gpt-5.6');
    expect(decode(value, d.orgCredential).preferred).toBe(true);
    expect(() => decode({ ...value, model: undefined }, d.orgCredential)).toThrowError(/model: expected string/);
    expect(() => decode({ ...value, preferred: undefined }, d.orgCredential)).toThrowError(/preferred: expected boolean/);
  });

  test('a live run has no prompt, carries a summary, and a response missing it fails loudly', () => {
    const value = {
      run_id: 'r1', state: 'succeeded', provider: 'openrouter', model: 'gpt-5.6',
      created_by: null, created_at: '2026-09-12T00:00:00Z', started_at: null, finished_at: null,
      counts: { targets: 1, done: 1, failed: 0, skipped: 0 },
      summary: { skills_indexed: 3, proposals_created: 1 },
      cost: { tokens_in: 0, tokens_out: 0, usd: 0, usd_estimated: false }, error: null,
    };
    const run = decode(value, d.liveRun);
    expect(run.summary).toEqual({ skills_indexed: 3, proposals_created: 1 });
    expect((run as unknown as { prompt?: unknown }).prompt).toBeUndefined();
    expect(() => decode({ ...value, summary: undefined }, d.liveRun)).toThrowError(/summary: expected object/);
  });

  test('a live run target carries phase, skills and proposals; each is required', () => {
    const value = { repo_id: 'monorepo', state: 'running', job_id: null, phase: 'parse', skills: 4, proposals: 0, error: null, started_at: null, finished_at: null };
    expect(decode(value, d.liveRunTarget).phase).toBe('parse');
    expect(() => decode({ ...value, phase: 'thinking' }, d.liveRunTarget)).toThrowError(/phase: expected one of/);
    expect(() => decode({ ...value, skills: undefined }, d.liveRunTarget)).toThrowError(/skills: expected number/);
  });

  test('a live run event type is the eight-member 1.6.0 set; model.delta and finding are gone', () => {
    expect(d.liveRunEventTypes).toEqual(['run.started', 'repo.started', 'repo.fetched', 'repo.parsed', 'repo.proposed', 'repo.finished', 'run.finished', 'error']);
    expect(() => decode({ seq: 1, at: '2026-09-12T00:00:00Z', repo_id: null, type: 'model.delta', payload: { text: 'x' } }, d.liveRunEvent)).toThrowError(/type: expected one of/);
  });

  test('every live run event carries payload.text, printed verbatim; a response missing it fails loudly', () => {
    const value = { seq: 2, at: '2026-09-12T00:00:01Z', repo_id: 'monorepo', type: 'repo.parsed', payload: { text: 'Parsed 4 skills.', skills: 4, import_id: 'im-1' } };
    const event = decode(value, d.liveRunEvent);
    expect(event.payload.text).toBe('Parsed 4 skills.');
    expect(event.payload.skills).toBe(4); // extra, type-specific keys survive alongside `text`.
    expect(() => decode({ ...value, payload: { skills: 4 } }, d.liveRunEvent)).toThrowError(/payload\.text: expected string/);
  });
});
