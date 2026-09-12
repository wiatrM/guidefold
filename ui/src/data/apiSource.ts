/** DataSource over the management API.
 *
 * Every read goes to the API. There is no response cache: contract §3 puts `Cache-Control:
 * no-store` on every `/api/v1` answer, so a cache here could only ever hold what the service
 * told us not to keep. Switching user, org, repo or policy still bumps the access generation,
 * which voids answers already in flight for the previous context. Mutations carry the caller's
 * stable Idempotency-Key and, where a re-read exists, a confirmation step the client uses after
 * a timeout.
 */
import { ApiClient, ApiError, type RequestSpec } from '../api/client';
import { AccessController } from '../api/access';
import * as d from '../api/decoders';
import type {
  AuditPage, AuthProviders, DecisionResult, DeviceApproval, DeviceStart, ExportPayload, Facets, FacetLookup,
  ImportCreated, ImportPlan, ImportStatus, Installation, Invitation, InvitationAccepted, InvitationLifecycle, Judgment, MapLayers, MapRepository, MapScopes,
  Me, Member, ModulePage, Org, Profile, ProposalDetail, ProposalGenerationResult, ProposalKind, ProposalList,
  ProposalLimits, Publication, Relations, Repo, Revision, Role, SkillDetail, SkillPage, Snapshot, Usage,
  Team, GitHubInstallation, RepoAccess, RepoAccessLevel, Reviewer,
  OrgCredential, OrgCredentialProvider, LiveRun, LiveRunDetail, LiveRunEventPage, LiveRunPage,
} from '../api/decoders';
import type { Session } from '../domain';
import type { DataSource, DraftStore, FacetQuery, LoginRedirect, OrgRepo, ProposalQuery, RelationQuery, SkillQuery, UsageQuery } from './source';

/** Drafts live in RAM only and are dropped with the access generation. */
export function createMemoryDraftStore(): DraftStore {
  let current: Session = {};
  const listeners = new Set<() => void>();
  const publish = () => { for (const listener of listeners) listener(); };
  return {
    get: () => current,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    save(patch) { current = { ...current, ...patch }; publish(); },
    clear() { if (Object.keys(current).length === 0) return; current = {}; publish(); },
  };
}

export interface ApiDataSourceOptions {
  client?: ApiClient;
  drafts?: DraftStore;
  /** Called for every 401/403, wherever it is observed. */
  onDenied?: (error: ApiError) => void;
}

export interface ApiDataSource extends DataSource {
  readonly client: ApiClient;
  /** Switching user, org, repo or policy voids in-flight answers for the previous context. */
  setContext(next: { user?: string | null; org?: string | null; repo?: string | null; policy?: string | null }): void;
  /** 401/403 handling: clear drafts, cancel in-flight, bump the generation. */
  revoke(reason: string): void;
}

interface Namespace { user: string | null; org: string | null; repo: string | null; policy: string | null }
const namespaceKey = (value: Namespace): string =>
  [value.user, value.org, value.repo, value.policy].map(part => part ?? '-').join('/');

const target = (t: OrgRepo) => '/orgs/' + encodeURIComponent(t.org) + '/repos/' + encodeURIComponent(t.repo);
const skillPath = (t: OrgRepo, skillId: string) => target(t) + '/skills/' + encodeURIComponent(skillId);

export function createApiDataSource(options: ApiDataSourceOptions = {}): ApiDataSource {
  const client = options.client ?? new ApiClient();
  const drafts = options.drafts ?? createMemoryDraftStore();
  let context: Namespace = { user: null, org: null, repo: null, policy: null };

  /** A denial anywhere means the whole context must stop revealing data. */
  const guard = (error: unknown): never => {
    if (error instanceof ApiError && error.denied) options.onDenied?.(error);
    throw error;
  };
  const read = async <T>(spec: Omit<RequestSpec<T>, 'method'>): Promise<T> => {
    try { return (await client.request({ ...spec, method: 'GET' })).value; } catch (error) { return guard(error); }
  };
  const write = async <T>(spec: RequestSpec<T>): Promise<T> => {
    try { return (await client.request(spec)).value; } catch (error) { return guard(error); }
  };

  const source: ApiDataSource = {
    drafts,
    client,

    setContext(next) {
      const merged: Namespace = { ...context, ...next };
      if (namespaceKey(merged) === namespaceKey(context)) return;
      context = merged;
      client.bumpGeneration('context_change');
    },
    revoke(reason) {
      drafts.clear();
      client.setCsrfToken(null);
      client.bumpGeneration(reason);
    },

    // Auth and identity -----------------------------------------------------
    getAuthProviders(): Promise<AuthProviders> {
      return read({ path: '/auth/providers', decode: d.authProviders, resource: 'auth/providers' });
    },
    async startLogin(provider: string, returnTo: string): Promise<LoginRedirect> {
      const providers = await source.getAuthProviders();
      const entry = providers.providers.find(item => item.id === provider);
      if (!entry) throw new ApiError({ status: 400, code: 'unknown_provider', message: 'This provider is not configured.' });
      const separator = entry.login_url.includes('?') ? '&' : '?';
      return { provider, loginUrl: entry.login_url + separator + 'return_to=' + encodeURIComponent(returnTo) };
    },
    async getMe(timeoutMs?: number): Promise<Me> {
      const me = await read({ path: '/me', decode: d.me, resource: 'me', retries: 0, timeoutMs });
      client.setCsrfToken(me.csrf_token);
      return me;
    },
    async logout(idempotencyKey: string): Promise<void> {
      try { await write({ path: '/auth/logout', method: 'POST', decode: d.nothing, resource: 'auth/logout', idempotencyKey }); }
      finally { source.revoke('logout'); }
    },
    startDeviceAuthorization(idempotencyKey: string): Promise<DeviceStart> {
      return write({ path: '/auth/device', method: 'POST', decode: d.deviceStart, resource: 'auth/device', idempotencyKey });
    },
    decideDevice(userCode: string, approve: boolean, idempotencyKey: string): Promise<DeviceApproval> {
      return write({
        path: approve ? '/auth/device/approve' : '/auth/device/deny',
        method: 'POST', body: { user_code: userCode },
        decode: d.deviceApproval, resource: 'auth/device/' + userCode, idempotencyKey,
      });
    },
    async startIdentityLink(provider: string, idempotencyKey: string): Promise<LoginRedirect> {
      const result = await write({
        path: '/me/identities/link/start', method: 'POST', body: { provider },
        decode: d.identityLinkStart, resource: 'identity-link/' + provider, idempotencyKey,
      });
      return { provider, loginUrl: result.login_url };
    },
    updateProfile(name: string, idempotencyKey: string): Promise<Profile> {
      return write({ path: '/me/profile', method: 'PATCH', body: { name }, decode: d.profile, resource: 'profile', idempotencyKey });
    },

    // Organizations ---------------------------------------------------------
    listOrgs(): Promise<Org[]> {
      return read({ path: '/orgs', decode: d.orgList, resource: 'orgs' });
    },
    getOrg(org: string): Promise<Org> {
      return read({ path: '/orgs/' + encodeURIComponent(org), decode: d.org, resource: 'org/' + org });
    },
    createOrg(input: { name: string; slug: string }, idempotencyKey: string): Promise<Org> {
      return write({ path: '/orgs', method: 'POST', body: input, decode: d.org, resource: 'create-org/' + input.slug, idempotencyKey });
    },
    listMembers(org: string): Promise<Member[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/members', decode: d.memberList, resource: 'members/' + org });
    },
    listTeams(org: string): Promise<Team[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/teams', decode: d.teamList, resource: 'teams/' + org });
    },
    createTeam(org: string, name: string, idempotencyKey: string): Promise<Team> {
      return write({ path: '/orgs/' + encodeURIComponent(org) + '/teams', method: 'POST', body: { name }, decode: d.team, resource: 'create-team/' + org + '/' + name, idempotencyKey });
    },
    async addTeamMember(org: string, teamId: string, userId: string, idempotencyKey: string): Promise<void> {
      await write({ path: '/orgs/' + encodeURIComponent(org) + '/teams/' + encodeURIComponent(teamId) + '/members/' + encodeURIComponent(userId), method: 'PUT', decode: d.ok, resource: 'team-member/' + org + '/' + teamId + '/' + userId, idempotencyKey });
    },
    async removeTeamMember(org: string, teamId: string, userId: string, idempotencyKey: string): Promise<void> {
      await write({ path: '/orgs/' + encodeURIComponent(org) + '/teams/' + encodeURIComponent(teamId) + '/members/' + encodeURIComponent(userId), method: 'DELETE', decode: d.ok, resource: 'team-member/' + org + '/' + teamId + '/' + userId, idempotencyKey });
    },
    inviteMember(org: string, input: { email: string; role: Role }, idempotencyKey: string): Promise<Invitation> {
      return write({ path: '/orgs/' + encodeURIComponent(org) + '/invitations', method: 'POST', body: input, decode: d.invitation, resource: 'invite/' + org + '/' + input.email, idempotencyKey });
    },
    listInvitations(org: string): Promise<InvitationLifecycle[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/invitations', decode: d.invitationLifecycleList, resource: 'invitations/' + org });
    },
    async revokeInvitation(org: string, invitationId: string, idempotencyKey: string): Promise<void> {
      await write({ path: '/orgs/' + encodeURIComponent(org) + '/invitations/' + encodeURIComponent(invitationId), method: 'DELETE', decode: d.ok, resource: 'invitation/' + org + '/' + invitationId, idempotencyKey });
    },
    acceptInvitation(token: string, idempotencyKey: string): Promise<InvitationAccepted> {
      return write({ path: '/invitations/' + encodeURIComponent(token) + '/accept', method: 'POST', decode: d.invitationAccepted, resource: 'accept-invitation/' + token, idempotencyKey });
    },
    changeMemberRole(org: string, userId: string, role: Role, idempotencyKey: string): Promise<Member> {
      return write({
        path: '/orgs/' + encodeURIComponent(org) + '/members/' + encodeURIComponent(userId),
        method: 'PATCH', body: { role }, decode: d.member, resource: 'member/' + org + '/' + userId, idempotencyKey,
        confirm: async () => (await source.listMembers(org)).find(entry => entry.user_id === userId && entry.role === role) ?? null,
      });
    },
    async removeMember(org: string, userId: string, idempotencyKey: string): Promise<void> {
      await write({
        path: '/orgs/' + encodeURIComponent(org) + '/members/' + encodeURIComponent(userId),
        method: 'DELETE', decode: d.ok, resource: 'member/' + org + '/' + userId, idempotencyKey,
        confirm: async () => (await source.listMembers(org)).some(entry => entry.user_id === userId) ? null : true,
      });
    },
    listInstallations(org: string): Promise<Installation[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/installations', decode: d.installationList, resource: 'installations/' + org });
    },
    createInstallation(org: string, input: { name: string; repo_id?: string | null; scopes: string[]; harness?: string | null }, idempotencyKey: string): Promise<Installation> {
      return write({ path: '/orgs/' + encodeURIComponent(org) + '/installations', method: 'POST', body: input, decode: d.installation, resource: 'create-installation/' + org + '/' + input.name, idempotencyKey });
    },
    async revokeInstallation(org: string, installationId: string, idempotencyKey: string): Promise<void> {
      await write({
        path: '/orgs/' + encodeURIComponent(org) + '/installations/' + encodeURIComponent(installationId),
        method: 'DELETE', decode: d.nothing, resource: 'installation/' + org + '/' + installationId, idempotencyKey,
      });
    },
    listGitHubInstallations(org: string): Promise<GitHubInstallation[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/github/installations', decode: d.githubInstallationList, resource: 'github-installations/' + org });
    },
    async deleteGitHubInstallation(org: string, installationId: number, idempotencyKey: string): Promise<void> {
      await write({ path: '/orgs/' + encodeURIComponent(org) + '/github/installations/' + encodeURIComponent(String(installationId)), method: 'DELETE', decode: d.ok, resource: 'github-installation/' + org + '/' + installationId, idempotencyKey });
    },
    getAudit(org: string, cursor?: string): Promise<AuditPage> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/audit', query: { cursor }, decode: d.auditPage, resource: 'audit/' + org });
    },

    // Model keys --------------------------------------------------------------
    listCredentials(org: string): Promise<OrgCredential[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/credentials', decode: d.orgCredentialList, resource: 'credentials/' + org });
    },
    setCredential(org: string, provider: OrgCredentialProvider, input: { api_key: string; name?: string | null }, idempotencyKey: string): Promise<OrgCredential> {
      return write({
        path: '/orgs/' + encodeURIComponent(org) + '/credentials/' + encodeURIComponent(provider),
        method: 'PUT', body: input, decode: d.orgCredential, resource: 'credential/' + org + '/' + provider, idempotencyKey,
      });
    },
    async deleteCredential(org: string, provider: OrgCredentialProvider, idempotencyKey: string): Promise<void> {
      await write({
        path: '/orgs/' + encodeURIComponent(org) + '/credentials/' + encodeURIComponent(provider),
        method: 'DELETE', decode: d.ok, resource: 'credential/' + org + '/' + provider, idempotencyKey,
      });
    },

    // Live Agent ----------------------------------------------------------------
    listLiveRuns(org: string, cursor?: string): Promise<LiveRunPage> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/live/runs', query: { cursor }, decode: d.liveRunPage, resource: 'live-runs/' + org });
    },
    getLiveRun(org: string, runId: string): Promise<LiveRunDetail> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/live/runs/' + encodeURIComponent(runId), decode: d.liveRunDetail, resource: 'live-run/' + org + '/' + runId });
    },
    getLiveRunEvents(org: string, runId: string, after?: number): Promise<LiveRunEventPage> {
      // Its own resource key per run (not shared with getLiveRun): the poll loop below issues
      // both every tick, and a superseded run detail must not void the events page, or vice versa.
      return read({
        path: '/orgs/' + encodeURIComponent(org) + '/live/runs/' + encodeURIComponent(runId) + '/events',
        query: { after }, decode: d.liveRunEventPage, resource: 'live-run-events/' + org + '/' + runId,
      });
    },
    startLiveRun(org: string, input: { prompt: string; provider?: OrgCredentialProvider; model?: string; repos?: string[] }, idempotencyKey: string): Promise<LiveRun> {
      return write({ path: '/orgs/' + encodeURIComponent(org) + '/live/runs', method: 'POST', body: input, decode: d.liveRun, resource: 'live-runs/' + org, idempotencyKey });
    },
    cancelLiveRun(org: string, runId: string, idempotencyKey: string): Promise<LiveRun> {
      return write({
        path: '/orgs/' + encodeURIComponent(org) + '/live/runs/' + encodeURIComponent(runId) + '/cancel',
        method: 'POST', decode: d.liveRun, resource: 'live-run/' + org + '/' + runId, idempotencyKey,
      });
    },

    // Repositories and import -----------------------------------------------
    listRepos(org: string): Promise<Repo[]> {
      return read({ path: '/orgs/' + encodeURIComponent(org) + '/repos', decode: d.repoList, resource: 'repos/' + org });
    },
    createRepo(org: string, input: { repo_id: string; name?: string | null; git_host_url?: string | null }, idempotencyKey: string): Promise<Repo> {
      return write({
        path: '/orgs/' + encodeURIComponent(org) + '/repos', method: 'POST', body: input,
        decode: d.repo, resource: 'create-repo/' + org + '/' + input.repo_id, idempotencyKey,
        confirm: async () => (await source.listRepos(org)).find(entry => entry.repo_id === input.repo_id) ?? null,
      });
    },
    listRepoAccess(t: OrgRepo): Promise<RepoAccess[]> {
      return read({ path: target(t) + '/access', decode: d.repoAccessList, resource: 'repo-access/' + t.org + '/' + t.repo });
    },
    setRepoAccess(t: OrgRepo, userId: string, access: RepoAccessLevel, idempotencyKey: string): Promise<RepoAccess> {
      return write({ path: target(t) + '/access/' + encodeURIComponent(userId), method: 'PUT', body: { access }, decode: d.repoAccess, resource: 'repo-access/' + t.org + '/' + t.repo + '/' + userId, idempotencyKey });
    },
    async removeRepoAccess(t: OrgRepo, userId: string, idempotencyKey: string): Promise<void> {
      await write({ path: target(t) + '/access/' + encodeURIComponent(userId), method: 'DELETE', decode: d.ok, resource: 'repo-access/' + t.org + '/' + t.repo + '/' + userId, idempotencyKey });
    },
    listReviewers(t: OrgRepo): Promise<Reviewer[]> {
      return read({ path: target(t) + '/reviewers', decode: d.reviewerList, resource: 'repo-reviewers/' + t.org + '/' + t.repo });
    },
    async assignReviewer(t: OrgRepo, userId: string, idempotencyKey: string): Promise<void> {
      await write({ path: target(t) + '/reviewers/' + encodeURIComponent(userId), method: 'PUT', decode: d.ok, resource: 'repo-reviewers/' + t.org + '/' + t.repo + '/' + userId, idempotencyKey });
    },
    async removeReviewer(t: OrgRepo, userId: string, idempotencyKey: string): Promise<void> {
      await write({ path: target(t) + '/reviewers/' + encodeURIComponent(userId), method: 'DELETE', decode: d.ok, resource: 'repo-reviewers/' + t.org + '/' + t.repo + '/' + userId, idempotencyKey });
    },
    listImports(t: OrgRepo, cursor?: string): Promise<ImportStatus[]> {
      return read({ path: target(t) + '/imports', query: { cursor }, decode: d.importStatusList, resource: 'imports/' + t.org + '/' + t.repo });
    },
    async createImport(t: OrgRepo, manifest: unknown, idempotencyKey: string): Promise<ImportCreated> {
      return await write({
        path: target(t) + '/imports', method: 'POST',
        body: { idempotency_key: idempotencyKey, manifest },
        decode: d.importCreated, resource: 'create-import/' + t.org + '/' + t.repo, idempotencyKey,
      });
    },
    async uploadImportBlob(t: OrgRepo, importId: string, sha256: string, bytes: Uint8Array): Promise<void> {
      await write({ path: target(t) + '/imports/' + encodeURIComponent(importId) + '/blobs/' + encodeURIComponent(sha256), method: 'PUT', body: bytes, decode: d.ok, resource: 'blob/' + t.org + '/' + t.repo + '/' + importId + '/' + sha256, contentType: 'application/octet-stream', idempotencyKey: 'blob:' + importId + ':' + sha256 });
    },
    finalizeImport(t: OrgRepo, importId: string, idempotencyKey: string): Promise<ImportStatus> {
      return write({ path: target(t) + '/imports/' + encodeURIComponent(importId) + '/finalize', method: 'POST', body: {}, decode: d.importStatus, resource: 'finalize-import/' + t.org + '/' + t.repo + '/' + importId, idempotencyKey });
    },
    getImport(t: OrgRepo, importId: string): Promise<ImportStatus> {
      return read({ path: target(t) + '/imports/' + encodeURIComponent(importId), decode: d.importStatus, resource: 'import/' + t.org + '/' + t.repo + '/' + importId });
    },
    async cancelImport(t: OrgRepo, importId: string, idempotencyKey: string): Promise<void> {
      await write({ path: target(t) + '/imports/' + encodeURIComponent(importId) + '/cancel', method: 'POST', body: { idempotency_key: idempotencyKey }, decode: d.nothing, resource: 'import/' + t.org + '/' + t.repo + '/' + importId, idempotencyKey });
    },
    getImportPlan(t: OrgRepo, importId: string, kinds: ProposalKind[]): Promise<ImportPlan> {
      // Never cached: the estimate must be current at the moment the operator decides to start (contract §4.2).
      return read({
        path: target(t) + '/imports/' + encodeURIComponent(importId) + '/plan',
        query: { kinds: kinds.length ? kinds.join(',') : undefined },
        decode: d.importPlan, resource: 'import-plan/' + t.org + '/' + t.repo + '/' + importId,
      });
    },
    generateProposals(t: OrgRepo, importId: string, input: { kinds: ProposalKind[]; limits: Partial<ProposalLimits> }, idempotencyKey: string): Promise<ProposalGenerationResult> {
      return write({
        path: target(t) + '/imports/' + encodeURIComponent(importId) + '/proposals:generate', method: 'POST',
        body: { idempotency_key: idempotencyKey, kinds: input.kinds, limits: input.limits },
        decode: d.proposalGenerationResult, resource: 'generate-proposals/' + t.org + '/' + t.repo + '/' + importId, idempotencyKey,
      });
    },

    // Knowledge -------------------------------------------------------------
    listSkills(t: OrgRepo, query: SkillQuery): Promise<SkillPage> {
      const filters = { q: query.q, scope: query.scope, owner: query.owner, layer: query.layer, status: query.status, limit: query.limit };
      return read({ path: target(t) + '/skills', query: { ...filters, cursor: query.cursor, snapshot_id: query.snapshotId }, decode: d.skillPage, resource: 'skills/' + t.org + '/' + t.repo });
    },
    getFacets(t: OrgRepo, query: FacetQuery): Promise<Facets> {
      return read({ path: target(t) + '/skills/facets', query: { field: query.field, q: query.q, cursor: query.cursor }, decode: d.facets, resource: 'facets/' + t.org + '/' + t.repo + '/' + query.field });
    },
    lookupFacet(t: OrgRepo, field: string, value: string): Promise<FacetLookup> {
      return read({ path: target(t) + '/skills/facets/lookup', query: { field, value }, decode: d.facetLookup, resource: 'facet-lookup/' + t.org + '/' + t.repo + '/' + field });
    },
    getSkill(t: OrgRepo, skillId: string): Promise<SkillDetail> {
      return read({ path: skillPath(t, skillId), decode: d.skillDetail, resource: 'skill/' + t.org + '/' + t.repo + '/' + skillId });
    },
    getRevision(t: OrgRepo, skillId: string, revisionId: string): Promise<Revision> {
      return read({ path: skillPath(t, skillId) + '/revisions/' + encodeURIComponent(revisionId), decode: d.revision, resource: 'revision/' + t.org + '/' + t.repo + '/' + skillId });
    },
    getRevisionRaw(t: OrgRepo, skillId: string, revisionId: string): Promise<string> {
      return read({ path: skillPath(t, skillId) + '/revisions/' + encodeURIComponent(revisionId) + '/raw', responseType: 'text', decode: d.str, resource: 'revision-raw/' + t.org + '/' + t.repo + '/' + skillId });
    },
    sendFeedback(t: OrgRepo, skillId: string, revisionId: string, input: { verdict: string; reason?: string; task_id?: string }, idempotencyKey: string): Promise<Judgment> {
      return write({
        path: skillPath(t, skillId) + '/revisions/' + encodeURIComponent(revisionId) + '/feedback',
        method: 'POST', body: { idempotency_key: idempotencyKey, ...input }, decode: d.judgment, resource: 'feedback/' + skillId + '/' + revisionId, idempotencyKey,
      });
    },

    // Map and modules -------------------------------------------------------
    getMapRepository(t: OrgRepo, path = '', cursor?: string): Promise<MapRepository> {
      // One branch at a time: the resource key carries the path so two open branches do not
      // supersede each other.
      return read({ path: target(t) + '/map/repository', query: { path, cursor }, decode: d.mapRepository, resource: 'map-repository/' + t.org + '/' + t.repo + '/' + path });
    },
    getMapScopes(t: OrgRepo, scope?: string): Promise<MapScopes> {
      return read({ path: target(t) + '/map/scopes', query: { scope }, decode: d.mapScopes, resource: 'map-scopes/' + t.org + '/' + t.repo });
    },
    getMapLayers(t: OrgRepo): Promise<MapLayers> {
      return read({ path: target(t) + '/map/layers', decode: d.mapLayers, resource: 'map-layers/' + t.org + '/' + t.repo });
    },
    getRelations(t: OrgRepo, query: RelationQuery): Promise<Relations> {
      return read({ path: target(t) + '/map/relations', query: { skill_id: query.skillId, type: query.type, cursor: query.cursor, limit: query.limit }, decode: d.relations, resource: 'relations/' + t.org + '/' + t.repo + '/' + (query.skillId ?? '') });
    },
    getModule(t: OrgRepo, scope: string): Promise<ModulePage> {
      return read({ path: target(t) + '/modules/' + encodeURIComponent(scope), decode: d.modulePage, resource: 'module/' + t.org + '/' + t.repo + '/' + scope });
    },

    // Proposals and review --------------------------------------------------
    listProposals(t: OrgRepo, query: ProposalQuery): Promise<ProposalList> {
      return read({ path: target(t) + '/proposals', query: { state: query.state, kind: query.kind, scope: query.scope, cursor: query.cursor }, decode: d.proposalList, resource: 'proposals/' + t.org + '/' + t.repo });
    },
    getProposal(t: OrgRepo, proposalId: string): Promise<ProposalDetail> {
      return read({ path: target(t) + '/proposals/' + encodeURIComponent(proposalId), decode: d.proposalDetail, resource: 'proposal/' + t.org + '/' + t.repo + '/' + proposalId });
    },
    decideProposal(t: OrgRepo, proposalId: string, input: { decision: 'approve' | 'edit' | 'reject'; reason: string; candidate_body?: string; expected_revision: string | null }, idempotencyKey: string): Promise<DecisionResult> {
      return write({
        path: target(t) + '/proposals/' + encodeURIComponent(proposalId) + '/decision',
        method: 'POST', body: { idempotency_key: idempotencyKey, ...input }, decode: d.decisionResult,
        resource: 'proposal/' + t.org + '/' + t.repo + '/' + proposalId, idempotencyKey,
      });
    },
    exportProposal(t: OrgRepo, proposalId: string, idempotencyKey: string): Promise<ExportPayload> {
      return write({ path: target(t) + '/proposals/' + encodeURIComponent(proposalId) + '/export', method: 'POST', body: { idempotency_key: idempotencyKey }, decode: d.exportPayload, resource: 'export/' + t.org + '/' + t.repo + '/' + proposalId, idempotencyKey });
    },
    getProposalPublication(t: OrgRepo, proposalId: string): Promise<Publication> {
      return read({ path: target(t) + '/proposals/' + encodeURIComponent(proposalId) + '/publication', decode: d.publication, resource: 'publication/' + t.org + '/' + t.repo + '/' + proposalId });
    },

    // Publication -----------------------------------------------------------
    listSnapshots(t: OrgRepo, cursor?: string): Promise<Snapshot[]> {
      return read({ path: target(t) + '/snapshots', query: { cursor }, decode: d.snapshotList, resource: 'snapshots/' + t.org + '/' + t.repo });
    },
    activateSnapshot(t: OrgRepo, snapshotId: string, reason: string, idempotencyKey: string): Promise<Snapshot> {
      // §4.4 requires the reason: it is the audit row explaining why what every agent in the
      // organisation reads was changed. The answer is the `{snapshot: …}` envelope, not a bare row.
      return write({
        path: target(t) + '/snapshots/' + encodeURIComponent(snapshotId) + '/activate', method: 'POST',
        body: { idempotency_key: idempotencyKey, reason },
        decode: d.field('snapshot', d.snapshot), resource: 'snapshot/' + t.org + '/' + t.repo + '/' + snapshotId, idempotencyKey,
        confirm: async () => (await source.listSnapshots(t)).find(entry => entry.snapshot_id === snapshotId && entry.active) ?? null,
      });
    },
    publish(t: OrgRepo, importId: string, idempotencyKey: string): Promise<{ job_id: string }> {
      return write({ path: target(t) + '/publish', method: 'POST', body: { idempotency_key: idempotencyKey, import_id: importId }, decode: d.jobRef, resource: 'publish/' + t.org + '/' + t.repo, idempotencyKey });
    },

    // Usage and quality -----------------------------------------------------
    getUsage(t: OrgRepo, query: UsageQuery): Promise<Usage> {
      // Contract §4.6 accepts exactly these five parameters; the report is not a paged list.
      const filters = { window: query.window, scope: query.scope, skill_id: query.skillId, revision: query.revision, harness: query.harness };
      return read({ path: target(t) + '/usage', query: filters, decode: d.usage, resource: 'usage/' + t.org + '/' + t.repo });
    },
    exportUsage(t: OrgRepo, query: UsageQuery): Promise<string> {
      return read({ path: target(t) + '/usage/export', query: { format: query.format ?? 'csv', window: query.window }, responseType: 'text', decode: d.str, resource: 'usage-export/' + t.org + '/' + t.repo + '/' + (query.format ?? 'csv') });
    },
    async decideQueueItem(t: OrgRepo, itemId: string, input: { action: 'reviewed' | 'fixed_in_git' | 'no_change'; reason: string }, idempotencyKey: string): Promise<void> {
      await write({ path: target(t) + '/usage/queue/' + encodeURIComponent(itemId) + '/decision', method: 'POST', body: { idempotency_key: idempotencyKey, ...input }, decode: d.nothing, resource: 'queue/' + t.org + '/' + t.repo + '/' + itemId, idempotencyKey });
    },
  };

  return source;
}

/** API composition: the data source plus the access confirmation loop wired to it. */
export function createApiRuntime(options: ApiDataSourceOptions = {}): { source: ApiDataSource; access: AccessController } {
  let controller: AccessController | null = null;
  // A 403 on a resource is not a session problem: the identity stays, only that organisation's or
  // repository's data is dropped. Reporting it as "no session" used to send the operator to sign
  // in, which returns to the same forbidden address and denies again (review, critical 1).
  const source = createApiDataSource({ ...options, onDenied: error => { options.onDenied?.(error); controller?.reportDenied(error.status === 403 ? 'forbidden' : 'unauthenticated'); } });
  controller = new AccessController({
    fetchMe: timeoutMs => source.getMe(timeoutMs),
    onDenied: () => source.revoke('access_denied'),
  });
  return { source, access: controller };
}
