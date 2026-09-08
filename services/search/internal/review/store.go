package review

import (
	"context"
	"encoding/json"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// proposal is one row of gfm.proposals plus the decoded columns the handlers
// use. Reading it is deliberately one query: a proposal is the unit an owner
// decides on, so its state, its candidate and its provenance must be read
// consistently rather than assembled from three round trips.
type proposal struct {
	ProposalID          string
	RepoID              string
	ImportID            string
	JobID               string
	Kind                string
	State               string
	Scope               string
	Owner               string
	TargetSkillID       string
	TargetRevisionID    string
	ExpectedRevision    string
	CandidatePath       string
	CandidateSHA256     string
	CandidateBlobSHA256 string
	CandidateFrontmater json.RawMessage
	Sources             json.RawMessage
	RecipeVersion       string
	Generator           string
	Model               string
	CacheKey            string
	Cost                json.RawMessage
	CreatedAt           time.Time
	UpdatedAt           time.Time
}

const proposalColumns = `proposal_id::text,repo_id,import_id::text,job_id::text,kind,state,scope,owner,
 target_skill_id,target_revision_id,expected_revision,candidate_path,candidate_sha256,
 candidate_blob_sha256,candidate_frontmatter::text,sources::text,recipe_version,generator,model,
 cache_key,cost::text,created_at,updated_at`

func scanProposal(row pgx.Row) (*proposal, error) {
	var p proposal
	var importID, jobID, scope, owner, target, targetRev, expected, model, cost *string
	var frontmatter, sources string
	e := row.Scan(&p.ProposalID, &p.RepoID, &importID, &jobID, &p.Kind, &p.State, &scope, &owner,
		&target, &targetRev, &expected, &p.CandidatePath, &p.CandidateSHA256,
		&p.CandidateBlobSHA256, &frontmatter, &sources, &p.RecipeVersion, &p.Generator, &model,
		&p.CacheKey, &cost, &p.CreatedAt, &p.UpdatedAt)
	if e != nil {
		return nil, e
	}
	p.ImportID, p.JobID = str(importID), str(jobID)
	p.Scope, p.Owner = str(scope), str(owner)
	p.TargetSkillID, p.TargetRevisionID, p.ExpectedRevision = str(target), str(targetRev), str(expected)
	p.Model = str(model)
	p.CandidateFrontmater = json.RawMessage(frontmatter)
	p.Sources = json.RawMessage(sources)
	if cost != nil {
		p.Cost = json.RawMessage(*cost)
	}
	return &p, nil
}

// loadProposal reads one proposal of one repository. A proposal of another
// repository in the same organisation is 404, not a cross-repository read.
func (s *Service) loadProposal(ctx context.Context, orgID, repoID, proposalID string) (*proposal, error) {
	return scanProposal(s.pool.QueryRow(ctx, `SELECT `+proposalColumns+` FROM gfm.proposals
 WHERE org_id=$1::uuid AND repo_id=$2 AND proposal_id=$3::uuid`, orgID, repoID, proposalID))
}

// lockProposal reads it inside a transaction, so a decision and the state it
// depends on cannot interleave with a second decision.
func lockProposal(ctx context.Context, tx pgx.Tx, orgID, repoID, proposalID string) (*proposal, error) {
	return scanProposal(tx.QueryRow(ctx, `SELECT `+proposalColumns+` FROM gfm.proposals
 WHERE org_id=$1::uuid AND repo_id=$2 AND proposal_id=$3::uuid FOR UPDATE`,
		orgID, repoID, proposalID))
}

// field is one row of gfm.proposal_fields.
type field struct {
	Field             string  `json:"field"`
	Origin            string  `json:"origin"`
	SourcePath        *string `json:"-"`
	SourceSHA256      *string `json:"-"`
	LineFrom          *int    `json:"-"`
	LineTo            *int    `json:"-"`
	NeedsConfirmation bool    `json:"needs_confirmation"`
	ValueSHA256       *string `json:"value_sha256"`
}

// sourceRef renders the provenance entry the ProposalDetail DTO carries. A
// field with no reference answers `null` and `needs_confirmation: true`, which
// is a named absence rather than an empty object pretending to be evidence.
func (f field) sourceRef() any {
	if f.SourcePath == nil {
		return nil
	}
	out := map[string]any{"path": *f.SourcePath}
	if f.SourceSHA256 != nil {
		out["sha256"] = *f.SourceSHA256
	}
	if f.LineFrom != nil {
		out["line_from"] = *f.LineFrom
	}
	if f.LineTo != nil {
		out["line_to"] = *f.LineTo
	}
	return out
}

func (s *Service) proposalFields(ctx context.Context, orgID, proposalID string) ([]field, error) {
	rows, e := s.pool.Query(ctx, `SELECT field,origin,source_path,source_sha256,line_from,line_to,
 needs_confirmation,value_sha256 FROM gfm.proposal_fields
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid ORDER BY field`, orgID, proposalID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []field{}
	for rows.Next() {
		var f field
		if e = rows.Scan(&f.Field, &f.Origin, &f.SourcePath, &f.SourceSHA256, &f.LineFrom,
			&f.LineTo, &f.NeedsConfirmation, &f.ValueSHA256); e != nil {
			return nil, e
		}
		out = append(out, f)
	}
	return out, rows.Err()
}

// relation is one authored edge of a proposal's candidate.
//
// `to` is the far end of an edge that leaves the candidate; `from` is the far
// end of one that arrives at it. Exactly one of the two is set, and a reviewer
// has to be able to tell them apart: "this shared element was derived from your
// runbook" and "your runbook refines this shared element" are two different
// claims about the same pair.
type relation struct {
	Type string  `json:"type"`
	To   string  `json:"to"`
	From *string `json:"from"`
}

func (s *Service) proposalRelations(ctx context.Context, orgID, proposalID string) ([]relation, error) {
	rows, e := s.pool.Query(ctx, `SELECT type,from_skill_id,to_skill_id FROM gfm.relations
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid ORDER BY type,from_skill_id,to_skill_id`,
		orgID, proposalID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	placeholder := "proposal:" + proposalID
	out := []relation{}
	for rows.Next() {
		var r relation
		var from, to string
		if e = rows.Scan(&r.Type, &from, &to); e != nil {
			return nil, e
		}
		if from == placeholder {
			r.To = to
		} else {
			source := from
			r.From, r.To = &source, ""
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// decisionRow is one row of gfm.decisions.
type decisionRow struct {
	DecisionID       string    `json:"decision_id"`
	Decision         string    `json:"decision"`
	Reason           string    `json:"reason"`
	ActorUserID      string    `json:"actor_user_id"`
	ExpectedRevision *string   `json:"expected_revision"`
	ResultRevisionID *string   `json:"result_revision_id"`
	At               time.Time `json:"at"`
}

func (s *Service) lastDecision(ctx context.Context, orgID, proposalID string) (*decisionRow, error) {
	var d decisionRow
	e := s.pool.QueryRow(ctx, `SELECT decision_id::text,decision,reason,actor_user_id::text,
 expected_revision,result_revision_id,at FROM gfm.decisions
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid ORDER BY at DESC LIMIT 1`, orgID, proposalID).
		Scan(&d.DecisionID, &d.Decision, &d.Reason, &d.ActorUserID, &d.ExpectedRevision,
			&d.ResultRevisionID, &d.At)
	if isNoRows(e) {
		return nil, nil
	}
	if e != nil {
		return nil, e
	}
	return &d, nil
}

// insertCandidate writes one generated candidate and its provenance inside the
// worker's transaction.
//
// The cache key carries the whole dedupe rule (API-CONTRACT §8): the unique
// index means a second run over the same bytes with the same recipe collides
// with the row that already exists, whatever its state, so a candidate an owner
// rejected is never offered again and a restarted job never doubles its output.
func insertCandidate(ctx context.Context, tx pgx.Tx, orgID, repoID, importID, jobID string,
	kind string, recipe generator.Recipe, cacheKey string, c generator.Candidate,
	blobSHA, contentSHA, expectedRevision string) (string, bool, error) {
	proposalID := newID()
	frontmatter := mustJSON(c.Frontmatter)
	sources := mustJSON(c.Sources)
	var stored string
	e := tx.QueryRow(ctx, `INSERT INTO gfm.proposals
 (org_id,proposal_id,repo_id,import_id,job_id,kind,state,scope,owner,target_skill_id,
  expected_revision,candidate_path,candidate_sha256,candidate_blob_sha256,candidate_frontmatter,
  sources,recipe_version,generator,model,cache_key)
 VALUES($1::uuid,$2::uuid,$3,$4::uuid,$5::uuid,$6,'draft',$7,$8,$9,$10,$11,$12,$13,$14::jsonb,
  $15::jsonb,$16,$17,$18,$19)
 ON CONFLICT (org_id,cache_key) DO NOTHING
 RETURNING proposal_id::text`,
		orgID, proposalID, repoID, nullable(importID), nullable(jobID), kind,
		nullable(c.Scope), nullable(c.Owner), nullable(c.TargetSkillID), nullable(expectedRevision),
		c.Path, contentSHA, blobSHA, string(frontmatter), string(sources),
		recipe.Version, recipe.Generator, nullable(recipe.Model), cacheKey).Scan(&stored)
	if isNoRows(e) {
		// The key is already taken: an earlier attempt of this job, or a run the
		// owner has already decided on. Either way, nothing new is produced.
		return "", false, nil
	}
	if e != nil {
		return "", false, e
	}
	for _, f := range c.Fields {
		var path, sha *string
		var from, to *int
		if f.Ref != nil {
			path, sha = optional(f.Ref.Path), optional(f.Ref.SHA256)
			lineFrom, lineTo := f.Ref.LineFrom, f.Ref.LineTo
			from, to = &lineFrom, &lineTo
		}
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.proposal_fields
 (org_id,proposal_id,field,origin,source_path,source_sha256,line_from,line_to,
  needs_confirmation,value_sha256)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9,$10)
 ON CONFLICT (org_id,proposal_id,field) DO UPDATE SET
  origin=EXCLUDED.origin,source_path=EXCLUDED.source_path,source_sha256=EXCLUDED.source_sha256,
  line_from=EXCLUDED.line_from,line_to=EXCLUDED.line_to,
  needs_confirmation=EXCLUDED.needs_confirmation,value_sha256=EXCLUDED.value_sha256`,
			orgID, stored, f.Field, f.Origin, path, sha, from, to, f.NeedsConfirmation,
			optional(digest(f.Value))); e != nil {
			return "", false, e
		}
	}
	// A candidate edge is stored against the proposal, with the candidate itself
	// standing in as `proposal:<id>` until approval gives it a skill id. Most
	// edges leave the candidate; a consolidation also proposes edges that *end*
	// at it — each source skill refines the shared element — and those carry the
	// existing skill in `From` (API-CONTRACT §5.4, `relations[].from`).
	for _, r := range c.Relations {
		from, to := "proposal:"+stored, r.To
		if r.From != "" {
			from, to = r.From, "proposal:"+stored
		}
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.relations
 (org_id,relation_id,from_skill_id,to_skill_id,type,provenance,proposal_id)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'proposal',$6::uuid)
 ON CONFLICT (org_id,from_skill_id,to_skill_id,type,revision_id) DO NOTHING`,
			orgID, newID(), from, to, r.Type, stored); e != nil {
			return "", false, e
		}
	}
	return stored, true, nil
}
