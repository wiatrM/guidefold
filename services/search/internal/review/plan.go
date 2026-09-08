package review

import (
	"context"
	"encoding/json"
	"net/http"
	"sort"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// Limits are the ceilings one generation run may not cross. They are part of
// the plan response *and* of the job row, so an owner sees the same numbers the
// worker will enforce before agreeing to spend anything (U2.7).
//
// The two that stop a combinatorial explosion are MaxGroups and MaxNeighbours.
// Consolidation compares procedures inside one group of at most MaxNeighbours
// skills, so the number of comparisons is bounded by the group size and never
// by the size of the catalog: this is deliberately not an all-pairs pass over
// the repository.
type Limits struct {
	MaxFiles             int     `json:"max_files"`
	MaxBytes             int64   `json:"max_bytes"`
	MaxTokens            int     `json:"max_tokens"`
	MaxGroups            int     `json:"max_groups"`
	MaxProposalsPerGroup int     `json:"max_proposals_per_group"`
	MaxNeighbours        int     `json:"max_neighbours"`
	MaxCalls             int     `json:"max_calls"`
	MaxUSD               float64 `json:"max_usd"`
}

// DefaultLimits are the contract's numbers (API-CONTRACT §8, `limits`).
func DefaultLimits() Limits {
	return Limits{MaxFiles: 20, MaxBytes: 1 << 20, MaxTokens: 24000, MaxGroups: 5,
		MaxProposalsPerGroup: 5, MaxNeighbours: 10, MaxCalls: 15, MaxUSD: 5}
}

// clampTo lowers every field to the ceiling and refuses to raise any of them. A
// caller may ask for less work; nobody may ask the service to spend more than
// the deployment allows.
func (l Limits) clampTo(ceiling Limits) Limits {
	out := ceiling
	pairs := []struct {
		got, max *int
	}{
		{&l.MaxFiles, &out.MaxFiles}, {&l.MaxTokens, &out.MaxTokens},
		{&l.MaxGroups, &out.MaxGroups}, {&l.MaxProposalsPerGroup, &out.MaxProposalsPerGroup},
		{&l.MaxNeighbours, &out.MaxNeighbours}, {&l.MaxCalls, &out.MaxCalls},
	}
	for _, p := range pairs {
		if *p.got > 0 && *p.got < *p.max {
			*p.max = *p.got
		}
	}
	if l.MaxBytes > 0 && l.MaxBytes < out.MaxBytes {
		out.MaxBytes = l.MaxBytes
	}
	if l.MaxUSD > 0 && l.MaxUSD < out.MaxUSD {
		out.MaxUSD = l.MaxUSD
	}
	return out
}

func (l Limits) generator() generator.Limits {
	return generator.Limits{MaxProposals: l.MaxProposalsPerGroup, MaxNeighbours: l.MaxNeighbours,
		MaxTokens: l.MaxTokens, MaxCalls: l.MaxCalls, MaxUSD: l.MaxUSD}
}

// Input is one file a group reads.
//
// `Scope`/`Owner` are the input's *own* scope and owner, which is not the
// group's once a group spans siblings: a consolidation group under `atlas`
// holds skills from `atlas.geo` and `atlas.graph`, and a generator that cannot
// tell them apart cannot know it is raising the scope at all.
type Input struct {
	Kind       string `json:"kind"` // document | skill
	Path       string `json:"path"`
	SHA256     string `json:"sha256"`
	Size       int64  `json:"size"`
	SkillID    string `json:"skill_id,omitempty"`
	RevisionID string `json:"revision_id,omitempty"`
	Scope      string `json:"scope,omitempty"`
	Owner      string `json:"owner,omitempty"`
}

// Group is one unit of generation work: one kind over one scope's inputs.
//
// The job payload carries the whole struct — the worker needs each input's
// digest to read its bytes and to build the cache key. The API answers with
// `view`, whose `inputs` is the list of names the `ImportPlanGroup` DTO
// specifies (API-CONTRACT §5.2).
type Group struct {
	GroupID        string  `json:"group_id"`
	Kind           string  `json:"kind"`
	Scope          string  `json:"scope"`
	Owner          *string `json:"owner"`
	Inputs         []Input `json:"inputs"`
	EstimatedCalls int     `json:"estimated_calls"`
}

// view renders one group as the ImportPlanGroup DTO.
func (g Group) view() map[string]any {
	names := make([]string, 0, len(g.Inputs))
	bytes := int64(0)
	for _, in := range g.Inputs {
		if in.SkillID != "" {
			names = append(names, in.SkillID)
		} else {
			names = append(names, in.Path)
		}
		bytes += in.Size
	}
	return map[string]any{"group_id": g.GroupID, "kind": g.Kind, "scope": g.Scope,
		"owner": g.Owner, "inputs": names, "n_inputs": len(names),
		// A byte-count proxy, not a tokeniser: it is an estimate the plan is
		// allowed to be wrong about, and JobCost after the fact is decisive.
		"estimated_tokens": bytes / 4, "estimated_calls": g.EstimatedCalls}
}

func groupViews(groups []Group) []map[string]any {
	out := make([]map[string]any, 0, len(groups))
	for _, g := range groups {
		out = append(out, g.view())
	}
	return out
}

// planKinds is the closed set of generation kinds.
var planKinds = []string{generator.KindExtraction, generator.KindEnrichment, generator.KindConsolidation}

// handlePlan answers what a generation run would do, and what it could cost,
// before anything runs. Nothing here enqueues, spends or writes.
func (s *Service) handlePlan(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	importID := c.Param("import_id")
	if !parseUUID(importID) {
		return notFound("import_not_found", "No such import in this repository.")
	}
	kinds, e := requestedKinds(c.Query("kinds"))
	if e != nil {
		return e
	}
	profile, e := parseProfile(c.Query("profile"))
	if e != nil {
		return e
	}
	limits := withProfile(DefaultLimits(), profile)
	groups, skipped, err := s.plan(c.Ctx(), rc, importID, kinds, limits)
	if err != nil {
		return err
	}
	limits = fitGroups(limits, groups, profile)
	body := s.planBody(rc, importID, groups, skipped, limits)
	body["profile"] = profileName(profile)
	return c.JSON(http.StatusOK, body)
}

// profileName renders the profile the plan ran under. `default` rather than an
// empty string, because a client reading a blank field cannot tell "the default"
// from "the server does not know about profiles".
func profileName(profile string) string {
	if profile == ProfileOneShot {
		return ProfileOneShot
	}
	return "default"
}

func (s *Service) planBody(rc *repoContext, importID string, groups []Group, skipped map[string]int,
	limits Limits) map[string]any {
	calls := 0
	for _, g := range groups {
		calls += g.EstimatedCalls
	}
	// A deterministic recipe costs nothing and says so; a provider recipe cannot
	// promise a price, so the plan states the ceiling the run will not cross
	// rather than a forecast it cannot keep.
	estimate := 0.0
	if s.recipe.Generator != generator.NameNone && s.recipe.Generator != generator.NameDeterministic {
		estimate = limits.MaxUSD
	}
	views := groupViews(groups)
	return map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"import_id": importID,
		"generator": map[string]any{
			// `name`/`configured` are what the UI decodes; `generator`/`version`/
			// `model` name the exact recipe the cache key is built from.
			"name": s.recipe.Generator, "configured": s.recipe.Generator != generator.NameNone,
			"generator": s.recipe.Generator, "version": s.recipe.Version,
			"model": nullable(s.recipe.Model)},
		"groups": views, "limits": limits, "groups_skipped": skipped,
		"estimated_calls": calls, "estimated_usd_max": estimate,
	}
}

func requestedKinds(raw string) ([]string, error) {
	if strings.TrimSpace(raw) == "" {
		return append([]string{}, planKinds...), nil
	}
	out := []string{}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		known := false
		for _, k := range planKinds {
			if k == part {
				known = true
			}
		}
		if !known {
			return nil, mgmt.Invalid("invalid_request",
				"kinds must be a subset of extraction, enrichment, consolidation.")
		}
		for _, existing := range out {
			if existing == part {
				known = false
			}
		}
		if known {
			out = append(out, part)
		}
	}
	if len(out) == 0 {
		return nil, mgmt.Invalid("invalid_request", "kinds names no known generation kind.")
	}
	return out, nil
}

// plan groups the import's inputs by scope.
//
// Grouping by scope is what makes the run reviewable: the owner of a scope sees
// the candidates built from that scope's own material, and the number of groups
// is bounded by MaxGroups rather than by the repository's size.
func (s *Service) plan(ctx context.Context, rc *repoContext, importID string,
	kinds []string, limits Limits) ([]Group, map[string]int, error) {
	var exists bool
	if e := s.pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid)`,
		rc.Org.ID, rc.RepoID, importID).Scan(&exists); e != nil {
		return nil, nil, mgmt.Internal(e)
	}
	if !exists {
		return nil, nil, notFound("import_not_found", "No such import in this repository.")
	}
	owners, e := s.scopeOwners(ctx, rc)
	if e != nil {
		return nil, nil, mgmt.Internal(e)
	}
	out := []Group{}
	skipped := map[string]int{}
	for _, kind := range kinds {
		var byScope map[string][]Input
		var err error
		if kind == generator.KindExtraction {
			byScope, err = s.documentsByScope(ctx, rc, importID, limits)
		} else {
			byScope, err = s.skillsByScope(ctx, rc, limits)
		}
		if err != nil {
			return nil, nil, mgmt.Internal(err)
		}
		if kind == generator.KindConsolidation {
			byScope = consolidationGroups(byScope, limits)
		}
		scopes := make([]string, 0, len(byScope))
		for scope := range byScope {
			inputs := byScope[scope]
			// Consolidation needs at least two procedures to compare; a group of
			// one is not a candidate for a shared element, it is one skill.
			if kind == generator.KindConsolidation && len(inputs) < 2 {
				continue
			}
			scopes = append(scopes, scope)
		}
		// A run is capped at MaxGroups, so which groups it keeps is a decision,
		// not an accident of iteration order. The scopes with the most material
		// go first — that is where a shared element or an extractable procedure
		// is most likely — and ties are broken by name so two plans over the
		// same catalog are identical.
		sort.Slice(scopes, func(i, j int) bool {
			a, b := byScope[scopes[i]], byScope[scopes[j]]
			if len(a) != len(b) {
				return len(a) > len(b)
			}
			return scopes[i] < scopes[j]
		})
		for i, scope := range scopes {
			if i >= limits.MaxGroups {
				// Named, not hidden: the plan says how many scopes the ceiling
				// left out so an owner can raise it or run them separately.
				skipped[kind] += len(scopes) - i
				break
			}
			owner := owners[scope]
			out = append(out, Group{
				GroupID: groupID(kind, scope), Kind: kind, Scope: scope,
				Owner: optional(owner), Inputs: byScope[scope], EstimatedCalls: 1,
			})
		}
	}
	return out, skipped, nil
}

func groupID(kind, scope string) string {
	if scope == "" {
		scope = "_root"
	}
	return kind + ":" + scope
}

func (s *Service) scopeOwners(ctx context.Context, rc *repoContext) (map[string]string, error) {
	rows, e := s.pool.Query(ctx, `SELECT scope,COALESCE(owner,'') FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2`, rc.Org.ID, rc.RepoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var scope, owner string
		if e = rows.Scan(&scope, &owner); e != nil {
			return nil, e
		}
		out[scope] = owner
	}
	return out, rows.Err()
}

func (s *Service) documentsByScope(ctx context.Context, rc *repoContext, importID string,
	limits Limits) (map[string][]Input, error) {
	rows, e := s.pool.Query(ctx, `SELECT path,sha256,size_bytes,COALESCE(scope,'_root')
 FROM gfm.documents WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid
 ORDER BY scope,path`, rc.Org.ID, rc.RepoID, importID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := map[string][]Input{}
	for rows.Next() {
		var in Input
		var scope string
		if e = rows.Scan(&in.Path, &in.SHA256, &in.Size, &scope); e != nil {
			return nil, e
		}
		in.Kind = "document"
		in.Scope = scope
		if in.Size > limits.MaxBytes || len(out[scope]) >= limits.MaxFiles {
			continue
		}
		out[scope] = append(out[scope], in)
	}
	return out, rows.Err()
}

func (s *Service) skillsByScope(ctx context.Context, rc *repoContext, limits Limits) (map[string][]Input, error) {
	rows, e := s.pool.Query(ctx, `SELECT s.skill_id,s.path,s.scope,COALESCE(s.owner,''),
 r.content_sha256,r.revision_id
 FROM gfm.skills s JOIN gfm.skill_revisions r
   ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.source_status='active'
 ORDER BY s.scope,s.skill_id`, rc.Org.ID, rc.RepoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := map[string][]Input{}
	for rows.Next() {
		var in Input
		var scope string
		if e = rows.Scan(&in.SkillID, &in.Path, &scope, &in.Owner, &in.SHA256,
			&in.RevisionID); e != nil {
			return nil, e
		}
		in.Kind = "skill"
		in.Scope = scope
		// MaxNeighbours is the cap that keeps consolidation away from an
		// all-pairs pass: at most this many procedures are compared per group.
		if len(out[scope]) >= limits.MaxNeighbours {
			continue
		}
		out[scope] = append(out[scope], in)
	}
	return out, rows.Err()
}

// generateRequest is the body of POST …/proposals:generate.
type generateRequest struct {
	IdempotencyKey string   `json:"idempotency_key"`
	Kinds          []string `json:"kinds"`
	Limits         *Limits  `json:"limits"`
	// Profile picks the run's ceilings before the caller's own clamping.
	// `one_shot` plans every group the import produced; the money ceilings do
	// not move (API-CONTRACT §4.2).
	Profile string `json:"profile"`
}

// generatePayload is the proposal.generate job contract (API-CONTRACT §8). One
// job carries one kind and every group of that kind, so the checkpoint can name
// the last group it finished and a restart resumes rather than repeats.
type generatePayload struct {
	SchemaVersion string  `json:"schema_version"`
	OrgID         string  `json:"org_id"`
	RepoID        string  `json:"repo_id"`
	ImportID      string  `json:"import_id"`
	Kind          string  `json:"kind"`
	Groups        []Group `json:"groups"`
}

// handleGenerate enqueues the planned work. Every job of the run is written in
// one transaction: a partially enqueued run would spend money on half a plan.
func (s *Service) handleGenerate(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	importID := c.Param("import_id")
	if !parseUUID(importID) {
		return notFound("import_not_found", "No such import in this repository.")
	}
	var req generateRequest
	if len(c.Body) > 0 {
		if e := c.Decode(&req); e != nil {
			return e
		}
	}
	kinds := append([]string{}, planKinds...)
	if len(req.Kinds) > 0 {
		kinds, e = requestedKinds(strings.Join(req.Kinds, ","))
		if e != nil {
			return e
		}
	}
	profile, e := parseProfile(req.Profile)
	if e != nil {
		return e
	}
	// The profile raises the ceiling; the caller may still ask for less. The
	// order matters: clamping first would let a one-shot request quietly restore
	// a limit the caller had lowered on purpose.
	limits := withProfile(DefaultLimits(), profile)
	if req.Limits != nil {
		limits = req.Limits.clampTo(limits)
	}
	groups, skipped, err := s.plan(c.Ctx(), rc, importID, kinds, limits)
	if err != nil {
		return err
	}
	limits = fitGroups(limits, groups, profile)
	if len(groups) > limits.MaxGroups*len(kinds) {
		return mgmt.Unprocessable("limit_exceeded", "The plan exceeds max_groups for this run.")
	}

	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	encodedLimits := mustJSON(limits)
	jobIDs := []string{}
	for _, kind := range kinds {
		mine := []Group{}
		for _, g := range groups {
			if g.Kind == kind {
				mine = append(mine, g)
			}
		}
		if len(mine) == 0 {
			continue
		}
		payload, _ := json.Marshal(generatePayload{SchemaVersion: GeneratePayloadVersion,
			OrgID: rc.Org.ID, RepoID: rc.RepoID, ImportID: importID, Kind: kind, Groups: mine})
		job, e := s.queue.Enqueue(c.Ctx(), tx, jobs.Job{
			OrgID: rc.Org.ID, RepoID: rc.RepoID, ImportID: importID, Kind: KindGenerate,
			Payload: payload, Limits: encodedLimits, RecipeVersion: s.recipe.Version,
			InputDigest: groupDigest(mine),
			// One job per (import, kind): asking twice resumes the same run
			// rather than paying for a second one.
			IdempotencyKey: KindGenerate + ":" + importID + ":" + kind,
		})
		if e != nil {
			return mgmt.Internal(e)
		}
		jobIDs = append(jobIDs, job.JobID)
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposals.generate", "import:"+importID,
		s.recipe.Version); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	body := s.planBody(rc, importID, groups, skipped, limits)
	body["profile"] = profileName(profile)
	body["job_ids"] = jobIDs
	body["plan"] = map[string]any{"groups": groupViews(groups), "limits": limits,
		"groups_skipped": skipped, "profile": profileName(profile)}
	return c.JSON(http.StatusOK, body)
}

func groupDigest(groups []Group) string {
	digests := []string{}
	for _, g := range groups {
		for _, in := range g.Inputs {
			digests = append(digests, in.SHA256)
		}
	}
	return generator.CacheKey("", "", digests, generator.Recipe{}, "")
}

// loadImportCommit reads the commit an import carried, which the export uses as
// the patch's base.
func (s *Service) loadImportCommit(ctx context.Context, orgID, importID string) (string, error) {
	var commit *string
	e := s.pool.QueryRow(ctx, `SELECT commit FROM gfm.imports
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, orgID, importID).Scan(&commit)
	if isNoRows(e) {
		return "", nil
	}
	if e != nil {
		return "", e
	}
	return str(commit), nil
}
