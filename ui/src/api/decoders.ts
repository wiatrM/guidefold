/** Runtime decoders for the management API (`schema_version: "mgmt-1"`).
 * Hand-written, no schema library. Unknown extra fields are ignored; a missing or
 * wrongly typed declared field throws DecodeError, which the API client turns into a
 * route-boundary ApiError instead of a render-time crash.
 */

export class DecodeError extends Error {
  readonly path: string;
  constructor(path: string, message: string) {
    super(path ? `${path}: ${message}` : message);
    this.name = 'DecodeError';
    this.path = path;
  }
}

export type Decoder<T> = (value: unknown, path?: string) => T;

const describe = (value: unknown): string => value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value;
const fail = (path: string, expected: string, value: unknown): never => {
  throw new DecodeError(path, `expected ${expected}, received ${describe(value)}`);
};

export const str: Decoder<string> = (value, path = '') => typeof value === 'string' ? value : fail(path, 'string', value);
export const num: Decoder<number> = (value, path = '') => typeof value === 'number' && Number.isFinite(value) ? value : fail(path, 'number', value);
export const bool: Decoder<boolean> = (value, path = '') => typeof value === 'boolean' ? value : fail(path, 'boolean', value);
export const anyValue: Decoder<unknown> = value => value;
export const nothing: Decoder<null> = () => null;
/** For responses with no body whose absence still has to be confirmable after a timeout. */
export const ok: Decoder<true> = () => true;

/** Absent and explicit null are both "not supplied"; the contract uses `x|null` widely. */
export const nullable = <T>(decoder: Decoder<T>): Decoder<T | null> => (value, path = '') =>
  value === null || value === undefined ? null : decoder(value, path);
export const fallback = <T>(decoder: Decoder<T>, value: T): Decoder<T> => (input, path = '') =>
  input === null || input === undefined ? value : decoder(input, path);
export const arrayOf = <T>(decoder: Decoder<T>): Decoder<T[]> => (value, path = '') =>
  Array.isArray(value) ? value.map((item, index) => decoder(item, `${path}[${index}]`)) : fail(path, 'array', value);
export const listOf = <T>(decoder: Decoder<T>): Decoder<T[]> => fallback(arrayOf(decoder), []);
export const oneOf = <T extends string>(values: readonly T[]): Decoder<T> => (value, path = '') =>
  typeof value === 'string' && (values as readonly string[]).includes(value) ? value as T : fail(path, `one of ${values.join('|')}`, value);
export const dictionary = <T>(decoder: Decoder<T>): Decoder<Record<string, T>> => (value, path = '') => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'object', value);
  const out: Record<string, T> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) out[key] = decoder(item, path ? `${path}.${key}` : key);
  return out;
};

type Shape<T> = { [K in keyof T]: Decoder<T[K]> };
export const object = <T>(shape: Shape<T>): Decoder<T> => (value, path = '') => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'object', value);
  const source = value as Record<string, unknown>;
  const out = {} as T;
  for (const key of Object.keys(shape) as (keyof T & string)[]) out[key] = shape[key](source[key], path ? `${path}.${key}` : key);
  return out;
};
/** Response envelopes differ per endpoint; read one named field out of the body. */
export const field = <T>(name: string, decoder: Decoder<T>): Decoder<T> => (value, path = '') => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'object', value);
  return decoder((value as Record<string, unknown>)[name], path ? `${path}.${name}` : name);
};

export const decode = <T>(value: unknown, decoder: Decoder<T>): T => decoder(value, '');

// ---------------------------------------------------------------------------
// Auth and identity
// ---------------------------------------------------------------------------

export type Role = 'owner' | 'member';
export const roles = ['owner', 'member'] as const;

export interface OrgMembership { org_id: string; slug: string; name: string; role: Role }
export const orgMembership = object<OrgMembership>({
  org_id: str, slug: str, name: str, role: fallback(oneOf(roles), 'member'),
});

export interface Me {
  user: { id: string; email: string; name: string | null };
  identities: { provider: string; created_at: string | null }[];
  orgs: OrgMembership[];
  csrf_token: string | null;
  access: { checked_at: string | null; valid_for_s: number };
  link_suggestions: { provider: string }[];
}
export const me = object<Me>({
  user: object({ id: str, email: str, name: nullable(str) }),
  identities: listOf(object({ provider: str, created_at: nullable(str) })),
  orgs: listOf(orgMembership),
  csrf_token: nullable(str),
  access: fallback(object({ checked_at: nullable(str), valid_for_s: fallback(num, 45) }), { checked_at: null, valid_for_s: 45 }),
  link_suggestions: listOf(object({ provider: str })),
});

export const authProviderIds = ['google', 'github'] as const;
export type AuthProviderId = typeof authProviderIds[number];
export interface AuthProviders {
  providers: { id: AuthProviderId; label: string; login_url: string }[];
  mode: 'dev' | 'workos';
}
export const authProviders = object<AuthProviders>({
  providers: listOf(object({ id: oneOf(authProviderIds), label: str, login_url: str })),
  mode: fallback(oneOf(['dev', 'workos'] as const), 'workos'),
});

/** `POST /me/identities/link/start` (contract §4.1). Redirects to link an identity — never auto-linked. */
export interface IdentityLinkStart { login_url: string }
export const identityLinkStart = object<IdentityLinkStart>({ login_url: str });

export interface DeviceApproval { user_code: string; state: 'approved' | 'denied' | 'pending' | 'expired'; expires_at: string | null }
export const deviceApproval = object<DeviceApproval>({
  user_code: fallback(str, ''),
  state: fallback(oneOf(['approved', 'denied', 'pending', 'expired'] as const), 'pending'),
  expires_at: nullable(str),
});

export interface DeviceStart { device_code: string; user_code: string; verification_uri: string; expires_in: number; interval: number }
export const deviceStart = object<DeviceStart>({
  device_code: str, user_code: str, verification_uri: str,
  expires_in: fallback(num, 600), interval: fallback(num, 5),
});

// ---------------------------------------------------------------------------
// Organizations and membership
// ---------------------------------------------------------------------------

export interface Org {
  org_id: string; slug: string; name: string;
  my_role: Role | null; created_at: string | null;
  counts: { members: number; repos: number } | null;
}
export const org = object<Org>({
  org_id: str, slug: str, name: str,
  my_role: nullable(oneOf(roles)),
  created_at: nullable(str),
  counts: nullable(object({ members: fallback(num, 0), repos: fallback(num, 0) })),
});
export const orgList: Decoder<Org[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(org)(value, path) : field('items', arrayOf(org))(value, path);

export interface Member { user_id: string; email: string; name: string | null; role: Role; joined_at: string | null }
export const member = object<Member>({
  user_id: str, email: str, name: nullable(str),
  role: fallback(oneOf(roles), 'member'), joined_at: nullable(str),
});
export const memberList: Decoder<Member[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(member)(value, path) : field('items', arrayOf(member))(value, path);

export interface Invitation { invitation_id: string; accept_url: string; expires_at: string | null; email: string | null; role: Role | null }
export const invitation = object<Invitation>({
  invitation_id: str, accept_url: str, expires_at: nullable(str),
  email: nullable(str), role: nullable(oneOf(roles)),
});

export interface Installation {
  installation_id: string; name: string; repo_id: string | null;
  scopes: string[]; harness: string | null;
  last_seen_at: string | null; adapter_version: string | null; capabilities: string[] | null;
  created_at: string | null; token: string | null;
}
export const installation = object<Installation>({
  installation_id: str, name: fallback(str, ''), repo_id: nullable(str),
  scopes: listOf(str), harness: nullable(str),
  last_seen_at: nullable(str), adapter_version: nullable(str),
  capabilities: nullable(arrayOf(str)),
  created_at: nullable(str),
  token: nullable(str),
});
export const installationList: Decoder<Installation[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(installation)(value, path) : field('items', arrayOf(installation))(value, path);

export interface AuditEntry { at: string; actor: string | null; action: string; entity: string | null; revision: string | null; request_id: string | null }
export const auditEntry = object<AuditEntry>({
  at: str, actor: nullable(str), action: str, entity: nullable(str),
  revision: nullable(str), request_id: nullable(str),
});
/** `GET {org_base}/audit`: the generic `{items, next_cursor}` list shape (contract §3), owner-only. */
export interface AuditPage { items: AuditEntry[]; next_cursor: string | null }
export const auditPage = object<AuditPage>({ items: listOf(auditEntry), next_cursor: nullable(str) });

// Shared by import (plan groups, proposals:generate) and by proposals review below.
export const proposalKinds = ['extraction', 'enrichment', 'consolidation'] as const;
export type ProposalKind = typeof proposalKinds[number];

// ---------------------------------------------------------------------------
// Repositories and import
// ---------------------------------------------------------------------------

export interface Repo { repo_id: string; name: string | null; git_host_url: string | null; created_at: string | null; created: boolean }
export const repo = object<Repo>({
  repo_id: str, name: nullable(str), git_host_url: nullable(str), created_at: nullable(str),
  // `POST {org_base}/repos` answers 201 with `created: true` and 200 with `false` (§4.2);
  // a row read from the list was not created by this call, so absent means false.
  created: fallback(bool, false),
});
export const repoList: Decoder<Repo[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(repo)(value, path) : field('items', arrayOf(repo))(value, path);

export interface ImportLimits { max_blob_bytes: number; max_total_bytes: number; max_files: number }
export const importLimits = object<ImportLimits>({
  max_blob_bytes: fallback(num, 0), max_total_bytes: fallback(num, 0), max_files: fallback(num, 0),
});

/** Contract §5.2 and §6: `created → uploading` on the first blob PUT, before `queued`. */
export const importStates = ['created', 'uploading', 'queued', 'parsing', 'ready', 'partial', 'failed', 'cancelled'] as const;
export type ImportState = typeof importStates[number];
export const importFileStates = ['pending', 'accepted', 'omitted', 'failed'] as const;
export type ImportFileState = typeof importFileStates[number];
export const importFileKinds = ['skill', 'document', 'config', 'resource'] as const;
export type ImportFileKind = typeof importFileKinds[number];

export interface ImportCreated {
  import_id: string; state: ImportState; missing_blobs: string[];
  limits: ImportLimits | null; reused_import_id: string | null;
}
export const importCreated = object<ImportCreated>({
  import_id: str, state: fallback(oneOf(importStates), 'created'),
  missing_blobs: listOf(str), limits: nullable(importLimits),
  reused_import_id: nullable(str),
});

export interface ImportFile { path: string; sha256: string | null; size: number | null; kind: ImportFileKind | null; status: ImportFileState; reason: string | null; skill_id: string | null }
export const importFile = object<ImportFile>({
  path: str, sha256: nullable(str), size: nullable(num), kind: nullable(oneOf(importFileKinds)),
  status: fallback(oneOf(importFileStates), 'pending'),
  reason: nullable(str), skill_id: nullable(str),
});

export interface JobCost { calls: number; tokens_in: number; tokens_out: number; usd_certain: number; usd_uncertain: number }
export const jobCost = object<JobCost>({
  calls: fallback(num, 0), tokens_in: fallback(num, 0), tokens_out: fallback(num, 0),
  usd_certain: fallback(num, 0), usd_uncertain: fallback(num, 0),
});

export const jobStates = ['queued', 'leased', 'done', 'failed', 'skipped', 'cancelled'] as const;
export type JobState = typeof jobStates[number];
export interface Job { job_id: string; kind: string; state: JobState; attempts: number; generation: number; error: string | null; cost: JobCost | null; started_at: string | null; finished_at: string | null }
export const job = object<Job>({
  job_id: str, kind: fallback(str, ''), state: fallback(oneOf(jobStates), 'queued'),
  attempts: fallback(num, 0), generation: fallback(num, 0),
  error: nullable(str), cost: nullable(jobCost),
  started_at: nullable(str), finished_at: nullable(str),
});

export const publicationStates = ['none', 'building', 'published', 'failed'] as const;
export type PublicationBuildState = typeof publicationStates[number];
export interface ImportPublication { snapshot_id: string | null; state: PublicationBuildState; error: string | null }
export const importPublication = object<ImportPublication>({
  snapshot_id: nullable(str), state: fallback(oneOf(publicationStates), 'none'), error: nullable(str),
});

export interface ImportCounts { files: number; accepted: number; omitted: number; failed: number; new_blobs: number; reused_blobs: number; skills: number; documents: number }
export const importCounts = object<ImportCounts>({
  files: fallback(num, 0), accepted: fallback(num, 0), omitted: fallback(num, 0), failed: fallback(num, 0),
  new_blobs: fallback(num, 0), reused_blobs: fallback(num, 0), skills: fallback(num, 0), documents: fallback(num, 0),
});

export interface ImportStatus {
  import_id: string; state: ImportState; manifest_digest: string | null; commit: string | null; complete: boolean;
  counts: ImportCounts | null; files: ImportFile[]; files_truncated: boolean; jobs: Job[]; publication: ImportPublication | null;
  created_at: string | null; updated_at: string | null;
}
export const importStatus = object<ImportStatus>({
  import_id: str,
  state: fallback(oneOf(importStates), 'queued'),
  manifest_digest: nullable(str), commit: nullable(str),
  complete: fallback(bool, false),
  counts: nullable(importCounts),
  files: listOf(importFile),
  // §5.2: `files` is cut at 20 000 entries and says so here. The list endpoint sends an empty
  // `files` with `files_truncated: true`, so the length of the array is never the file count.
  files_truncated: fallback(bool, false),
  jobs: listOf(job),
  publication: nullable(importPublication),
  created_at: nullable(str), updated_at: nullable(str),
});
export const importStatusList: Decoder<ImportStatus[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(importStatus)(value, path) : field('items', arrayOf(importStatus))(value, path);

/** `GET {repo_base}/imports/{id}/plan`: one group of inputs the next `proposal.generate` job would cover. */
export interface ImportPlanGroup {
  group_id: string; kind: ProposalKind; scope: string; owner: string | null;
  inputs: string[]; n_inputs: number; estimated_tokens: number | null; estimated_calls: number;
}
export const importPlanGroup = object<ImportPlanGroup>({
  group_id: str, kind: fallback(oneOf(proposalKinds), 'extraction'),
  scope: str, owner: nullable(str),
  inputs: listOf(str), n_inputs: fallback(num, 0),
  estimated_tokens: nullable(num), estimated_calls: fallback(num, 0),
});

/** The subset of job-limit fields that apply to `proposal.generate` (contract §8). */
export interface ProposalLimits {
  max_files: number; max_bytes: number;
  max_groups: number; max_proposals_per_group: number; max_neighbours: number;
  max_tokens: number | null; max_calls: number | null; max_usd: number | null;
}
export const proposalLimits = object<ProposalLimits>({
  max_files: fallback(num, 0), max_bytes: fallback(num, 0),
  max_groups: fallback(num, 5), max_proposals_per_group: fallback(num, 5), max_neighbours: fallback(num, 10),
  max_tokens: nullable(num), max_calls: nullable(num), max_usd: nullable(num),
});
const defaultProposalLimits: ProposalLimits = {
  max_files: 0, max_bytes: 0,
  max_groups: 5, max_proposals_per_group: 5, max_neighbours: 10, max_tokens: null, max_calls: null, max_usd: null,
};

export const generatorNames = ['none', 'deterministic', 'openai', 'anthropic'] as const;
export type GeneratorName = typeof generatorNames[number];
/** `name`/`configured` drive the UI; `generator`/`version`/`model` name the exact recipe (§5.2). */
export interface Generator { name: GeneratorName; configured: boolean; generator: string; version: string; model: string | null }
const generator = object<Generator>({
  name: fallback(oneOf(generatorNames), 'none'), configured: fallback(bool, false),
  generator: fallback(str, ''), version: fallback(str, ''), model: nullable(str),
});
const defaultGenerator: Generator = { name: 'none', configured: false, generator: '', version: '', model: null };

/** Same shape for `GET …/plan` and the `plan` field of `POST …/proposals:generate` (contract §4.2, §5.2). */
export interface ImportPlan {
  groups: ImportPlanGroup[]; limits: ProposalLimits; estimated_usd_max: number; estimated_calls: number;
  /** Per kind: how many scopes `max_groups` cut from this plan. Above zero the group list is incomplete. */
  groups_skipped: Record<string, number>;
  generator: Generator;
}
export const importPlan = object<ImportPlan>({
  groups: listOf(importPlanGroup),
  limits: fallback(proposalLimits, defaultProposalLimits),
  estimated_usd_max: fallback(num, 0),
  estimated_calls: fallback(num, 0),
  groups_skipped: fallback(dictionary(num), {}),
  generator: fallback(generator, defaultGenerator),
});

/** `POST {repo_base}/imports/{id}/proposals:generate`: one job per requested kind. */
export interface ProposalGenerationResult { job_ids: string[]; plan: ImportPlan }
export const proposalGenerationResult = object<ProposalGenerationResult>({
  job_ids: listOf(str), plan: importPlan,
});

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export const skillPublicationStates = ['draft', 'approved_for_export', 'awaiting_git', 'published', 'needs_review', 'archived'] as const;
export type SkillPublicationStatus = typeof skillPublicationStates[number];
export const knowledgeLayers = ['atomic', 'task', 'abstract', 'unclassified'] as const;
export type KnowledgeLayer = typeof knowledgeLayers[number];

export interface SkillSummary {
  skill_id: string; name: string; description: string;
  scope: string; owner: string | null;
  source_layer: string | null; knowledge_layer: KnowledgeLayer | null; source_status: string | null;
  publication_status: SkillPublicationStatus;
  path: string; content_sha256: string | null; revision_id: string | null;
  /** The card revision the publication minted for the current revision; null until it entered a snapshot. */
  card_revision: string | null;
  package_digest: string | null; commit: string | null; updated_at: string | null;
}
export const skillSummary = object<SkillSummary>({
  skill_id: str, name: str, description: fallback(str, ''),
  scope: fallback(str, ''), owner: nullable(str),
  source_layer: nullable(str), knowledge_layer: nullable(oneOf(knowledgeLayers)), source_status: nullable(str),
  publication_status: fallback(oneOf(skillPublicationStates), 'draft'),
  path: fallback(str, ''), content_sha256: nullable(str), revision_id: nullable(str),
  card_revision: nullable(str),
  package_digest: nullable(str), commit: nullable(str), updated_at: nullable(str),
});

export interface FilterEcho { value: string; available: boolean }
export const filterEcho = object<FilterEcho>({ value: fallback(str, ''), available: fallback(bool, true) });

export interface SkillPage {
  items: SkillSummary[]; next_cursor: string | null; snapshot_id: string | null;
  schema_version: string | null; filters: Record<string, FilterEcho>;
}
export const skillPage = object<SkillPage>({
  items: listOf(skillSummary), next_cursor: nullable(str), snapshot_id: nullable(str),
  schema_version: nullable(str), filters: fallback(dictionary(filterEcho), {}),
});

export interface Facets { field: string; values: { value: string; count: number }[]; next_cursor: string | null }
export const facets = object<Facets>({
  field: fallback(str, ''),
  values: listOf(object({ value: str, count: fallback(num, 0) })),
  next_cursor: nullable(str),
});

export interface FacetLookup { field: string; value: string; count: number; available: boolean }
export const facetLookup = object<FacetLookup>({
  field: fallback(str, ''), value: fallback(str, ''),
  count: fallback(num, 0), available: fallback(bool, false),
});

export const revisionSources = ['import', 'proposal'] as const;
export type RevisionSource = typeof revisionSources[number];
export interface RevisionRef { revision_id: string; content_sha256: string | null; card_revision: string | null; commit: string | null; import_id: string | null; created_at: string | null; source: RevisionSource | null }
export const revisionRef = object<RevisionRef>({
  revision_id: str, content_sha256: nullable(str), card_revision: nullable(str), commit: nullable(str),
  import_id: nullable(str), created_at: nullable(str), source: nullable(oneOf(revisionSources)),
});

export interface SkillDetail extends SkillSummary { revisions: RevisionRef[] }
export const skillDetail: Decoder<SkillDetail> = (value, path = '') => ({
  ...skillSummary(value, path),
  revisions: field('revisions', listOf(revisionRef))(value, path),
});

export const relationTypes = ['derived_from', 'requires', 'refines', 'similar', 'conflicts_with'] as const;
export type RelationType = typeof relationTypes[number];
export const provenanceOrigins = ['source', 'parsed', 'inferred', 'human'] as const;
export type ProvenanceOrigin = typeof provenanceOrigins[number];

export interface SkillReference { path: string; sha256: string | null; size: number | null; type: string | null; required: boolean; available: boolean }
export const skillReference = object<SkillReference>({
  path: str, sha256: nullable(str), size: nullable(num), type: nullable(str),
  required: fallback(bool, false), available: fallback(bool, false),
});

export const feedbackVerdicts = ['helped', 'hindered', 'mixed', 'not_applicable', 'unknown'] as const;
export type FeedbackVerdict = typeof feedbackVerdicts[number];
export interface FeedbackEntry { judgment_id: string; verdict: FeedbackVerdict; reason: string | null; source: string | null; task_id: string | null; occurred_at: string | null }
export const feedbackEntry = object<FeedbackEntry>({
  // An absent verdict is the contract's own "no rating" category, not a helped/hindered vote.
  judgment_id: str, verdict: fallback(oneOf(feedbackVerdicts), 'unknown'), reason: nullable(str),
  source: nullable(str), task_id: nullable(str), occurred_at: nullable(str),
});

/** No default: coercing an unrecognised edge would invent a `requires` the source never declared. */
export interface RelationEdge { from: string | null; to: string; type: RelationType; provenance: string | null; revision: string | null }
export const relationEdge = object<RelationEdge>({
  from: nullable(str), to: str, type: oneOf(relationTypes),
  provenance: nullable(str), revision: nullable(str),
});

export interface Revision {
  revision_id: string; content_sha256: string | null; card_revision: string | null; body: string | null;
  frontmatter: Record<string, unknown> | null;
  source: { path: string | null; commit: string | null; url: string | null } | null;
  references: SkillReference[]; requires: string[]; refines: string[];
  relations: RelationEdge[]; feedback: FeedbackEntry[];
  provenance: { origin: ProvenanceOrigin; import_id: string | null; proposal_id: string | null } | null;
  publication_status: SkillPublicationStatus;
}
export const revision = object<Revision>({
  revision_id: str, content_sha256: nullable(str), card_revision: nullable(str), body: nullable(str),
  frontmatter: nullable(dictionary(anyValue)),
  source: nullable(object({ path: nullable(str), commit: nullable(str), url: nullable(str) })),
  references: listOf(skillReference), requires: listOf(str), refines: listOf(str),
  relations: listOf(relationEdge), feedback: listOf(feedbackEntry),
  provenance: nullable(object({ origin: oneOf(provenanceOrigins), import_id: nullable(str), proposal_id: nullable(str) })),
  publication_status: fallback(oneOf(skillPublicationStates), 'draft'),
});

export interface Judgment { judgment_id: string }
export const judgment = object<Judgment>({ judgment_id: str });

// ---------------------------------------------------------------------------
// Map and modules
// ---------------------------------------------------------------------------

export interface MapChild { name: string; path: string; kind: 'dir' | 'skill' | 'document'; skill_id: string | null; count: number | null }
export const mapChild = object<MapChild>({
  name: str, path: str,
  kind: fallback(oneOf(['dir', 'skill', 'document'] as const), 'dir'),
  skill_id: nullable(str), count: nullable(num),
});
export interface MapRepository { path: string; children: MapChild[]; next_cursor: string | null }
export const mapRepository = object<MapRepository>({
  path: fallback(str, ''), children: listOf(mapChild), next_cursor: nullable(str),
});

export interface MapScopes {
  scope: { id: string; owner: string | null; paths: string[]; parent: string | null } | null;
  children: { id: string; owner: string | null; skills: number }[];
  skills: { skill_id: string; name: string }[];
  unmapped: { skill_id: string; name: string }[];
}
export const mapScopes = object<MapScopes>({
  scope: nullable(object({ id: str, owner: nullable(str), paths: listOf(str), parent: nullable(str) })),
  children: listOf(object({ id: str, owner: nullable(str), skills: fallback(num, 0) })),
  skills: listOf(object({ skill_id: str, name: str })),
  unmapped: listOf(object({ skill_id: str, name: str })),
});

export interface MapLayers { layers: { layer: KnowledgeLayer; count: number }[] }
export const mapLayers = object<MapLayers>({ layers: listOf(object({ layer: oneOf(knowledgeLayers), count: fallback(num, 0) })) });

export interface Relations { items: RelationEdge[]; next_cursor: string | null; truncated: boolean }
export const relations = object<Relations>({
  items: listOf(relationEdge), next_cursor: nullable(str), truncated: fallback(bool, false),
});

export interface ModulePage {
  scope: string; owner: string | null; skills: SkillSummary[]; reading_order: string[];
  shared: { skill_id: string; name: string; used_by: string[] }[];
  documents: { path: string; kind: string | null }[];
}
export const modulePage = object<ModulePage>({
  scope: str, owner: nullable(str), skills: listOf(skillSummary), reading_order: listOf(str),
  shared: listOf(object({ skill_id: str, name: str, used_by: listOf(str) })),
  documents: listOf(object({ path: str, kind: nullable(str) })),
});

// ---------------------------------------------------------------------------
// Proposals and review
// ---------------------------------------------------------------------------

export const proposalStates = ['draft', 'approved_for_export', 'awaiting_git', 'published', 'rejected', 'superseded'] as const;
export type ProposalState = typeof proposalStates[number];
export const decisionKinds = ['approve', 'edit', 'reject'] as const;
export type DecisionKind = typeof decisionKinds[number];

export interface ProposalSummary {
  proposal_id: string; kind: ProposalKind; state: ProposalState; scope: string | null; owner: string | null;
  target_skill_id: string | null; path: string | null; created_at: string | null;
}
export const proposalSummary = object<ProposalSummary>({
  proposal_id: str, kind: fallback(oneOf(proposalKinds), 'extraction'),
  state: fallback(oneOf(proposalStates), 'draft'),
  scope: nullable(str), owner: nullable(str), target_skill_id: nullable(str),
  path: nullable(str), created_at: nullable(str),
});
export interface ProposalList { items: ProposalSummary[]; next_cursor: string | null }
export const proposalList = object<ProposalList>({ items: listOf(proposalSummary), next_cursor: nullable(str) });

export interface ProposalDetail {
  proposal_id: string; kind: ProposalKind; state: ProposalState; scope: string | null; owner: string | null;
  target_skill_id: string | null; target_revision_id: string | null;
  sources: { path: string; sha256: string | null; commit: string | null; lines: number[] | null }[];
  recipe: { version: string; generator: string; model: string | null } | null;
  candidate: { path: string; body: string; sha256: string | null; frontmatter: Record<string, unknown> | null };
  source_body: string | null;
  provenance: { field: string; origin: ProvenanceOrigin; source_ref: Record<string, unknown> | null; needs_confirmation: boolean }[];
  relations: { type: RelationType; to: string }[];
  decision: { decision: DecisionKind; reason: string | null; at: string | null; actor: string | null } | null;
  expected_revision: string | null; created_at: string | null; cost: JobCost | null;
}
export const proposalDetail = object<ProposalDetail>({
  proposal_id: str, kind: fallback(oneOf(proposalKinds), 'extraction'),
  state: fallback(oneOf(proposalStates), 'draft'),
  scope: nullable(str), owner: nullable(str),
  target_skill_id: nullable(str), target_revision_id: nullable(str),
  sources: listOf(object({ path: str, sha256: nullable(str), commit: nullable(str), lines: nullable(arrayOf(num)) })),
  recipe: nullable(object({ version: fallback(str, ''), generator: fallback(str, ''), model: nullable(str) })),
  candidate: object({ path: fallback(str, ''), body: fallback(str, ''), sha256: nullable(str), frontmatter: nullable(dictionary(anyValue)) }),
  source_body: nullable(str),
  provenance: listOf(object({ field: str, origin: fallback(oneOf(provenanceOrigins), 'inferred'), source_ref: nullable(dictionary(anyValue)), needs_confirmation: fallback(bool, false) })),
  relations: listOf(object({ type: oneOf(relationTypes), to: str })),
  decision: nullable(object({ decision: oneOf(decisionKinds), reason: nullable(str), at: nullable(str), actor: nullable(str) })),
  expected_revision: nullable(str), created_at: nullable(str), cost: nullable(jobCost),
});

export interface DecisionResult { proposal_id: string; state: ProposalState; revision_id: string | null; expected_revision: string | null }
export const decisionResult = object<DecisionResult>({
  proposal_id: fallback(str, ''), state: fallback(oneOf(proposalStates), 'draft'),
  revision_id: nullable(str), expected_revision: nullable(str),
});

export const exportStates = ['awaiting_git'] as const;
export type ExportState = typeof exportStates[number];
export interface ExportPayload {
  export_id: string; proposal_id: string; state: ExportState; base_commit: string | null;
  files: { path: string; sha256: string | null; content: string }[];
  patch: string | null;
}
export const exportPayload = object<ExportPayload>({
  // An export names the proposal it came from and stays `awaiting_git`: it is not a publication.
  export_id: str, proposal_id: fallback(str, ''), state: fallback(oneOf(exportStates), 'awaiting_git'),
  base_commit: nullable(str),
  files: listOf(object({ path: str, sha256: nullable(str), content: fallback(str, '') })),
  patch: nullable(str),
});

export interface Publication { state: 'awaiting_git' | 'published' | 'superseded'; published_revision_id: string | null; import_id: string | null; snapshot_id: string | null }
export const publication = object<Publication>({
  state: fallback(oneOf(['awaiting_git', 'published', 'superseded'] as const), 'awaiting_git'),
  published_revision_id: nullable(str), import_id: nullable(str), snapshot_id: nullable(str),
});

// ---------------------------------------------------------------------------
// Publication and snapshots
// ---------------------------------------------------------------------------

export const snapshotStates = ['building', 'validated', 'active', 'failed', 'superseded'] as const;
export type SnapshotState = typeof snapshotStates[number];
/**
 * One row of `gfm.publications` (§5.4). A publication exists before its snapshot does, so
 * `snapshot_id` is null while it is building and after it failed; `publication_id` is the row
 * identity. `validation.findings` carries why a failed build did not publish.
 */
export interface Snapshot {
  publication_id: string; snapshot_id: string | null; state: SnapshotState; active: boolean;
  import_id: string | null; job_id: string | null; commit: string | null; n_skills: number;
  builder_sha256: string | null; validation: { ok: boolean; findings: string[] } | null;
  error: string | null; activated_at: string | null; created_at: string | null;
}
export const snapshot = object<Snapshot>({
  publication_id: str, snapshot_id: nullable(str),
  state: fallback(oneOf(snapshotStates), 'building'), active: fallback(bool, false),
  import_id: nullable(str), job_id: nullable(str), commit: nullable(str), n_skills: fallback(num, 0),
  builder_sha256: nullable(str),
  validation: nullable(object({ ok: fallback(bool, false), findings: listOf(str) })),
  error: nullable(str), activated_at: nullable(str), created_at: nullable(str),
});
export const snapshotList: Decoder<Snapshot[]> = (value, path = '') =>
  Array.isArray(value) ? arrayOf(snapshot)(value, path) : field('items', arrayOf(snapshot))(value, path);

export interface JobRef { job_id: string }
export const jobRef = object<JobRef>({ job_id: str });

// ---------------------------------------------------------------------------
// Usage and quality
// ---------------------------------------------------------------------------

export interface FeedbackTotals { helped: number; hindered: number; mixed: number; not_applicable: number; unknown: number; n: number }
export const feedbackTotals = object<FeedbackTotals>({
  helped: fallback(num, 0), hindered: fallback(num, 0), mixed: fallback(num, 0),
  not_applicable: fallback(num, 0), unknown: fallback(num, 0), n: fallback(num, 0),
});

export interface HelpedRatio { numerator: number; denominator: number; small_sample: boolean }
export const helpedRatio = object<HelpedRatio>({
  numerator: fallback(num, 0), denominator: fallback(num, 0), small_sample: fallback(bool, false),
});

export interface UsageSkill {
  skill_id: string; revision: string | null;
  /** The same revision's two other names: the delivery path uses `card_revision`, the UI the catalogue one. */
  card_revision: string | null; content_sha256: string | null;
  /** From the current catalogue revision; `harness` only when one adapter produced the row (§5.5). */
  scope: string | null; owner: string | null; harness: string | null;
  exposures: number; loads_verified: number; context_loaded: number; context_unknown: number;
  use_reported: number; use_observed: number; use_episodes: number;
  /** Contract 1.1.4: exposures whose search led to a verified load of the same skill, and loads with
   *  no search_id (unknown, never "without a card"). While `loads_unlinked > 0`, exposures minus
   *  expanded is an upper bound on cards that sufficed. */
  exposures_expanded: number; loads_unlinked: number;
  feedback: FeedbackTotals | null; helped_ratio: HelpedRatio | null; zero_loads: boolean;
}
export const usageSkill = object<UsageSkill>({
  skill_id: str, revision: nullable(str),
  card_revision: nullable(str), content_sha256: nullable(str),
  scope: nullable(str), owner: nullable(str), harness: nullable(str),
  exposures: fallback(num, 0), loads_verified: fallback(num, 0), context_loaded: fallback(num, 0),
  // `context_unknown` is loads_verified − context_loaded: unknown, not a failure.
  context_unknown: fallback(num, 0),
  use_reported: fallback(num, 0), use_observed: fallback(num, 0), use_episodes: fallback(num, 0),
  exposures_expanded: fallback(num, 0), loads_unlinked: fallback(num, 0),
  feedback: nullable(feedbackTotals),
  helped_ratio: nullable(helpedRatio),
  zero_loads: fallback(bool, false),
});

export const queueReasons = ['negative_feedback', 'source_changed', 'source_removed', 'zero_loads', 'missing_dependency'] as const;
export type QueueReason = typeof queueReasons[number];
export const queueActions = ['reviewed', 'fixed_in_git', 'no_change'] as const;
export type QueueAction = typeof queueActions[number];
export interface QueueItem {
  item_id: string; skill_id: string; revision: string | null; reason: QueueReason; since: string | null;
  evidence: Record<string, unknown> | null; decision: { action: QueueAction; reason: string | null; at: string | null } | null;
}
export const queueItem = object<QueueItem>({
  // The reason drives the owner decision, so an absent or unknown one is a contract break, not a default.
  item_id: str, skill_id: str, revision: nullable(str),
  reason: oneOf(queueReasons), since: nullable(str),
  evidence: nullable(dictionary(anyValue)),
  decision: nullable(object({ action: oneOf(queueActions), reason: nullable(str), at: nullable(str) })),
});

export interface AdapterHealth { harness: string; adapter_version: string | null; capabilities: string[] | null; last_seen_at: string | null; lag_s: number | null; dropped: number | null }
export const adapterHealth = object<AdapterHealth>({
  harness: str, adapter_version: nullable(str), capabilities: nullable(arrayOf(str)),
  last_seen_at: nullable(str), lag_s: nullable(num), dropped: nullable(num),
});

export interface Usage {
  window: { from: string | null; to: string | null; watermark: string | null };
  coverage: { events_received: number; dropped_reported: number; oldest_lag_s: number | null; task_ids_present: boolean } | null;
  totals: {
    exposures: number; loads_verified: number; context_loaded: number; context_unknown: number;
    use_reported: number; use_observed: number; use_episodes: number;
    exposures_expanded: number; loads_unlinked: number; feedback: FeedbackTotals | null;
  };
  skills: UsageSkill[]; queue: QueueItem[]; health: { adapters: AdapterHealth[] } | null;
}
export const usage = object<Usage>({
  window: fallback(object({ from: nullable(str), to: nullable(str), watermark: nullable(str) }), { from: null, to: null, watermark: null }),
  coverage: nullable(object({
    events_received: fallback(num, 0), dropped_reported: fallback(num, 0),
    oldest_lag_s: nullable(num), task_ids_present: fallback(bool, false),
  })),
  totals: fallback(object({
    exposures: fallback(num, 0), loads_verified: fallback(num, 0), context_loaded: fallback(num, 0),
    context_unknown: fallback(num, 0), use_reported: fallback(num, 0), use_observed: fallback(num, 0),
    use_episodes: fallback(num, 0), exposures_expanded: fallback(num, 0), loads_unlinked: fallback(num, 0),
    feedback: nullable(feedbackTotals),
  }), {
    exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0,
    use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null,
  }),
  skills: listOf(usageSkill), queue: listOf(queueItem),
  health: nullable(object({ adapters: listOf(adapterHealth) })),
});
