package review

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// GenerateWorker runs proposal.generate: one kind over the groups the plan
// produced.
//
// One job holds every group of its kind so the checkpoint can say which group
// was the last one finished. A worker that dies mid-run resumes at the next
// group, and the groups it already did produce nothing new, because every
// candidate is keyed by sha256(org, inputs, recipe, model, identity) and the
// unique index on that key rejects the second insert (API-CONTRACT §8, U2.3).
type GenerateWorker struct {
	pool   *pgxpool.Pool
	blobs  BlobStore
	engine generator.Generator
	recipe generator.Recipe
}

// generateCheckpoint is what a restarted job reads. It records progress, not
// "which rows were written": the cache key is what makes resuming safe.
type generateCheckpoint struct {
	Groups int             `json:"groups_done"`
	Cost   generator.Cost  `json:"cost"`
	Notes  json.RawMessage `json:"abstentions,omitempty"`
}

// NewGenerateWorker wires the job handler with the configured generator.
func NewGenerateWorker(pool *pgxpool.Pool, blobs BlobStore) (*GenerateWorker, error) {
	engine, recipe, e := generator.Select(nil)
	if e != nil {
		return nil, e
	}
	return &GenerateWorker{pool: pool, blobs: blobs, engine: engine, recipe: recipe}, nil
}

// WithGenerator replaces the engine, which is how a test drives the same worker
// against an httptest fake provider without changing the process environment.
func (w *GenerateWorker) WithGenerator(engine generator.Generator, recipe generator.Recipe) *GenerateWorker {
	w.engine, w.recipe = engine, recipe
	return w
}

// Handlers maps the job kind this worker runs.
func (w *GenerateWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindGenerate: w.Run}
}

// Run executes one proposal.generate job.
func (w *GenerateWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload generatePayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode proposal.generate payload: %w", e))
	}
	if payload.SchemaVersion != GeneratePayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported payload schema_version %q", payload.SchemaVersion))
	}
	// The job carries its own identity claim; it has to agree with the row the
	// queue handed out before anything is read or written for that tenant.
	if payload.OrgID != t.Job.OrgID || payload.RepoID != t.Job.RepoID ||
		payload.ImportID != t.Job.ImportID {
		return worker.Permanent(errors.New("proposal.generate payload does not match its job row"))
	}
	limits := DefaultLimits()
	if len(t.Job.Limits) > 0 {
		_ = json.Unmarshal(t.Job.Limits, &limits)
	}
	var cp generateCheckpoint
	_ = json.Unmarshal(t.Job.Checkpoint, &cp)

	total := cp.Cost
	produced, skipped := 0, 0
	abstentions := []generator.Abstention{}
	stopped := ""
	for i := cp.Groups; i < len(payload.Groups); i++ {
		if e := ctx.Err(); e != nil {
			return e
		}
		// The cost ceiling stops *new* calls and keeps everything already done.
		// A run that hit its budget is a finished job with a named stop reason,
		// not a failure and not a silent truncation (PRODUCT-PIVOT U2 AC7).
		if limits.MaxUSD > 0 && total.USDCertain+total.USDUncertain >= limits.MaxUSD {
			stopped = "max_usd_reached"
			break
		}
		if limits.MaxCalls > 0 && total.Calls >= limits.MaxCalls {
			stopped = "max_calls_reached"
			break
		}
		group := payload.Groups[i]
		// The generator is told what is *left* of the call budget, not the
		// job's original ceiling, so its own retries cannot spend past it.
		remaining := limits
		if remaining.MaxCalls > 0 {
			remaining.MaxCalls -= total.Calls
		}
		req, e := w.request(ctx, payload, group, remaining)
		if e != nil {
			return e
		}
		out, cost, e := w.engine.Generate(ctx, req)
		total.Add(cost)
		if errors.Is(e, generator.ErrNotConfigured) {
			// No generator is configured. The import stays exactly as it is —
			// the skills a repository already has do not depend on a model.
			return worker.Skipped("llm_not_configured")
		}
		if e != nil {
			// The cost of a failed attempt is still recorded before the retry.
			_ = t.Cost(ctx, mustJSON(total))
			if errors.Is(e, generator.ErrUncertainCost) {
				return worker.Permanent(fmt.Errorf("group %s: %w", group.GroupID, e))
			}
			return fmt.Errorf("group %s: %w", group.GroupID, e)
		}
		abstentions = append(abstentions, out.Abstentions...)
		n, s, e := w.store(ctx, t, payload, group, req, out)
		if e != nil {
			return e
		}
		produced += n
		skipped += s
		cp = generateCheckpoint{Groups: i + 1, Cost: total, Notes: mustJSON(abstentions)}
		if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
			return e
		}
		if e := t.Cost(ctx, mustJSON(total)); e != nil {
			return e
		}
	}
	result := map[string]any{"kind": payload.Kind, "groups": len(payload.Groups),
		"groups_done": maxInt(cp.Groups, 0), "candidates": produced, "deduplicated": skipped,
		"abstentions": abstentions, "cost": total}
	if stopped != "" {
		result["stopped"] = stopped
	}
	t.Result = mustJSON(result)
	return nil
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// request loads one group's bytes out of the blob store.
func (w *GenerateWorker) request(ctx context.Context, payload generatePayload, group Group,
	limits Limits) (generator.Request, error) {
	req := generator.Request{Kind: payload.Kind, OrgID: payload.OrgID, RepoID: payload.RepoID,
		Scope: group.Scope, Owner: str(group.Owner), GroupID: group.GroupID,
		Limits: limits.generator()}
	commit, e := w.importCommit(ctx, payload.OrgID, payload.ImportID)
	if e != nil {
		return req, e
	}
	for _, in := range group.Inputs {
		raw, e := w.blobs.Get(ctx, payload.OrgID, in.SHA256)
		if e != nil {
			// A blob that has been retained away is a group the run cannot read.
			// Skipping the input is honest; inventing text for it is not.
			continue
		}
		// Each input keeps its own scope and owner. In a consolidation group they
		// differ from the group's — that is exactly what makes a shared element a
		// scope raise — and reading the group's for every input would hide the
		// raise from the generator and from the reviewer (P08).
		scope, owner := in.Scope, in.Owner
		if scope == "" {
			scope = group.Scope
		}
		if owner == "" {
			owner = str(group.Owner)
		}
		if in.Kind == "document" {
			req.Documents = append(req.Documents, generator.Document{Path: in.Path,
				SHA256: in.SHA256, Commit: commit, Scope: scope,
				Owner: owner, Body: string(raw)})
			continue
		}
		skill := generator.Skill{SkillID: in.SkillID, RevisionID: in.RevisionID, Path: in.Path,
			SHA256: in.SHA256, Scope: scope, Owner: owner, Body: string(raw)}
		if e := w.pool.QueryRow(ctx, `SELECT name,description FROM gfm.skills
 WHERE org_id=$1::uuid AND skill_id=$2`, payload.OrgID, in.SkillID).
			Scan(&skill.Name, &skill.Description); e != nil && !errors.Is(e, pgx.ErrNoRows) {
			return req, e
		}
		req.Skills = append(req.Skills, skill)
	}
	dirs, e := w.scopeDirs(ctx, payload.OrgID, payload.RepoID, req)
	if e != nil {
		return req, e
	}
	req.ScopeDirs = dirs
	return req, nil
}

// scopeDirs resolves every scope this request's group and inputs touch to its
// real on-disk directory, from guidefold.yaml's own declared node paths
// (gfm.scopes, written by import.parse -- see writeScopes in
// internal/importer/parse.go). candidatePath needs this because a scope's
// dotted name does not have to mirror its directory: the Meridian fixture's
// `atlas` node lives at `platforms/atlas/**`, not `atlas/` (2026-09-08 ACT-01
// finding). A scope this query finds nothing for is simply absent from the
// returned map; candidatePath falls back to the dotted-name guess for it.
//
// This reads a table import.parse wrote through a direct, single-purpose
// query -- the explicit projection module-boundaries-go asks for in place of
// reaching into review's own tables, mirroring the `gfm.skills` read four
// lines above it in request().
func (w *GenerateWorker) scopeDirs(ctx context.Context, orgID, repoID string, req generator.Request) (map[string]string, error) {
	scopes := map[string]bool{}
	if req.Scope != "" {
		scopes[req.Scope] = true
	}
	for _, d := range req.Documents {
		if d.Scope != "" {
			scopes[d.Scope] = true
		}
	}
	for _, s := range req.Skills {
		if s.Scope != "" {
			scopes[s.Scope] = true
		}
	}
	if len(scopes) == 0 {
		return nil, nil
	}
	names := make([]string, 0, len(scopes))
	for name := range scopes {
		names = append(names, name)
	}
	rows, e := w.pool.Query(ctx, `SELECT scope,paths FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2 AND scope = ANY($3::text[])`, orgID, repoID, names)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	dirs := map[string]string{}
	for rows.Next() {
		var scope string
		var paths []string
		if e := rows.Scan(&scope, &paths); e != nil {
			return nil, e
		}
		if dir := longestLiteralPrefix(paths); dir != "" {
			dirs[scope] = dir
		}
	}
	return dirs, rows.Err()
}

// longestLiteralPrefix picks the most specific literal directory a node's own
// globs name: the same rule internal/importer/domain.ScopeOf applies to match
// a path against a node, run in reverse to place a new file inside one.
// Duplicated rather than imported -- see the dry-without-wrong-abstraction
// skill -- because importing internal/importer/domain here for three lines of
// string-splitting would add a cross-module Go dependency this package does
// not otherwise have, for logic small and stable enough that drift between
// the two copies is not a realistic risk.
func longestLiteralPrefix(globs []string) string {
	best := ""
	for _, g := range globs {
		prefix := g
		if i := strings.IndexAny(g, "*?["); i >= 0 {
			prefix = g[:i]
		}
		prefix = strings.TrimSuffix(prefix, "/")
		if len(prefix) > len(best) {
			best = prefix
		}
	}
	return best
}

func (w *GenerateWorker) importCommit(ctx context.Context, orgID, importID string) (string, error) {
	if importID == "" {
		return "", nil
	}
	var commit *string
	e := w.pool.QueryRow(ctx, `SELECT commit FROM gfm.imports
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, orgID, importID).Scan(&commit)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", nil
	}
	if e != nil {
		return "", e
	}
	return str(commit), nil
}

// store writes one group's candidates. The whole group is one transaction,
// fenced by the job's generation: a worker whose lease has moved on writes
// nothing at all.
func (w *GenerateWorker) store(ctx context.Context, t *worker.Task, payload generatePayload,
	group Group, req generator.Request, out generator.Output) (int, int, error) {
	if len(out.Candidates) == 0 {
		return 0, 0, nil
	}
	digests := generator.InputDigests(req)
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return 0, 0, fmt.Errorf("open proposal transaction: %w", e)
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return 0, 0, e
	}
	created, skipped := 0, 0
	for _, c := range out.Candidates {
		key := generator.CacheKey(payload.OrgID, payload.Kind, digests, w.recipe, c.Identity)
		contentSHA := digest(c.Body)
		if _, e := w.blobs.Put(ctx, payload.OrgID, contentSHA, []byte(c.Body)); e != nil {
			return 0, 0, fmt.Errorf("store candidate body: %w", e)
		}
		expected := ""
		if c.TargetSkillID != "" {
			expected, e = currentRevision(ctx, tx, payload.OrgID, payload.RepoID, c.TargetSkillID)
			if e != nil {
				return 0, 0, e
			}
		}
		id, isNew, e := insertCandidate(ctx, tx, payload.OrgID, payload.RepoID, payload.ImportID,
			t.Job.JobID, payload.Kind, w.recipe, key, c, contentSHA, contentSHA, expected)
		if e != nil {
			return 0, 0, fmt.Errorf("store candidate %s: %w", c.Slug, e)
		}
		if !isNew {
			skipped++
			continue
		}
		created++
		if e := mgmt.Audit(ctx, tx, payload.OrgID, "worker", "proposal.create", "proposal:"+id,
			key, t.Job.JobID); e != nil {
			return 0, 0, e
		}
	}
	if e := tx.Commit(ctx); e != nil {
		return 0, 0, fmt.Errorf("commit proposals of %s: %w", group.GroupID, e)
	}
	return created, skipped, nil
}

// fence refuses to write when the job's generation has moved. The queue bumps
// the generation on every lease and on cancellation, so a worker that lost its
// lease writes nothing.
func fence(ctx context.Context, tx pgx.Tx, t *worker.Task) error {
	var ok bool
	e := tx.QueryRow(ctx, `SELECT true FROM gfm.jobs
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased' FOR UPDATE`,
		t.Job.JobID, t.Job.Generation).Scan(&ok)
	if errors.Is(e, pgx.ErrNoRows) {
		return jobs.ErrFenced
	}
	if e != nil {
		return fmt.Errorf("check job fence: %w", e)
	}
	return nil
}
