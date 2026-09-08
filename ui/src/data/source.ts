/** The single data boundary the seven U4 routes read and write through.
 *
 * The one production implementation is `ApiDataSource` (the hosted management API through
 * `src/api/client.ts`); tests substitute `fakeSource` from `src/test/fakes.ts`. Routes never
 * call `fetch` and never hold sample data of their own.
 */
import type {
  AuditPage, AuthProviders, DecisionResult, DeviceApproval, DeviceStart, ExportPayload, Facets, FacetLookup,
  ImportCreated, ImportPlan, ImportStatus, Installation, Invitation, Judgment, MapLayers, MapRepository, MapScopes,
  Me, Member, ModulePage, Org, ProposalDetail, ProposalGenerationResult, ProposalKind, ProposalList,
  ProposalLimits, Publication, Relations, Repo, Revision, Role, SkillDetail, SkillPage, Snapshot, Usage,
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
export interface FacetQuery { field: 'scope' | 'owner' | 'layer' | 'status'; q?: string; cursor?: string }
export interface RelationQuery { skillId?: string; type?: string; cursor?: string; limit?: number }
export interface ProposalQuery { state?: string; kind?: string; scope?: string; cursor?: string }
/** Contract §4.6: `window, scope, skill_id, revision, harness` for the report, `format, window` for the export. */
export interface UsageQuery {
  window?: string; scope?: string; skillId?: string; revision?: string; harness?: string;
  format?: 'csv' | 'json';
}
export interface OrgRepo { org: string; repo: string }

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
  getMe(timeoutMs?: number): Promise<Me>;
  logout(idempotencyKey: string): Promise<void>;
  startDeviceAuthorization(idempotencyKey: string): Promise<DeviceStart>;
  decideDevice(userCode: string, approve: boolean, idempotencyKey: string): Promise<DeviceApproval>;
  /** `POST /me/identities/link/start` (contract §4.1). Never auto-linked: the operator picks the provider. */
  startIdentityLink(provider: string, idempotencyKey: string): Promise<LoginRedirect>;

  // Organizations -----------------------------------------------------------
  listOrgs(): Promise<Org[]>;
  getOrg(org: string): Promise<Org>;
  createOrg(input: { name: string; slug: string }, idempotencyKey: string): Promise<Org>;
  listMembers(org: string): Promise<Member[]>;
  inviteMember(org: string, input: { email: string; role: Role }, idempotencyKey: string): Promise<Invitation>;
  changeMemberRole(org: string, userId: string, role: Role, idempotencyKey: string): Promise<Member>;
  removeMember(org: string, userId: string, idempotencyKey: string): Promise<void>;
  listInstallations(org: string): Promise<Installation[]>;
  createInstallation(org: string, input: { name: string; repo_id?: string | null; scopes: string[]; harness?: string | null }, idempotencyKey: string): Promise<Installation>;
  revokeInstallation(org: string, installationId: string, idempotencyKey: string): Promise<void>;
  /** `GET {org_base}/audit`, owner only (contract §4.1). */
  getAudit(org: string, cursor?: string): Promise<AuditPage>;

  // Repositories and import -------------------------------------------------
  listRepos(org: string): Promise<Repo[]>;
  createRepo(org: string, input: { repo_id: string; name?: string | null; git_host_url?: string | null }, idempotencyKey: string): Promise<Repo>;
  listImports(target: OrgRepo, cursor?: string): Promise<ImportStatus[]>;
  createImport(target: OrgRepo, manifest: unknown, idempotencyKey: string): Promise<ImportCreated>;
  getImport(target: OrgRepo, importId: string): Promise<ImportStatus>;
  cancelImport(target: OrgRepo, importId: string, idempotencyKey: string): Promise<void>;
  /** `GET {repo_base}/imports/{id}/plan`: estimate before any generation starts (contract §4.2). */
  getImportPlan(target: OrgRepo, importId: string, kinds: ProposalKind[]): Promise<ImportPlan>;
  /** `POST {repo_base}/imports/{id}/proposals:generate`: one `proposal.generate` job per requested kind. */
  generateProposals(target: OrgRepo, importId: string, input: { kinds: ProposalKind[]; limits: Partial<ProposalLimits> }, idempotencyKey: string): Promise<ProposalGenerationResult>;

  // Knowledge ---------------------------------------------------------------
  listSkills(target: OrgRepo, query: SkillQuery): Promise<SkillPage>;
  getFacets(target: OrgRepo, query: FacetQuery): Promise<Facets>;
  lookupFacet(target: OrgRepo, field: string, value: string): Promise<FacetLookup>;
  getSkill(target: OrgRepo, skillId: string): Promise<SkillDetail>;
  getRevision(target: OrgRepo, skillId: string, revisionId: string): Promise<Revision>;
  getRevisionRaw(target: OrgRepo, skillId: string, revisionId: string): Promise<string>;
  sendFeedback(target: OrgRepo, skillId: string, revisionId: string, input: { verdict: string; reason?: string; task_id?: string }, idempotencyKey: string): Promise<Judgment>;

  // Map and modules ---------------------------------------------------------
  getMapRepository(target: OrgRepo, path?: string, cursor?: string): Promise<MapRepository>;
  getMapScopes(target: OrgRepo, scope?: string): Promise<MapScopes>;
  getMapLayers(target: OrgRepo): Promise<MapLayers>;
  getRelations(target: OrgRepo, query: RelationQuery): Promise<Relations>;
  getModule(target: OrgRepo, scope: string): Promise<ModulePage>;

  // Proposals and review ----------------------------------------------------
  listProposals(target: OrgRepo, query: ProposalQuery): Promise<ProposalList>;
  getProposal(target: OrgRepo, proposalId: string): Promise<ProposalDetail>;
  decideProposal(target: OrgRepo, proposalId: string, input: { decision: 'approve' | 'edit' | 'reject'; reason: string; candidate_body?: string; expected_revision: string | null }, idempotencyKey: string): Promise<DecisionResult>;
  exportProposal(target: OrgRepo, proposalId: string, idempotencyKey: string): Promise<ExportPayload>;
  getProposalPublication(target: OrgRepo, proposalId: string): Promise<Publication>;

  // Publication -------------------------------------------------------------
  listSnapshots(target: OrgRepo, cursor?: string): Promise<Snapshot[]>;
  /** `reason` is required by contract §4.4: a rollback without one is refused with 400. */
  activateSnapshot(target: OrgRepo, snapshotId: string, reason: string, idempotencyKey: string): Promise<Snapshot>;
  publish(target: OrgRepo, importId: string, idempotencyKey: string): Promise<{ job_id: string }>;

  // Usage and quality -------------------------------------------------------
  getUsage(target: OrgRepo, query: UsageQuery): Promise<Usage>;
  exportUsage(target: OrgRepo, query: UsageQuery): Promise<string>;
  decideQueueItem(target: OrgRepo, itemId: string, input: { action: 'reviewed' | 'fixed_in_git' | 'no_change'; reason: string }, idempotencyKey: string): Promise<void>;
}
