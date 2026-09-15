/** The single data boundary the seven U4 routes read and write through.
 *
 * The one production implementation is `ApiDataSource` (the hosted management API through
 * `src/api/client.ts`); tests substitute `fakeSource` from `src/test/fakes.ts`. Routes never
 * call `fetch` and never hold sample data of their own.
 */
import type {
  AuditPage, AuthProviders, DecisionResult, DeviceApproval, DeviceStart, DuplicatePage, ExportPayload, Facets, FacetLookup,
  ImportCreated, ImportPlan, ImportStatus, Installation, Invitation, InvitationAccepted, InvitationLifecycle, Judgment, MapLayers, MapRepository, MapScopes,
  Me, Member, ModulePage, Org, ProposalDetail, ProposalGenerationResult, ProposalKind, ProposalList,
  ProposalLimits, Profile, Publication, Relations, Repo, Revision, Role, SkillDetail, SkillPage, Snapshot, Usage,
  Team, GitHubInstallation, GitHubInstallStart, RepoAccess, RepoAccessLevel, Reviewer,
  OrgCredential, OrgCredentialProvider, LiveRun, LiveRunDetail, LiveRunEventPage, LiveRunPage,
} from '../api/decoders';
import type { Session } from '../domain';

/** Local, unsent text, kept in RAM only and dropped with the access generation. */
export interface DraftStore {
  get(): Session;
  subscribe(listener: () => void): () => void;
  save(patch: Partial<Session>): void;
  clear(): void;
}

export interface SkillQuery {
  q?: string; scope?: string; owner?: string; layer?: string; status?: string;
  cursor?: string; limit?: number; snapshotId?: string;
}
export interface FacetQuery { field: 'scope' | 'owner' | 'layer' | 'status' | 'repo'; q?: string; cursor?: string }
export interface DuplicateQuery { repo?: string | null; cursor?: string; limit?: number }
export interface RelationQuery { skillId?: string; type?: string; cursor?: string; limit?: number }
export interface ProposalQuery { state?: string; kind?: string; scope?: string; cursor?: string }
/** Contract §4.6: `window, scope, skill_id, revision, harness` for the report, `format, window` for the export. */
export interface UsageQuery {
  window?: string; scope?: string; skillId?: string; revision?: string; harness?: string;
  format?: 'csv' | 'json';
}
export interface OrgRepo { org: string; repo: string }
/**
 * Where a read looks (contract §4.10, 1.11.0): one repository, or — with `repo: null` — every
 * repository of the organisation the signed-in principal may read. The API decides the set; the
 * console never fans out per repository. Mutations always take an `OrgRepo`: they act on one
 * repository, named by the row they act on.
 */
export interface ReadScope { org: string; repo: string | null }

export interface LoginRedirect {
  loginUrl: string;
  provider: string;
}

export interface DataSource {
  readonly drafts: DraftStore;

  /** The user/org/repo/policy context whose answers this source may still accept. */
  setContext?(next: { user?: string | null; org?: string | null; repo?: string | null; policy?: string | null }): void;
  /** Clear drafts, cancel in-flight work, bump the access generation. */
  revoke?(reason: string): void;

  // Auth and identity -------------------------------------------------------
  getAuthProviders(): Promise<AuthProviders>;
  startLogin(provider: string, returnTo: string): Promise<LoginRedirect>;
  /** `POST /auth/verify-email` (contract §2, §4.1): the code the callback's
   * email_verification_required redirect sent the browser to enter. Public and CSRF-exempt — the
   * gf_auth_state cookie the callback set is this route's own defense — so this is the one port
   * mutation that does not require a session's CSRF token. A wrong code stays retryable and
   * throws `ApiError` with `email_code_invalid`; success returns the address to navigate to. */
  verifyEmailCode(code: string, idempotencyKey: string): Promise<{ returnTo: string }>;
  getMe(timeoutMs?: number): Promise<Me>;
  logout(idempotencyKey: string): Promise<void>;
  startDeviceAuthorization(idempotencyKey: string): Promise<DeviceStart>;
  decideDevice(userCode: string, approve: boolean, idempotencyKey: string): Promise<DeviceApproval>;
  /** `POST /me/identities/link/start` (contract §4.1). Never auto-linked: the operator picks the provider. */
  startIdentityLink(provider: string, idempotencyKey: string): Promise<LoginRedirect>;
  updateProfile(name: string, idempotencyKey: string): Promise<Profile>;

  // Organizations -----------------------------------------------------------
  listOrgs(): Promise<Org[]>;
  getOrg(org: string): Promise<Org>;
  createOrg(input: { name: string; slug: string }, idempotencyKey: string): Promise<Org>;
  listMembers(org: string): Promise<Member[]>;
  listTeams(org: string): Promise<Team[]>;
  createTeam(org: string, name: string, idempotencyKey: string): Promise<Team>;
  addTeamMember(org: string, teamId: string, userId: string, idempotencyKey: string): Promise<void>;
  removeTeamMember(org: string, teamId: string, userId: string, idempotencyKey: string): Promise<void>;
  inviteMember(org: string, input: { email: string; role: Role }, idempotencyKey: string): Promise<Invitation>;
  listInvitations(org: string): Promise<InvitationLifecycle[]>;
  revokeInvitation(org: string, invitationId: string, idempotencyKey: string): Promise<void>;
  acceptInvitation(token: string, idempotencyKey: string): Promise<InvitationAccepted>;
  changeMemberRole(org: string, userId: string, role: Role, idempotencyKey: string): Promise<Member>;
  removeMember(org: string, userId: string, idempotencyKey: string): Promise<void>;
  listInstallations(org: string): Promise<Installation[]>;
  createInstallation(org: string, input: { name: string; repo_id?: string | null; scopes: string[]; harness?: string | null }, idempotencyKey: string): Promise<Installation>;
  revokeInstallation(org: string, installationId: string, idempotencyKey: string): Promise<void>;
  listGitHubInstallations(org: string): Promise<GitHubInstallation[]>;
  /** `POST {org_base}/github/installations/start`, owner + CSRF (contract §4.7, ADR-0034). The
   * caller sends the browser to the returned `install_url`; this call never links anything by
   * itself. `returnTo` (1.13.0, Task 1) is an optional console path — the wizard and the import
   * screen pass their own address so the callback sends the owner back there instead of always
   * landing on the Integrations tab; the server ignores anything outside its allow-list. */
  startGitHubInstall(org: string, idempotencyKey: string, returnTo?: string): Promise<GitHubInstallStart>;
  deleteGitHubInstallation(org: string, installationId: number, idempotencyKey: string): Promise<void>;
  /** `GET {org_base}/audit`, owner only (contract §4.1). */
  getAudit(org: string, cursor?: string): Promise<AuditPage>;

  // Model keys (contract §4.8, §5.5a, ADR-0045) ------------------------------
  /** Member-readable; a provider absent from the result has no stored key. */
  listCredentials(org: string): Promise<OrgCredential[]>;
  /** Owner + CSRF. The server checks the key with the provider before saving it. Storing or
   * replacing the key itself always goes through this route; `model`/`preferred` may ride
   * along on the same call, but changing either one on its own goes through `patchCredential`
   * instead, which never asks for the key. */
  setCredential(org: string, provider: OrgCredentialProvider, input: { api_key: string; name?: string | null; model?: string | null; preferred?: boolean }, idempotencyKey: string): Promise<OrgCredential>;
  /** Owner + CSRF. Changes `model` and/or `preferred` without the key (contract §4.8): the key
   * cannot be shown back, so asking for it again to flip one field would confirm nothing.
   * Never accepts `api_key`; replacing the key itself is `setCredential` (`PUT`). The server
   * refuses `preferred: false` on the organization's only preferred credential (an organization
   * with any credential always has exactly one preferred) — the UI never sends that value. */
  patchCredential(org: string, provider: OrgCredentialProvider, input: { model?: string; preferred?: boolean }, idempotencyKey: string): Promise<OrgCredential>;
  deleteCredential(org: string, provider: OrgCredentialProvider, idempotencyKey: string): Promise<void>;

  // Live Agent (contract §4.9, §5.5a, ADR-0046) ------------------------------
  listLiveRuns(org: string, cursor?: string): Promise<LiveRunPage>;
  getLiveRun(org: string, runId: string): Promise<LiveRunDetail>;
  /** `after` is the positional `seq` cursor (contract §4.9), not an opaque page token. */
  getLiveRunEvents(org: string, runId: string, after?: number): Promise<LiveRunEventPage>;
  /** No request fields (ADR-0046 1.6.0): the run always covers every connected repository and
   * always does the same thing, so there is nothing left for the caller to supply. */
  startLiveRun(org: string, idempotencyKey: string): Promise<LiveRun>;
  cancelLiveRun(org: string, runId: string, idempotencyKey: string): Promise<LiveRun>;

  // Repositories and import -------------------------------------------------
  listRepos(org: string): Promise<Repo[]>;
  createRepo(org: string, input: { repo_id: string; name?: string | null; git_host_url?: string | null }, idempotencyKey: string): Promise<Repo>;
  /** `POST {repo_base}/github/import`, owner + CSRF (contract §4.2, Task 3, 1.13.0). Enqueues
   * `github.import_repo` (fetch + `import.parse` only, never `proposal.generate`) for one
   * repository already registered from a linked GitHub installation; never requires an
   * organization model key. `repo_not_github_linked` when the repository was registered by hand
   * or the CLI instead. */
  importGitHubRepo(target: OrgRepo, idempotencyKey: string): Promise<{ job_id: string }>;
  /** `POST {org_base}/github/import`, owner + CSRF (contract §4.2, Task 3, 1.13.0). "Import all"
   * as one call: enqueues `github.import_repo` for every repository of the organization
   * registered from a linked GitHub installation. */
  importAllGitHubRepos(org: string, idempotencyKey: string): Promise<{ items: { repo_id: string; job_id: string }[]; count: number }>;
  listRepoAccess(target: OrgRepo): Promise<RepoAccess[]>;
  setRepoAccess(target: OrgRepo, userId: string, access: RepoAccessLevel, idempotencyKey: string): Promise<RepoAccess>;
  removeRepoAccess(target: OrgRepo, userId: string, idempotencyKey: string): Promise<void>;
  listReviewers(target: OrgRepo): Promise<Reviewer[]>;
  assignReviewer(target: OrgRepo, userId: string, idempotencyKey: string): Promise<void>;
  removeReviewer(target: OrgRepo, userId: string, idempotencyKey: string): Promise<void>;
  listImports(target: ReadScope, cursor?: string): Promise<ImportStatus[]>;
  createImport(target: OrgRepo, manifest: unknown, idempotencyKey: string): Promise<ImportCreated>;
  uploadImportBlob(target: OrgRepo, importId: string, sha256: string, bytes: Uint8Array): Promise<void>;
  finalizeImport(target: OrgRepo, importId: string, idempotencyKey: string): Promise<ImportStatus>;
  getImport(target: ReadScope, importId: string): Promise<ImportStatus>;
  cancelImport(target: OrgRepo, importId: string, idempotencyKey: string): Promise<void>;
  /** `GET {repo_base}/imports/{id}/plan`: estimate before any generation starts (contract §4.2). */
  getImportPlan(target: OrgRepo, importId: string, kinds: ProposalKind[]): Promise<ImportPlan>;
  /** `POST {repo_base}/imports/{id}/proposals:generate`: one `proposal.generate` job per requested kind. */
  generateProposals(target: OrgRepo, importId: string, input: { kinds: ProposalKind[]; limits: Partial<ProposalLimits> }, idempotencyKey: string): Promise<ProposalGenerationResult>;

  // Knowledge ---------------------------------------------------------------
  listSkills(target: ReadScope, query: SkillQuery): Promise<SkillPage>;
  getFacets(target: ReadScope, query: FacetQuery): Promise<Facets>;
  /** `GET {org_base}/skills/duplicates` (contract 1.12.0): organisation scope only; `repo` keeps the groups that include it. */
  listDuplicates(org: string, query: DuplicateQuery): Promise<DuplicatePage>;
  lookupFacet(target: ReadScope, field: string, value: string): Promise<FacetLookup>;
  getSkill(target: ReadScope, skillId: string): Promise<SkillDetail>;
  getRevision(target: ReadScope, skillId: string, revisionId: string): Promise<Revision>;
  getRevisionRaw(target: ReadScope, skillId: string, revisionId: string): Promise<string>;
  sendFeedback(target: OrgRepo, skillId: string, revisionId: string, input: { verdict: string; reason?: string; task_id?: string }, idempotencyKey: string): Promise<Judgment>;

  // Map and modules ---------------------------------------------------------
  getMapRepository(target: ReadScope, path?: string, cursor?: string): Promise<MapRepository>;
  getMapScopes(target: ReadScope, scope?: string): Promise<MapScopes>;
  getMapLayers(target: ReadScope): Promise<MapLayers>;
  getRelations(target: ReadScope, query: RelationQuery): Promise<Relations>;
  getModule(target: ReadScope, scope: string): Promise<ModulePage>;

  // Proposals and review ----------------------------------------------------
  listProposals(target: ReadScope, query: ProposalQuery): Promise<ProposalList>;
  getProposal(target: ReadScope, proposalId: string): Promise<ProposalDetail>;
  /** `target.repo` is null for a `scope_map` proposal: that decision is taken at organisation
   *  scope by an organisation owner (contract §4.10 point 10, ADR-0051). */
  decideProposal(target: ReadScope, proposalId: string, input: { decision: 'approve' | 'edit' | 'reject'; reason: string; candidate_body?: string; expected_revision: string | null }, idempotencyKey: string): Promise<DecisionResult>;
  exportProposal(target: OrgRepo, proposalId: string, idempotencyKey: string): Promise<ExportPayload>;
  getProposalPublication(target: ReadScope, proposalId: string): Promise<Publication>;

  // Publication -------------------------------------------------------------
  listSnapshots(target: OrgRepo, cursor?: string): Promise<Snapshot[]>;
  /** `reason` is required by contract §4.4: a rollback without one is refused with 400. */
  activateSnapshot(target: OrgRepo, snapshotId: string, reason: string, idempotencyKey: string): Promise<Snapshot>;
  publish(target: OrgRepo, importId: string, idempotencyKey: string): Promise<{ job_id: string }>;

  // Usage and quality -------------------------------------------------------
  getUsage(target: ReadScope, query: UsageQuery): Promise<Usage>;
  exportUsage(target: ReadScope, query: UsageQuery): Promise<string>;
  decideQueueItem(target: OrgRepo, itemId: string, input: { action: 'reviewed' | 'fixed_in_git' | 'no_change'; reason: string }, idempotencyKey: string): Promise<void>;
}
