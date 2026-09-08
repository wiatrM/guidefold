/** DataSource over the public Meridian fixture and the sessionStorage simulation.
 *
 * No network call, no private data: every value comes from `src/data/fixture.json` and from the
 * local scenario draft the operator saves in this browser tab. Public behaviour of the seven
 * routes is unchanged by this indirection.
 */
import { ApiError } from '../api/client';
import { knowledgeLayers } from '../api/decoders';
import type {
  AuditPage, AuthProviders, DecisionResult, DeviceApproval, DeviceStart, ExportPayload, Facets, FacetLookup,
  ImportCreated, ImportPlan, ImportStatus, Installation, Invitation, Judgment, KnowledgeLayer, MapLayers,
  MapRepository, MapScopes, Me, Member, ModulePage, Org, ProposalDetail, ProposalGenerationResult, ProposalList,
  Publication, Relations, Repo, Revision, Role, SkillDetail, SkillPage, SkillSummary, Snapshot, Usage,
} from '../api/decoders';
import type { FixtureAdapter } from '../data';
import { fixtureUsage } from './fixtureUsage';
import type { Session, Skill } from '../domain';
import type { DataSource, DraftStore, FacetQuery, LoginRedirect, OrgRepo, ProposalQuery, RelationQuery, SkillQuery } from './source';

export const fixtureSessionKey = 'guidefold-ui-meridian-v1';

/** Public simulation only. Private API data never uses browser storage (07-frontend). */
export function createFixtureDraftStore(key = fixtureSessionKey): DraftStore {
  const read = (): Session => {
    try {
      const value = JSON.parse(sessionStorage.getItem(key) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value as Session : {};
    } catch { return {}; }
  };
  let current = read();
  const listeners = new Set<() => void>();
  const publish = () => { for (const listener of listeners) listener(); };
  return {
    get: () => current,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    save(patch) {
      current = { ...current, ...patch };
      try { sessionStorage.setItem(key, JSON.stringify(current)); } catch { /* storage disabled */ }
      publish();
    },
    clear() {
      try { sessionStorage.removeItem(key); } catch { /* storage disabled */ }
      if (Object.keys(current).length === 0) return;
      current = {};
      publish();
    },
  };
}

const unsupported = (operation: string): never => {
  throw new ApiError({ status: 0, code: 'fixture_only', message: operation + ' is not part of the local fixture. Run the hosted API to exercise it.' });
};

export function createFixtureDataSource(adapter: FixtureAdapter, drafts: DraftStore = createFixtureDraftStore()): DataSource {
  const { fixture, findSkill, sourceURL } = adapter;
  /** The fixture labels every skill "Unclassified"; the contract domain is lower case (§5.3). */
  const layerOf = (skill: Skill): KnowledgeLayer | null => {
    const value = skill.knowledgeLayer.toLowerCase();
    return (knowledgeLayers as readonly string[]).includes(value) ? value as KnowledgeLayer : null;
  };
  const summary = (skill: Skill): SkillSummary => ({
    skill_id: skill.id, name: skill.name, description: skill.description,
    scope: skill.scope, owner: skill.owner,
    source_layer: skill.sourceLayer, knowledge_layer: layerOf(skill), source_status: skill.sourceStatus,
    publication_status: 'draft', path: skill.path,
    content_sha256: skill.revision, revision_id: skill.revision, card_revision: null,
    package_digest: null, commit: fixture.commit, updated_at: null,
  });
  const fixtureOrg = (): Org => ({
    org_id: fixture.org, slug: fixture.org, name: fixture.label,
    my_role: 'owner', created_at: null,
    counts: { members: 1 + (drafts.get().members?.length ?? 0), repos: 1 },
  });
  const identity = (): Me => ({
    user: { id: 'fixture-operator', email: 'operator@' + fixture.org + '.fixture', name: 'Fixture operator' },
    identities: drafts.get().login ? [{ provider: drafts.get().login as string, created_at: null }] : [],
    orgs: [{ org_id: fixture.org, slug: fixture.org, name: fixture.label, role: 'owner' }],
    csrf_token: null,
    access: { checked_at: null, valid_for_s: 45 },
    link_suggestions: [],
  });
  const fixtureImport = (): ImportStatus => {
    const files = fixture.skills.map(skill => ({
      path: skill.path, sha256: skill.revision, size: skill.bytes, kind: 'skill' as const,
      status: 'accepted' as const, reason: null, skill_id: skill.id,
    }));
    return {
      import_id: 'fixture-import', state: drafts.get().imported ? 'ready' : 'created',
      manifest_digest: fixture.commit, commit: fixture.commit, complete: true,
      counts: {
        files: files.length, accepted: files.length, omitted: 0, failed: 0,
        new_blobs: 0, reused_blobs: files.length, skills: files.length, documents: 0,
      },
      files, files_truncated: false, jobs: [], publication: { snapshot_id: null, state: 'none', error: null },
      created_at: null, updated_at: null,
    };
  };
  const values = (pick: (skill: Skill) => string) => {
    const counts = new Map<string, number>();
    for (const skill of fixture.skills) counts.set(pick(skill), (counts.get(pick(skill)) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([value, count]) => ({ value, count }));
  };
  const facetField = (field: string): ((skill: Skill) => string) =>
    field === 'owner' ? skill => skill.owner
      : field === 'layer' ? skill => skill.sourceLayer
        : field === 'status' ? skill => skill.sourceStatus
          : skill => skill.scope;

  return {
    mode: 'fixture',
    drafts,

    async getAuthProviders(): Promise<AuthProviders> {
      return { mode: 'dev', providers: [{ id: 'google', label: 'Google', login_url: '' }, { id: 'github', label: 'GitHub', login_url: '' }] };
    },
    async startLogin(provider: string): Promise<LoginRedirect> {
      drafts.save({ login: provider });
      return { loginUrl: '', provider };
    },
    async getMe(): Promise<Me> { return identity(); },
    async logout(): Promise<void> { drafts.clear(); },
    async startDeviceAuthorization(): Promise<DeviceStart> { return unsupported('Device authorization'); },
    async decideDevice(): Promise<DeviceApproval> { return unsupported('Device approval'); },
    async startIdentityLink(): Promise<LoginRedirect> { return unsupported('Identity linking'); },

    async listOrgs(): Promise<Org[]> { return drafts.get().org ? [fixtureOrg()] : []; },
    async getOrg(): Promise<Org> { return fixtureOrg(); },
    async createOrg(): Promise<Org> { drafts.save({ org: true }); return fixtureOrg(); },
    async listMembers(): Promise<Member[]> {
      const extra = drafts.get().members ?? [];
      return [
        { user_id: 'fixture-operator', email: 'operator@' + fixture.org + '.fixture', name: 'Fixture operator', role: 'owner', joined_at: null },
        ...extra.map((label, index) => ({ user_id: 'local-' + index, email: label, name: label, role: 'member' as Role, joined_at: null })),
      ];
    },
    async inviteMember(_org: string, input: { email: string; role: Role }): Promise<Invitation> {
      const members = drafts.get().members ?? [];
      drafts.save({ members: [...members, input.email] });
      return { invitation_id: 'local-' + members.length, accept_url: '', expires_at: null, email: input.email, role: input.role };
    },
    async changeMemberRole(): Promise<Member> { return unsupported('Role change'); },
    async removeMember(_org: string, userId: string): Promise<void> {
      const members = drafts.get().members ?? [];
      const index = Number(userId.replace('local-', ''));
      drafts.save({ members: members.filter((_, position) => position !== index) });
    },
    async listInstallations(): Promise<Installation[]> {
      if (!drafts.get().token) return [];
      return [{
        installation_id: 'fixture-installation', name: 'Local scenario token', repo_id: fixture.repo,
        scopes: ['search', 'use', 'events'], harness: null,
        last_seen_at: null, adapter_version: null, capabilities: null, created_at: null, token: null,
      }];
    },
    async createInstallation(): Promise<Installation> {
      drafts.save({ token: true });
      return {
        installation_id: 'fixture-installation', name: 'Local scenario token', repo_id: fixture.repo,
        scopes: ['search', 'use', 'events'], harness: null,
        last_seen_at: null, adapter_version: null, capabilities: null, created_at: null, token: null,
      };
    },
    async revokeInstallation(): Promise<void> { drafts.save({ token: false }); },
    async getAudit(): Promise<AuditPage> { return unsupported('Audit log'); },

    async listRepos(): Promise<Repo[]> {
      return [{ repo_id: fixture.repo, name: fixture.repo, git_host_url: sourceURL('').replace(/\/blob\/.*$/, ''), created_at: null, created: false }];
    },
    // The fixture repository always existed; nothing is registered by this call.
    async createRepo(): Promise<Repo> { return { repo_id: fixture.repo, name: fixture.repo, git_host_url: null, created_at: null, created: false }; },
    async listImports(): Promise<ImportStatus[]> { return drafts.get().imported ? [fixtureImport()] : []; },
    async createImport(): Promise<ImportCreated> {
      drafts.save({ imported: true });
      return { import_id: 'fixture-import', state: 'created', missing_blobs: [], limits: null, reused_import_id: null };
    },
    async getImport(): Promise<ImportStatus> { return fixtureImport(); },
    async cancelImport(): Promise<void> { drafts.save({ imported: false }); },
    async getImportPlan(): Promise<ImportPlan> {
      // A fixed, offline estimate: the fixture never calls a model, so there is nothing to price live.
      return {
        groups: [{
          group_id: 'fixture-group-1', kind: 'extraction', scope: fixture.nodes[0]?.id ?? '_root', owner: null,
          inputs: [fixture.repo], n_inputs: 1, estimated_tokens: 1200, estimated_calls: 1,
        }],
        limits: { max_files: 20, max_bytes: 1048576, max_groups: 5, max_proposals_per_group: 5, max_neighbours: 10, max_tokens: null, max_calls: null, max_usd: null },
        estimated_usd_max: 0,
        estimated_calls: 1,
        groups_skipped: {},
        generator: { name: 'none', configured: false, generator: 'none', version: '', model: null },
      };
    },
    async generateProposals(): Promise<ProposalGenerationResult> { return unsupported('Proposal generation'); },

    async listSkills(_target: OrgRepo, query: SkillQuery): Promise<SkillPage> {
      const needle = (query.q ?? '').toLowerCase();
      const items = fixture.skills.filter(skill =>
        (!needle || (skill.name + ' ' + skill.description + ' ' + skill.path).toLowerCase().includes(needle))
        && (!query.scope || skill.scope === query.scope)
        && (!query.owner || skill.owner === query.owner)
        && (!query.layer || skill.sourceLayer === query.layer)
        && (!query.status || skill.sourceStatus === query.status)).map(summary);
      return { items, next_cursor: null, snapshot_id: null, schema_version: 'fixture', filters: {} };
    },
    async getFacets(_target: OrgRepo, query: FacetQuery): Promise<Facets> {
      return { field: query.field, values: values(facetField(query.field)), next_cursor: null };
    },
    async lookupFacet(_target: OrgRepo, field: string, value: string): Promise<FacetLookup> {
      const found = values(facetField(field)).find(entry => entry.value === value);
      return { field, value, count: found?.count ?? 0, available: Boolean(found) };
    },
    async getSkill(_target: OrgRepo, skillId: string): Promise<SkillDetail> {
      const skill = findSkill(skillId);
      if (!skill) throw new ApiError({ status: 404, code: 'not_found', message: 'No such skill in this fixture.' });
      return { ...summary(skill), revisions: [{ revision_id: skill.revision, content_sha256: skill.revision, card_revision: null, commit: fixture.commit, import_id: 'fixture-import', created_at: null, source: 'import' }] };
    },
    async getRevision(_target: OrgRepo, skillId: string): Promise<Revision> {
      const skill = findSkill(skillId);
      if (!skill) throw new ApiError({ status: 404, code: 'revision_not_found', message: 'No such revision in this fixture.' });
      return {
        revision_id: skill.revision, content_sha256: skill.revision, card_revision: null, body: skill.body,
        frontmatter: null,
        source: { path: skill.path, commit: fixture.commit, url: sourceURL(skill.path) },
        references: skill.references.map(path => ({ path, sha256: null, size: null, type: null, required: false, available: false })),
        requires: skill.requires, refines: skill.refines, relations: [], feedback: [],
        provenance: { origin: 'source', import_id: 'fixture-import', proposal_id: null },
        publication_status: 'draft',
      };
    },
    async getRevisionRaw(_target: OrgRepo, skillId: string): Promise<string> {
      const skill = findSkill(skillId);
      if (!skill) throw new ApiError({ status: 404, code: 'revision_not_found', message: 'No such revision in this fixture.' });
      return skill.raw;
    },
    async sendFeedback(): Promise<Judgment> { return { judgment_id: 'fixture-judgment' }; },

    async getMapRepository(_target: OrgRepo, path = ''): Promise<MapRepository> {
      const prefix = path ? path.replace(/\/$/, '') + '/' : '';
      const children = new Map<string, { name: string; path: string; kind: 'dir' | 'skill'; skill_id: string | null; count: number }>();
      for (const skill of fixture.skills) {
        if (!skill.path.startsWith(prefix)) continue;
        const rest = skill.path.slice(prefix.length);
        const cut = rest.indexOf('/');
        const name = cut === -1 ? rest : rest.slice(0, cut);
        const entry = children.get(name) ?? { name, path: prefix + name, kind: cut === -1 ? 'skill' : 'dir', skill_id: cut === -1 ? skill.id : null, count: 0 };
        entry.count += 1;
        children.set(name, entry);
      }
      return { path, children: [...children.values()].sort((a, b) => a.name.localeCompare(b.name)), next_cursor: null };
    },
    async getMapScopes(_target: OrgRepo, scope?: string): Promise<MapScopes> {
      const node = fixture.nodes.find(entry => entry.id === scope) ?? null;
      const mapped = new Set(fixture.skills.filter(skill => fixture.nodes.some(entry => entry.id === skill.scope)).map(skill => skill.id));
      return {
        scope: node ? { id: node.id, owner: node.owner, paths: node.paths, parent: null } : null,
        children: fixture.nodes.filter(entry => !scope || entry.id.startsWith(scope + '.')).map(entry => ({ id: entry.id, owner: entry.owner, skills: fixture.skills.filter(skill => skill.scope === entry.id).length })),
        skills: fixture.skills.filter(skill => !scope || skill.scope === scope).map(skill => ({ skill_id: skill.id, name: skill.name })),
        unmapped: fixture.skills.filter(skill => !mapped.has(skill.id)).map(skill => ({ skill_id: skill.id, name: skill.name })),
      };
    },
    async getMapLayers(): Promise<MapLayers> {
      const counts = new Map<KnowledgeLayer, number>();
      for (const skill of fixture.skills) {
        const layer = layerOf(skill);
        if (layer) counts.set(layer, (counts.get(layer) ?? 0) + 1);
      }
      return { layers: [...counts.entries()].map(([layer, count]) => ({ layer, count })) };
    },
    async getRelations(_target: OrgRepo, query: RelationQuery): Promise<Relations> {
      const items = fixture.skills
        .filter(skill => !query.skillId || skill.id === query.skillId)
        .flatMap(skill => [
          ...skill.requires.map(to => ({ from: skill.id, to, type: 'requires' as const, provenance: 'source', revision: skill.revision })),
          ...skill.refines.map(to => ({ from: skill.id, to, type: 'refines' as const, provenance: 'source', revision: skill.revision })),
        ])
        .filter(edge => !query.type || edge.type === query.type);
      return { items, next_cursor: null, truncated: false };
    },
    async getModule(_target: OrgRepo, scope: string): Promise<ModulePage> {
      const node = fixture.nodes.find(entry => entry.id === scope);
      const skills = fixture.skills.filter(skill => skill.scope === scope);
      return {
        scope, owner: node?.owner ?? null, skills: skills.map(summary),
        reading_order: skills.map(skill => skill.id), shared: [],
        documents: [],
      };
    },

    async listProposals(_target: OrgRepo, query: ProposalQuery): Promise<ProposalList> {
      const draft = drafts.get().proposal;
      if (!draft || (query.state && query.state !== draft.stage)) return { items: [], next_cursor: null };
      return {
        items: [{
          proposal_id: 'fixture-proposal', kind: 'enrichment', state: draft.stage === 'editing' ? 'draft' : draft.stage,
          scope: adapter.proposalSkill.scope, owner: adapter.proposalSkill.owner,
          target_skill_id: adapter.proposalSkill.id, path: adapter.proposalSkill.path, created_at: null,
        }],
        next_cursor: null,
      };
    },
    async getProposal(): Promise<ProposalDetail> { return unsupported('Proposal detail'); },
    async decideProposal(): Promise<DecisionResult> { return unsupported('Proposal decision'); },
    async exportProposal(): Promise<ExportPayload> { return unsupported('Proposal export'); },
    async getProposalPublication(): Promise<Publication> { return unsupported('Publication state'); },

    async listSnapshots(): Promise<Snapshot[]> { return []; },
    async activateSnapshot(): Promise<Snapshot> { return unsupported('Snapshot activation'); },
    async publish(): Promise<{ job_id: string }> { return unsupported('Publication'); },

    /** Simulated ledger (`fixtureUsage`), labelled as such wherever it is shown; the fixture repository has no adapter events. */
    async getUsage(): Promise<Usage> { return fixtureUsage; },
    async exportUsage(): Promise<string> { return ''; },
    async decideQueueItem(): Promise<void> { return unsupported('Queue decision'); },
  };
}

export type FixtureDataSource = ReturnType<typeof createFixtureDataSource>;
