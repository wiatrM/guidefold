package review

// The LLM-proposed organisation scope map (ADR-0051, API-CONTRACT 1.14.0).
//
// One rule shapes every line here: a map is a proposal until an owner accepts
// it, and accepting it is the only thing that writes `gfm.scopes`. PRODUCT-PIVOT
// U1 line 69 puts it as "niepewna hierarchia/owner są widoczne i nie stają się
// samoczynnie polityką", and the code keeps that literal — the worker writes a
// draft and nothing else, the decision handler writes rows and nothing else.
//
// Two things about it are easy to get wrong.
//
// **Path containment is per repository.** A scope identifier is unique per
// repository, not per organisation (ADR-0047 decision 4). A map that checked
// "every path under exactly one node" over a flat, global path set would pass
// happily for two repositories that both have `services/api` and then write
// rows for the wrong one.
//
// **The diff is read, not stored.** A proposal left in the queue for a week has
// to show what approving it would do today. Freezing the diff at write time
// would show what it would have done when the job ran, which is a different and
// possibly false claim.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sort"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/domain"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// KindScopeMap is the proposal kind, KindScopeMapPropose the job kind that
// produces it. They are separate names because they are separate things: one is
// a row in `gfm.proposals`, the other a row in `gfm.jobs`.
const (
	KindScopeMap        = generator.KindScopeMap
	KindScopeMapPropose = "scope_map.propose"
)

// StateApplied is the terminal state of an approved scope map. It is not
// `published`: `published` means a candidate's bytes reached git and a snapshot
// activated, and a map has neither (API-CONTRACT §6).
const StateApplied = "applied"

// ScopeMapPayloadVersion labels the job's payload. A worker that does not know
// the version refuses the job rather than guessing what the fields mean.
const ScopeMapPayloadVersion = "scope_map.propose-1"

// ScopeMapCandidatePath is the synthetic path the proposal's candidate carries.
// It is not a file anyone exports: `export` on a scope map is
// `proposal_state_invalid`. It exists so the candidate has one identity, and so
// the existing detail route can hand back the map's own bytes without a second
// storage path that could disagree with the first.
const ScopeMapCandidatePath = ".guidefold/scope-map.json"

// scopeMapPayload is the job's own claim about what it is for.
type scopeMapPayload struct {
	SchemaVersion string `json:"schema_version"`
	OrgID         string `json:"org_id"`
	RepoID        string `json:"repo_id"`
	ImportID      string `json:"import_id"`
}

// ScopeMapApplier is the outbound port the decision handler uses to write the
// approved map.
//
// `gfm.scopes` belongs to the import module (services/search/internal/README),
// and review does not write another module's table. The interface is declared
// here because this is where the need is; `internal/importer` implements it,
// and the composition happens in `package main` where both already meet.
type ScopeMapApplier interface {
	ApplyScopeMap(ctx context.Context, tx pgx.Tx, orgID, proposalID, reviewerID string,
		m domain.ScopeMap) (int, error)
}

// SetScopeMapApplier wires the port. A service with no applier answers a
// `scope_map` approval with a named 503 rather than a panic or, worse, a
// success that wrote nothing.
func (s *Service) SetScopeMapApplier(a ScopeMapApplier) { s.scopeMaps = a }

// ---------------------------------------------------------------- read side

// scopeMapOf decodes a proposal's stored map and returns the `ScopeMap` DTO of
// API-CONTRACT §5.4, with the diff and any findings computed now.
func (s *Service) scopeMapOf(ctx context.Context, orgID, blobSHA string) (map[string]any, error) {
	raw, e := s.blobs.Get(ctx, orgID, blobSHA)
	if e != nil {
		// The bytes are gone. The proposal still exists and still says what kind
		// it is; the map is a named absence rather than an invented empty one.
		return nil, nil
	}
	var m domain.ScopeMap
	if e := json.Unmarshal(raw, &m); e != nil {
		return nil, nil
	}
	existing, e := s.existingScopes(ctx, orgID, m.Repos)
	if e != nil {
		return nil, e
	}
	owners, e := s.codeownersTeams(ctx, orgID, m.Repos)
	if e != nil {
		return nil, e
	}
	findings := domain.ValidateScopeMap(m, m.Repos, owners)
	if findings == nil {
		findings = []string{}
	}
	nodes := make([]map[string]any, 0, len(m.Nodes))
	for _, n := range m.Nodes {
		paths := make([]map[string]any, 0, len(n.Paths))
		for _, p := range n.Paths {
			paths = append(paths, map[string]any{"repo_id": p.RepoID, "path": p.Path})
		}
		nodes = append(nodes, map[string]any{"scope": n.Scope, "parent": nullable(n.Parent),
			"owner": nullable(n.Owner), "paths": paths, "confidence": n.Confidence,
			"reason": n.Reason})
	}
	return map[string]any{"origin": m.Origin, "model": nullable(m.Model), "repos": m.Repos,
		"nodes": nodes, "diff": domain.DiffScopeMap(m, existing), "findings": findings}, nil
}

// existingScopes reads what the organisation's repositories say about their own
// scopes today.
//
// This is a read of a table `importer` writes. It is an explicit, single-purpose
// projection rather than a join into that module's queries — the same shape
// `GenerateWorker.scopeDirs` already uses for the same table and the same
// reason (module-boundaries-go, "odczyt między modułami idzie przez jawny
// interfejs lub projekcję").
func (s *Service) existingScopes(ctx context.Context, orgID string, repos []string) ([]domain.ExistingScope, error) {
	rows, e := s.pool.Query(ctx, `SELECT repo_id,scope,COALESCE(parent,''),COALESCE(owner,''),
 paths,source FROM gfm.scopes WHERE org_id=$1::uuid AND repo_id=ANY($2::text[])
 ORDER BY repo_id,scope`, orgID, repos)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []domain.ExistingScope{}
	for rows.Next() {
		var x domain.ExistingScope
		if e := rows.Scan(&x.RepoID, &x.Scope, &x.Parent, &x.Owner, &x.Paths, &x.Source); e != nil {
			return nil, e
		}
		out = append(out, x)
	}
	return out, rows.Err()
}

// codeownersPaths are the three places a repository is allowed to keep the file.
// The list is closed on purpose: a CODEOWNERS found somewhere else is a file
// GitHub itself would not honour, so honouring it here would assign owners
// nobody actually owns.
var codeownersPaths = []string{"CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"}

// codeownersTeams reads each repository's CODEOWNERS and returns the team names
// it mentions. A repository with no CODEOWNERS gets an empty set, which makes
// every owner on its nodes a finding rather than a silent pass.
func (s *Service) codeownersTeams(ctx context.Context, orgID string, repos []string) (map[string]map[string]bool, error) {
	out := map[string]map[string]bool{}
	for _, repo := range repos {
		text, e := s.codeownersOf(ctx, orgID, repo)
		if e != nil {
			return nil, e
		}
		out[repo] = generator.CodeownersTeams(text)
	}
	return out, nil
}

func (s *Service) codeownersOf(ctx context.Context, orgID, repoID string) (string, error) {
	return documentBody(ctx, s.pool, s.blobs, orgID, repoID, codeownersPaths...)
}

// documentBody returns the bytes of the first of `paths` the repository's most
// recent import carried, or "" when it carried none of them.
func documentBody(ctx context.Context, pool *pgxpool.Pool, blobs BlobStore,
	orgID, repoID string, paths ...string) (string, error) {
	var sha string
	e := pool.QueryRow(ctx, `SELECT sha256 FROM gfm.documents
 WHERE org_id=$1::uuid AND repo_id=$2 AND path=ANY($3::text[])
 ORDER BY array_position($3::text[], path), created_at DESC LIMIT 1`,
		orgID, repoID, paths).Scan(&sha)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", nil
	}
	if e != nil {
		return "", e
	}
	raw, e := blobs.Get(ctx, orgID, sha)
	if e != nil {
		// The upload was retained away. An absent document is honest; inventing
		// text for it is not.
		return "", nil
	}
	return string(raw), nil
}

// --------------------------------------------------------------- write side

// decideScopeMap is the `scope_map` half of handleDecision. It runs inside the
// caller's transaction, so either the rows, the decision, the state change and
// the audit entry all land, or none of them do.
func (s *Service) decideScopeMap(c *mgmt.Context, tx pgx.Tx, rc *repoContext, p *proposal,
	req decisionRequest) error {
	id := p.ProposalID
	if req.Decision == "edit" {
		// The candidate is a typed structure, not prose. "I will fix it by hand"
		// has no domain here in which it could be right: an owner who wants a
		// different map rejects this one and writes guidefold.yaml, which
		// outranks every proposal (ADR-0050 precedence).
		return mgmt.Unprocessable("invalid_candidate_change",
			"A scope map cannot be edited in place; reject it and declare the map in guidefold.yaml.")
	}
	if req.Decision == "reject" {
		if e := s.recordDecision(c, tx, rc, p, req, ""); e != nil {
			return e
		}
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposals SET state='rejected',updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, rc.Org.ID, id); e != nil {
			return mgmt.Internal(e)
		}
		if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposal.reject", "proposal:"+id, p.CacheKey); e != nil {
			return mgmt.Internal(e)
		}
		if e := tx.Commit(c.Ctx()); e != nil {
			return mgmt.Internal(e)
		}
		return c.JSON(http.StatusOK, map[string]any{
			"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
			"proposal_id": id, "state": StateRejected, "revision_id": nil,
			"expected_revision": nil})
	}

	if s.scopeMaps == nil {
		return mgmt.Fail(http.StatusServiceUnavailable, "database_unavailable",
			"This deployment cannot apply scope maps.")
	}
	raw, e := s.blobs.Get(c.Ctx(), rc.Org.ID, p.CandidateBlobSHA256)
	if e != nil {
		return mgmt.Conflict("proposal_state_invalid",
			"The map's bytes are no longer stored; run the import again to propose a new one.")
	}
	var m domain.ScopeMap
	if e := json.Unmarshal(raw, &m); e != nil {
		return mgmt.Conflict("proposal_state_invalid",
			"The stored map is not readable; run the import again to propose a new one.")
	}
	// Validation runs again here, not only in the worker: an import between the
	// proposal and this click may have added or removed paths, and a map that
	// was sound then can be unsound now.
	owners, e2 := s.codeownersTeams(c.Ctx(), rc.Org.ID, m.Repos)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if findings := domain.ValidateScopeMap(m, m.Repos, owners); len(findings) > 0 {
		return mgmt.Unprocessable("scope_map_invalid",
			"The proposed map no longer describes this organisation.").
			WithDetails(map[string]any{"findings": findings})
	}
	written, e2 := s.scopeMaps.ApplyScopeMap(c.Ctx(), tx, rc.Org.ID, id,
		c.Principal.UserID, m)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if e := s.recordDecision(c, tx, rc, p, req, ""); e != nil {
		return e
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposals SET state=$3,updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, rc.Org.ID, id, StateApplied); e != nil {
		return mgmt.Internal(e)
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposal.apply_scope_map", "proposal:"+id,
		p.CacheKey); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"proposal_id": id, "state": StateApplied, "revision_id": nil,
		"expected_revision": nil, "scopes_written": written})
}

// handleOrgDecision is the organisation-scope decision route (API-CONTRACT
// §4.4, §4.10 point 10).
//
// The address carries no repository, so the repository comes from the proposal
// row — and the caller is then checked against *that* repository with the same
// reviewer rule the `{repo_base}` twin applies. Two authorisations, in this
// order, on purpose: the first decides whether the caller may even learn the
// proposal exists (a proposal outside their readable scope is 404, never a hint
// that it is elsewhere), the second whether they may decide it.
func (s *Service) handleOrgDecision(c *mgmt.Context) error {
	sc, e := s.authorizeScope(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	id := c.Param("proposal_id")
	if !parseUUID(id) {
		return notFound("proposal_not_found", "No such proposal in this organization.")
	}
	p, err := s.loadProposalIn(c.Ctx(), sc.Org.ID, sc.Scope.Repos, id)
	if isNoRows(err) {
		return notFound("proposal_not_found", "No such proposal in this organization.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	org, repo, e := c.AuthorizeReviewerRepoID("org", p.RepoID)
	if e != nil {
		return e
	}
	return s.decide(c, &repoContext{Org: org, Repo: repo, RepoID: repo.ID}, id)
}

// ------------------------------------------------------------------- worker

// ScopeMapWorker runs `scope_map.propose`.
type ScopeMapWorker struct {
	pool    *pgxpool.Pool
	blobs   BlobStore
	engine  generator.Generator
	recipe  generator.Recipe
	keyring *secrets.Keyring
}

// NewScopeMapWorker builds the worker from the deployment's configured
// generator, exactly as the generation worker does.
func NewScopeMapWorker(pool *pgxpool.Pool, blobs BlobStore, keyring *secrets.Keyring) (*ScopeMapWorker, error) {
	engine, recipe, e := generator.Select(nil)
	if e != nil {
		return nil, e
	}
	return &ScopeMapWorker{pool: pool, blobs: blobs, engine: engine, recipe: recipe,
		keyring: keyring}, nil
}

// Handlers registers this worker's one job kind.
func (w *ScopeMapWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindScopeMapPropose: w.Run}
}

// Run proposes one organisation scope map.
func (w *ScopeMapWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload scopeMapPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode scope_map.propose payload: %w", e))
	}
	if payload.SchemaVersion != ScopeMapPayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported payload schema_version %q", payload.SchemaVersion))
	}
	if payload.OrgID != t.Job.OrgID {
		return worker.Permanent(errors.New("scope_map.propose payload does not match its job row"))
	}
	limits := generator.DefaultScopeMapLimits()
	req, e := w.request(ctx, payload.OrgID, limits)
	if e != nil {
		return e
	}
	if len(req.Repos) == 0 {
		return worker.Skipped("no_repositories")
	}
	engine, recipe, key, e := w.resolve(ctx, payload.OrgID)
	if e != nil {
		return e
	}
	mapper, e := generator.ScopeMapperFor(engine)
	if e != nil {
		// No generator can answer this question. The import stays exactly as it
		// is — the skills a repository already has do not depend on a model
		// (U2.7, #146/#167: a repository imports without a model key).
		return worker.Skipped("llm_not_configured")
	}
	req.APIKey = key
	m, cost, e := mapper.ProposeScopeMap(ctx, req)
	if errors.Is(e, generator.ErrNotConfigured) {
		return worker.Skipped("llm_not_configured")
	}
	if errors.Is(e, generator.ErrCredentialMissing) {
		return worker.Skipped("model_credential_missing")
	}
	_ = t.Cost(ctx, mustJSON(cost))
	if e != nil {
		if errors.Is(e, generator.ErrUncertainCost) {
			return worker.Permanent(e)
		}
		return e
	}
	repos := make([]string, 0, len(req.Repos))
	owners := map[string]map[string]bool{}
	for _, r := range req.Repos {
		repos = append(repos, r.RepoID)
		owners[r.RepoID] = generator.CodeownersTeams(r.Codeowners)
	}
	sort.Strings(repos)
	m.Repos = repos
	if findings := domain.ValidateScopeMap(m, repos, owners); len(findings) > 0 {
		// Retrying the same call cannot repair a structure the model could not
		// build, so this is permanent and the findings are the result.
		t.Result = mustJSON(map[string]any{"findings": findings, "cost": cost})
		return worker.Permanent(fmt.Errorf("proposed scope map is not valid: %s",
			strings.Join(findings, "; ")))
	}
	proposalID, created, e := w.store(ctx, t, payload, m, recipe, cost)
	if e != nil {
		return e
	}
	t.Result = mustJSON(map[string]any{"proposal_id": proposalID, "created": created,
		"origin": m.Origin, "nodes": len(m.Nodes), "repos": repos, "cost": cost})
	return nil
}

// resolve picks what answers the question: the organisation's own provider and
// key when it has one, the deployment's generator otherwise. It is the same
// rule `proposal.generate` follows (ADR-0045), for the same reason — running a
// deployment's key on an organisation's behalf is the cross-tenant charge BYOK
// exists to prevent.
func (w *ScopeMapWorker) resolve(ctx context.Context, orgID string) (generator.Generator,
	generator.Recipe, string, error) {
	provider, model, key, e := secrets.OpenPreferred(ctx, w.pool, w.keyring, orgID)
	switch {
	case e == nil:
		engine, recipe, e := generator.ForOrganisation(provider, model, nil)
		if e != nil {
			return nil, generator.Recipe{}, "", e
		}
		return engine, recipe, key, nil
	case errors.Is(e, secrets.ErrNoCredential), errors.Is(e, secrets.ErrNoKeyring):
		return w.engine, w.recipe, "", nil
	default:
		return nil, generator.Recipe{}, "", e
	}
}

// request assembles the closed list of ADR-0051 decision 3. Everything it reads
// is structure; nothing it reads is code.
func (w *ScopeMapWorker) request(ctx context.Context, orgID string,
	limits generator.ScopeMapLimits) (generator.ScopeMapRequest, error) {
	req := generator.ScopeMapRequest{OrgID: orgID, Limits: limits}
	rows, e := w.pool.Query(ctx, `SELECT repo_id FROM gfm.repos
 WHERE org_id=$1::uuid ORDER BY repo_id LIMIT $2`, orgID, limits.MaxRepos)
	if e != nil {
		return req, e
	}
	var repos []string
	for rows.Next() {
		var id string
		if e := rows.Scan(&id); e != nil {
			rows.Close()
			return req, e
		}
		repos = append(repos, id)
	}
	rows.Close()
	if e := rows.Err(); e != nil {
		return req, e
	}
	for _, repoID := range repos {
		r := generator.ScopeMapRepo{RepoID: repoID}
		dirs, e := w.skillDirs(ctx, orgID, repoID, limits.MaxPathsPerRepo)
		if e != nil {
			return req, e
		}
		r.SkillDirs = dirs
		scopes, e := scopeRows(ctx, w.pool, orgID, repoID)
		if e != nil {
			return req, e
		}
		r.Existing = scopes
		if r.Codeowners, e = documentBody(ctx, w.pool, w.blobs, orgID, repoID, codeownersPaths...); e != nil {
			return req, e
		}
		if r.GuidefoldYAML, e = documentBody(ctx, w.pool, w.blobs, orgID, repoID, "guidefold.yaml"); e != nil {
			return req, e
		}
		readme, e := documentBody(ctx, w.pool, w.blobs, orgID, repoID, "README.md")
		if e != nil {
			return req, e
		}
		agents, e := documentBody(ctx, w.pool, w.blobs, orgID, repoID, "AGENTS.md")
		if e != nil {
			return req, e
		}
		r.ReadmeHead, r.AgentsHead = head(readme), head(agents)
		req.Repos = append(req.Repos, r)
	}
	return req, nil
}

// head is the "first 400 characters" of ADR-0051 decision 3, counted in runes
// so a multi-byte character is never cut in half.
func head(text string) string {
	runes := []rune(strings.TrimSpace(text))
	if len(runes) > generator.ScopeMapHeadChars {
		runes = runes[:generator.ScopeMapHeadChars]
	}
	return string(runes)
}

// skillDirs lists the directories a repository actually governs: the directory
// a `SKILL.md` sits in, with the `.agents/skills/<name>` tail removed, so the
// answer is "this part of the tree has rules" rather than "this is where the
// file happens to live".
func (w *ScopeMapWorker) skillDirs(ctx context.Context, orgID, repoID string, limit int) ([]string, error) {
	rows, e := w.pool.Query(ctx, `SELECT DISTINCT path FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND source_status<>'removed' ORDER BY path LIMIT $3`,
		orgID, repoID, limit)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	seen := map[string]bool{}
	out := []string{}
	for rows.Next() {
		var path string
		if e := rows.Scan(&path); e != nil {
			return nil, e
		}
		dir := governedDir(path)
		if dir == "" || seen[dir] {
			continue
		}
		seen[dir] = true
		out = append(out, dir)
	}
	if e := rows.Err(); e != nil {
		return nil, e
	}
	sort.Strings(out)
	return out, nil
}

// governedDir turns `platforms/atlas/.agents/skills/turnstile/SKILL.md` into
// `platforms/atlas`. A skill at the repository root returns "", which the
// inferred map reads as `_root`.
func governedDir(path string) string {
	if i := strings.Index(path, "/.agents/"); i >= 0 {
		return path[:i]
	}
	if strings.HasPrefix(path, ".agents/") {
		return ""
	}
	if i := strings.LastIndex(path, "/"); i >= 0 {
		return path[:i]
	}
	return ""
}

// scopeRows is the projection of gfm.scopes the worker needs. It is the same
// read `Service.existingScopes` performs, kept as one function so the worker
// and the API cannot disagree about what "the scopes this repository has" means.
func scopeRows(ctx context.Context, pool *pgxpool.Pool, orgID, repoID string) ([]domain.ExistingScope, error) {
	rows, e := pool.Query(ctx, `SELECT repo_id,scope,COALESCE(parent,''),COALESCE(owner,''),
 paths,source FROM gfm.scopes WHERE org_id=$1::uuid AND repo_id=$2 ORDER BY scope`, orgID, repoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []domain.ExistingScope{}
	for rows.Next() {
		var x domain.ExistingScope
		if e := rows.Scan(&x.RepoID, &x.Scope, &x.Parent, &x.Owner, &x.Paths, &x.Source); e != nil {
			return nil, e
		}
		out = append(out, x)
	}
	return out, rows.Err()
}

// store writes the draft proposal. The cache key is the whole dedupe rule: two
// imports in a row over an unchanged structure collide with the row that
// already holds the owner's decision instead of producing a second map.
func (w *ScopeMapWorker) store(ctx context.Context, t *worker.Task, payload scopeMapPayload,
	m domain.ScopeMap, recipe generator.Recipe, cost generator.Cost) (string, bool, error) {
	body, e := json.MarshalIndent(m, "", "  ")
	if e != nil {
		return "", false, e
	}
	contentSHA := digest(string(body))
	if _, e := w.blobs.Put(ctx, payload.OrgID, contentSHA, body); e != nil {
		return "", false, fmt.Errorf("store scope map: %w", e)
	}
	inputs := make([]string, 0, len(m.Nodes))
	for _, n := range m.Nodes {
		for _, p := range n.Paths {
			inputs = append(inputs, p.RepoID+"/"+p.Path)
		}
	}
	key := generator.CacheKey(payload.OrgID, KindScopeMap, inputs, recipe, m.Origin)
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", false, e
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return "", false, e
	}
	proposalID := newID()
	var stored string
	e = tx.QueryRow(ctx, `INSERT INTO gfm.proposals
 (org_id,proposal_id,repo_id,import_id,job_id,kind,state,candidate_path,candidate_sha256,
  candidate_blob_sha256,candidate_frontmatter,sources,recipe_version,generator,model,cache_key,cost)
 VALUES($1::uuid,$2::uuid,$3,$4::uuid,$5::uuid,$6,'draft',$7,$8,$8,'{}'::jsonb,'[]'::jsonb,
  $9,$10,$11,$12,$13::jsonb)
 ON CONFLICT (org_id,cache_key) DO NOTHING
 RETURNING proposal_id::text`,
		payload.OrgID, proposalID, payload.RepoID, nullable(payload.ImportID),
		nullable(t.Job.JobID), KindScopeMap, ScopeMapCandidatePath, contentSHA,
		recipe.Version, recipe.Generator, nullable(recipe.Model), key,
		string(mustJSON(cost))).Scan(&stored)
	if isNoRows(e) {
		// The same structure under the same recipe has already been proposed —
		// and possibly already decided. Nothing new is produced.
		return "", false, nil
	}
	if e != nil {
		return "", false, e
	}
	// One provenance row per node, so the proposal says where each node came
	// from. `inferred` for every node, including a model's: a model never quotes
	// a file here, so `source` would be a claim the request cannot support
	// (API-CONTRACT §8, "każde pole mówi, skąd pochodzi").
	for _, n := range m.Nodes {
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.proposal_fields
 (org_id,proposal_id,field,origin,needs_confirmation)
 VALUES($1::uuid,$2::uuid,$3,$4,true)
 ON CONFLICT (org_id,proposal_id,field) DO NOTHING`,
			payload.OrgID, stored, "scope:"+n.Scope, generator.OriginInferred); e != nil {
			return "", false, e
		}
	}
	if e := mgmt.Audit(ctx, tx, payload.OrgID, "worker", "proposal.create",
		"proposal:"+stored, key, t.Job.JobID); e != nil {
		return "", false, e
	}
	if e := tx.Commit(ctx); e != nil {
		return "", false, e
	}
	return stored, true, nil
}

// EnqueueScopeMap queues one `scope_map.propose` for an organisation after an
// import of one of its repositories succeeded.
//
// It is exported because the enqueue belongs to the import worker's own flow —
// `import.parse` is the event, and only it knows the import finished — while
// the job, the payload and the proposal belong to this module. The port that
// joins the two is declared in `internal/importer`; this is its implementation.
//
// The queue's own unique `(org_id, idempotency_key)` makes a repeated call a
// no-op, so a retried parse job does not queue a second proposal.
func EnqueueScopeMap(ctx context.Context, queue *jobs.Queue, tx pgx.Tx,
	orgID, repoID, importID string) error {
	payload := scopeMapPayload{SchemaVersion: ScopeMapPayloadVersion, OrgID: orgID,
		RepoID: repoID, ImportID: importID}
	_, e := queue.Enqueue(ctx, tx, jobs.Job{OrgID: orgID, RepoID: repoID, ImportID: importID,
		Kind: KindScopeMapPropose, Payload: mustJSON(payload),
		IdempotencyKey: KindScopeMapPropose + ":" + importID})
	return e
}

// ScopeMapFollowUp is the adapter behind `importer.ImportFollowUp`: after an
// import lands, it decides whether this organisation can be asked for a map at
// all, and queues the job only then.
//
// The decision lives here rather than in the import worker because it is about
// generation, not about importing: the organisation's model key (ADR-0045) and
// the deployment's generator are this module's concerns, and the import module
// has no business knowing either.
type ScopeMapFollowUp struct {
	pool      *pgxpool.Pool
	queue     *jobs.Queue
	generator string
}

// NewScopeMapFollowUp builds it from the deployment's configured generator.
func NewScopeMapFollowUp(pool *pgxpool.Pool) (*ScopeMapFollowUp, error) {
	_, recipe, e := generator.Select(nil)
	if e != nil {
		return nil, e
	}
	return &ScopeMapFollowUp{pool: pool, queue: jobs.New(pool), generator: recipe.Generator}, nil
}

// AfterImport queues `scope_map.propose` when something could answer it.
//
// The pre-check on `gfm.org_credentials` asks only whether a row exists; it
// never opens the key. That is the same read `internal/live` performs before
// starting a run, and for the same reason: deciding whether to start work is
// not a reason to decrypt a secret.
//
// A failed import is not here at all: `import.parse` only calls its follow-up
// after the catalog transaction committed, so `state` is `ready` or `partial`.
func (f *ScopeMapFollowUp) AfterImport(ctx context.Context, orgID, repoID, importID, state string) error {
	if state != "ready" && state != "partial" {
		return nil
	}
	if f.generator == generator.NameNone {
		var hasKey bool
		if e := f.pool.QueryRow(ctx, `SELECT EXISTS(
 SELECT 1 FROM gfm.org_credentials WHERE org_id=$1::uuid)`, orgID).Scan(&hasKey); e != nil {
			return e
		}
		if !hasKey {
			// Nothing could answer. Queuing a job so it can end `skipped` would
			// turn "this deployment has no generator" into a line of noise on
			// every import (#146, #167: importing must not need a model key).
			return nil
		}
	}
	tx, e := f.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if e := EnqueueScopeMap(ctx, f.queue, tx, orgID, repoID, importID); e != nil {
		return e
	}
	return tx.Commit(ctx)
}
