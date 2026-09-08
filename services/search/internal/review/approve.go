package review

import (
	"context"
	"encoding/json"
	"reflect"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"gopkg.in/yaml.v3"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// pgxTx is the subset of a transaction the decision path uses.
type pgxTx interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// currentRevision reads the revision a proposal's target skill is on right now,
// or "" when the proposal creates a new skill.
func currentRevision(ctx context.Context, tx pgxTx, orgID, repoID, skillID string) (string, error) {
	if skillID == "" {
		return "", nil
	}
	var revision *string
	e := tx.QueryRow(ctx, `SELECT current_revision_id FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=$3`, orgID, repoID, skillID).Scan(&revision)
	if isNoRows(e) {
		return "", nil
	}
	if e != nil {
		return "", e
	}
	return str(revision), nil
}

// frontmatterOf reads the YAML block of a SKILL.md. A body without one is not a
// skill package, and an edit may not turn one into the other.
func frontmatterOf(body string) (map[string]any, string, error) {
	if !strings.HasPrefix(body, "---\n") {
		return nil, "", mgmt.Unprocessable("invalid_candidate_change",
			"The candidate body must start with a YAML frontmatter block.")
	}
	rest := body[4:]
	end := strings.Index(rest, "\n---")
	if end < 0 {
		return nil, "", mgmt.Unprocessable("invalid_candidate_change",
			"The candidate body's frontmatter block is not closed.")
	}
	var parsed map[string]any
	if e := yaml.Unmarshal([]byte(rest[:end]), &parsed); e != nil {
		return nil, "", mgmt.Unprocessable("invalid_candidate_change",
			"The candidate body's frontmatter is not valid YAML.")
	}
	if parsed == nil {
		parsed = map[string]any{}
	}
	return parsed, rest[end:], nil
}

// identityFields are the frontmatter keys an edit may not touch. They are what
// the graph, the scope policy and the URN are derived from: changing them in a
// review would move a candidate into someone else's scope, or rewire the graph,
// without either owner agreeing (API-CONTRACT §4.4, `invalid_candidate_change`).
var identityFields = []string{"name", "scope", "owner", "layer", "requires", "refines",
	"replaces", "derived_from", "similar", "conflicts_with", "status", "kind"}

// sameIdentity reports whether an edited body keeps the candidate's identity.
// Prose, steps and descriptions are the reviewer's to change; identity is not.
func sameIdentity(original, edited string) error {
	before, _, e := frontmatterOf(original)
	if e != nil {
		return e
	}
	after, _, e := frontmatterOf(edited)
	if e != nil {
		return e
	}
	beforeMeta, afterMeta := metadataOf(before), metadataOf(after)
	changed := []string{}
	for _, key := range identityFields {
		if !reflect.DeepEqual(canonicalValue(before[key]), canonicalValue(after[key])) {
			changed = append(changed, key)
		}
		if !reflect.DeepEqual(canonicalValue(beforeMeta[key]), canonicalValue(afterMeta[key])) {
			changed = append(changed, "metadata."+key)
		}
	}
	// A new top-level or metadata key is a change of identity too: it is how a
	// relation or a scope would be smuggled in.
	for key := range after {
		if _, ok := before[key]; !ok {
			changed = append(changed, key)
		}
	}
	for key := range afterMeta {
		if _, ok := beforeMeta[key]; !ok {
			changed = append(changed, "metadata."+key)
		}
	}
	if len(changed) == 0 {
		return nil
	}
	return mgmt.Unprocessable("invalid_candidate_change",
		"An edit may change the body, not the frontmatter, scope, owner or relations.").
		WithDetails(map[string]any{"changed": unique(changed)})
}

func metadataOf(fm map[string]any) map[string]any {
	out, _ := fm["metadata"].(map[string]any)
	if out == nil {
		return map[string]any{}
	}
	return out
}

// canonicalValue makes two YAML shapes of the same value compare equal: a
// one-item list and a scalar, a comma-separated string and a sequence.
func canonicalValue(v any) any {
	switch value := v.(type) {
	case nil:
		return nil
	case []any:
		out := make([]string, 0, len(value))
		for _, item := range value {
			out = append(out, strings.TrimSpace(scalar(item)))
		}
		return out
	case string:
		if strings.Contains(value, ",") {
			parts := strings.Split(value, ",")
			out := make([]string, 0, len(parts))
			for _, p := range parts {
				if p = strings.TrimSpace(p); p != "" {
					out = append(out, p)
				}
			}
			return out
		}
		return strings.TrimSpace(value)
	default:
		return scalar(v)
	}
}

func scalar(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	raw, _ := json.Marshal(v)
	return string(raw)
}

func unique(list []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, v := range list {
		if !seen[v] {
			seen[v] = true
			out = append(out, v)
		}
	}
	return out
}

// resolveSkillID decides which skill an approved candidate belongs to: the one
// it targets, or a new identity for a new package.
//
// A new URN follows the same shape as an imported one, `urn:skill:<publisher>:
// <node>:<name>`, with the publisher taken from a skill this repository already
// has rather than from a hard-coded organisation name (CLAUDE.md, "Naming").
func (s *Service) resolveSkillID(c *mgmt.Context, tx pgxTx, rc *repoContext, p *proposal) (string, error) {
	if p.TargetSkillID != "" {
		return p.TargetSkillID, nil
	}
	var sample string
	e := tx.QueryRow(c.Ctx(), `SELECT skill_id FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id LIKE 'urn:skill:%'
 ORDER BY skill_id LIMIT 1`, rc.Org.ID, rc.RepoID).Scan(&sample)
	publisher := rc.RepoID
	if e == nil {
		if parts := strings.Split(sample, ":"); len(parts) >= 3 {
			publisher = parts[2]
		}
	} else if !isNoRows(e) {
		return "", mgmt.Internal(e)
	}
	node := p.Scope
	if node == "" {
		node = "_root"
	}
	name := candidateName(p.CandidatePath)
	return "urn:skill:" + publisher + ":" + node + ":" + name, nil
}

func candidateName(path string) string {
	trimmed := strings.TrimSuffix(path, "/SKILL.md")
	if i := strings.LastIndex(trimmed, "/"); i >= 0 {
		return trimmed[i+1:]
	}
	return trimmed
}

// writeHumanRevision stores the approved bytes as an immutable revision with
// `origin: human`, and creates the skill row when the candidate is a new
// package.
//
// The new skill's `publication_status` stays `draft`: approving a candidate
// does not put it in front of an agent. It becomes `published` only when its
// file has landed in git and a later import has carried it into a snapshot
// (PRODUCT-PIVOT U2.6).
func (s *Service) writeHumanRevision(c *mgmt.Context, tx pgxTx, rc *repoContext, p *proposal,
	skillID, body string) (string, error) {
	contentSHA := digest(body)
	if _, e := s.blobs.Put(c.Ctx(), rc.Org.ID, contentSHA, []byte(body)); e != nil {
		return "", mgmt.Internal(e)
	}
	frontmatter, _, e := frontmatterOf(body)
	if e != nil {
		return "", e
	}
	revisionID := digest(skillID + "@" + contentSHA)
	meta := metadataOf(frontmatter)
	scope := p.Scope
	if v := scalar(meta["scope"]); v != "" {
		scope = v
	}
	if scope == "" {
		scope = "_root"
	}
	owner := p.Owner
	if v := scalar(meta["owner"]); v != "" {
		owner = v
	}
	name := scalar(frontmatter["name"])
	if name == "" {
		name = candidateName(p.CandidatePath)
	}
	// The knowledge layer the owner is approving. The generator only ever infers
	// it; whatever the approved body carries is what the catalog gets, and if the
	// owner changed it the field's origin becomes `human` (P08, API-CONTRACT §4.4).
	layer := scalar(meta[generator.FieldKnowledgeLayer])
	if !generator.KnownLayer(layer) {
		layer = generator.LayerUnclassified
	}
	// The skill row is created only for a new package, and never overwrites the
	// catalog's own view of an existing one: enrichment adds a revision, it does
	// not re-parent a skill.
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.skills
 (org_id,skill_id,repo_id,name,description,scope,owner,path,knowledge_layer,source_status,publication_status)
 VALUES($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,'active','draft')
 ON CONFLICT (org_id,skill_id) DO NOTHING`,
		rc.Org.ID, skillID, rc.RepoID, name, scalar(frontmatter["description"]), scope,
		nullable(owner), p.CandidatePath, layer); err != nil {
		return "", mgmt.Internal(err)
	}
	// The approved revision becomes the skill's current one, and an existing skill
	// takes the approved layer: the whole point of enriching it was to put it on
	// the pyramid. `unclassified` never overwrites a layer somebody decided on.
	//
	// `current_revision_id` is what makes the approval visible to the rest of the
	// catalog — the generation plan, the scope map and the graph validator all
	// join on it, so without this a shared element could never itself become the
	// input of anything, and a newly approved package would look revision-less.
	// It does **not** publish: `publication_status` stays `draft`, and the
	// publication job only ever moves skills whose file is in the imported tree
	// (`markPublished`), so nothing an owner approved is served before it lands
	// in git (PRODUCT-PIVOT U2.6).
	if _, err := tx.Exec(c.Ctx(), `UPDATE gfm.skills
 SET current_revision_id=$3,knowledge_layer=CASE WHEN $4='' THEN knowledge_layer ELSE $4 END,
     updated_at=now()
 WHERE org_id=$1::uuid AND skill_id=$2`, rc.Org.ID, skillID, revisionID,
		layerOrEmpty(layer)); err != nil {
		return "", mgmt.Internal(err)
	}
	if err := recordLayerOverride(c, tx, rc, p, layer); err != nil {
		return "", err
	}
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.skill_revisions
 (org_id,revision_id,skill_id,content_sha256,blob_sha256,frontmatter,import_id,proposal_id,
  origin,source_path)
 VALUES($1::uuid,$2,$3,$4,$4,$5::jsonb,$6::uuid,$7::uuid,'human',$8)
 ON CONFLICT (org_id,revision_id) DO NOTHING`,
		rc.Org.ID, revisionID, skillID, contentSHA, string(mustJSON(frontmatter)),
		nullable(p.ImportID), p.ProposalID, p.CandidatePath); err != nil {
		return "", mgmt.Internal(err)
	}
	// The proposal's relations become the candidate revision's relations, so the
	// graph validator and the map see the same edges the reviewer approved.
	//
	// An edge that arrives at the candidate keeps its own source: `refines` from
	// a runbook up to the shared element belongs to the runbook, and is carried
	// on the runbook's current revision, not on the shared element's. Storing it
	// the other way round would make the map claim the abstraction refines its
	// own children.
	placeholder := "proposal:" + p.ProposalID
	rows, err := tx.Query(c.Ctx(), `SELECT type,from_skill_id,to_skill_id FROM gfm.relations
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, rc.Org.ID, p.ProposalID)
	if err != nil {
		return "", mgmt.Internal(err)
	}
	edges := [][3]string{}
	for rows.Next() {
		var kind, from, to string
		if err = rows.Scan(&kind, &from, &to); err != nil {
			rows.Close()
			return "", mgmt.Internal(err)
		}
		edges = append(edges, [3]string{kind, from, to})
	}
	rows.Close()
	if err = rows.Err(); err != nil {
		return "", mgmt.Internal(err)
	}
	for _, edge := range edges {
		from, to, revision := skillID, edge[2], revisionID
		if edge[1] != placeholder {
			from, to = edge[1], skillID
			revision, err = currentRevision(c.Ctx(), tx, rc.Org.ID, rc.RepoID, from)
			if err != nil {
				return "", mgmt.Internal(err)
			}
		}
		if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.relations
 (org_id,relation_id,from_skill_id,to_skill_id,type,provenance,revision_id,proposal_id)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'proposal',$6,$7::uuid)
 ON CONFLICT (org_id,from_skill_id,to_skill_id,type,revision_id) DO NOTHING`,
			rc.Org.ID, newID(), from, to, edge[0], nullable(revision), p.ProposalID); err != nil {
			return "", mgmt.Internal(err)
		}
	}
	return revisionID, nil
}

// layerOrEmpty is the value the catalog should take, or "" for "leave it alone".
func layerOrEmpty(layer string) string {
	if layer == generator.LayerUnclassified {
		return ""
	}
	return layer
}

// recordLayerOverride marks the `knowledge_layer` field `human` when the owner
// approved a layer other than the one the generator inferred.
//
// It is the one field an edit may move without changing the candidate's
// identity: which rung of the pyramid an instruction sits on is a judgement, and
// the person who owns the scope is allowed to make it. What may not happen is
// the record still claiming a machine inferred the value (API-CONTRACT §7,
// `gfm.proposal_fields.origin`).
func recordLayerOverride(c *mgmt.Context, tx pgxTx, rc *repoContext, p *proposal, layer string) error {
	var origin string
	var stored *string
	e := tx.QueryRow(c.Ctx(), `SELECT origin,value_sha256 FROM gfm.proposal_fields
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid AND field=$3`,
		rc.Org.ID, p.ProposalID, generator.FieldKnowledgeLayer).Scan(&origin, &stored)
	if isNoRows(e) {
		return nil
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	if origin == generator.OriginHuman || str(stored) == digest(layer) {
		return nil
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposal_fields
 SET origin='human',value_sha256=$4,needs_confirmation=false
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid AND field=$3`,
		rc.Org.ID, p.ProposalID, generator.FieldKnowledgeLayer, digest(layer)); e != nil {
		return mgmt.Internal(e)
	}
	return nil
}
