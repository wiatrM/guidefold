package knowledge

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// facetColumns maps the four filter names the contract exposes to the columns
// that hold them. The two layer axes are deliberately separate: `layer` is the
// source's own org/platform/team label, while the knowledge layer is a
// classification and has its own map endpoint (API-CONTRACT §5.3).
var facetColumns = map[string]string{
	"scope":  "scope",
	"owner":  "owner",
	"layer":  "source_layer",
	"status": "source_status",
}

// maxPage bounds one page of skills.
const maxPage = 100

// skillSummary is the `SkillSummary` DTO.
type skillSummary struct {
	SkillID           string     `json:"skill_id"`
	Name              string     `json:"name"`
	Description       string     `json:"description"`
	Scope             string     `json:"scope"`
	Owner             *string    `json:"owner"`
	SourceLayer       *string    `json:"source_layer"`
	KnowledgeLayer    string     `json:"knowledge_layer"`
	SourceStatus      string     `json:"source_status"`
	PublicationStatus string     `json:"publication_status"`
	Path              string     `json:"path"`
	ContentSHA256     *string    `json:"content_sha256"`
	RevisionID        *string    `json:"revision_id"`
	CardRevision      *string    `json:"card_revision"`
	PackageDigest     *string    `json:"package_digest"`
	Commit            *string    `json:"commit"`
	UpdatedAt         *time.Time `json:"updated_at"`
}

const summaryColumns = `s.skill_id,s.name,s.description,s.scope,s.owner,s.source_layer,
 s.knowledge_layer,s.source_status,s.publication_status,s.path,
 r.content_sha256,s.current_revision_id,r.card_revision,r.commit,s.updated_at`

const summaryFrom = ` FROM gfm.skills s
 LEFT JOIN gfm.skill_revisions r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id`

func scanSummary(rows pgx.Rows) (skillSummary, error) {
	var v skillSummary
	e := rows.Scan(&v.SkillID, &v.Name, &v.Description, &v.Scope, &v.Owner, &v.SourceLayer,
		&v.KnowledgeLayer, &v.SourceStatus, &v.PublicationStatus, &v.Path,
		&v.ContentSHA256, &v.RevisionID, &v.CardRevision, &v.Commit, &v.UpdatedAt)
	return v, e
}

// handleListSkills answers one keyset page of skill summaries.
//
// The page echoes every filter it was given, with whether that value exists in
// this repository at all. A filter the catalog does not recognise returns an
// empty page and `available:false` rather than silently falling back to "All",
// which would show the reader a list that answers a different question
// (API-CONTRACT §3).
func (s *Service) handleListSkills(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	limit := 50
	if v := c.Query("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > maxPage {
			return mgmt.Invalid("invalid_request", "limit must be between 1 and 100.")
		}
		limit = n
	}
	afterName, afterID := "", ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 2)
		if err != nil {
			return err
		}
		afterName, afterID = parts[0], parts[1]
	}
	q := strings.TrimSpace(c.Query("q"))
	if len(q) > 200 {
		return mgmt.Invalid("invalid_request", "q must be at most 200 characters.")
	}
	scope, owner, layer, status := c.Query("scope"), c.Query("owner"), c.Query("layer"), c.Query("status")

	rows, err := s.pool.Query(c.Ctx(), `SELECT `+summaryColumns+summaryFrom+`
 WHERE s.org_id=$1::uuid AND s.repo_id=$2
   AND ($3='' OR s.scope=$3)
   AND ($4='' OR s.owner=$4)
   AND ($5='' OR s.source_layer=$5)
   AND ($6='' OR s.source_status=$6)
   AND ($7='' OR s.name ILIKE '%'||$7||'%' ESCAPE '\'
     OR s.description ILIKE '%'||$7||'%' ESCAPE '\'
     OR s.path ILIKE '%'||$7||'%' ESCAPE '\')
   AND ($8='' OR (s.name,s.skill_id) > ($8,$9))
 ORDER BY s.name,s.skill_id LIMIT $10`,
		org.ID, repo.ID, scope, owner, layer, status, likeEscape(q), afterName, afterID, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []skillSummary{}
	for rows.Next() {
		v, e := scanSummary(rows)
		if e != nil {
			return mgmt.Internal(e)
		}
		items = append(items, v)
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	next := ""
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		next = mgmt.EncodeCursor(last.Name, last.SkillID)
	}

	filters := map[string]any{}
	for field, value := range map[string]string{
		"scope": scope, "owner": owner, "layer": layer, "status": status} {
		if value == "" {
			continue
		}
		available, e := s.facetExists(c.Ctx(), org.ID, repo.ID, field, value)
		if e != nil {
			return mgmt.Internal(e)
		}
		filters[field] = map[string]any{"value": value, "available": available}
	}
	if q != "" {
		filters["q"] = map[string]any{"value": q, "available": len(items) > 0}
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "repo_id": repo.ID,
		"items": items, "next_cursor": nullable(next), "snapshot_id": nil,
		"filters": filters})
}

// likeEscape neutralises the wildcards a person typed, so a search for "100%"
// is a search for that text and not for everything.
func likeEscape(q string) string {
	r := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`)
	return r.Replace(q)
}

func (s *Service) facetExists(ctx context.Context, orgID, repoID, field, value string) (bool, error) {
	column, ok := facetColumns[field]
	if !ok {
		return false, nil
	}
	var exists bool
	e := s.pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND `+column+`=$3)`, orgID, repoID, value).Scan(&exists)
	return exists, e
}

// handleFacets counts the distinct values of one filter field.
func (s *Service) handleFacets(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	field := c.Query("field")
	column, ok := facetColumns[field]
	if !ok {
		return mgmt.Invalid("invalid_request", "field must be one of scope, owner, layer, status.")
	}
	after := ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 1)
		if err != nil {
			return err
		}
		after = parts[0]
	}
	const limit = 200
	rows, err := s.pool.Query(c.Ctx(), `SELECT `+column+` AS value,count(*)
 FROM gfm.skills WHERE org_id=$1::uuid AND repo_id=$2 AND `+column+` IS NOT NULL AND `+column+`<>''
   AND ($3='' OR `+column+` ILIKE '%'||$3||'%' ESCAPE '\')
   AND ($4='' OR `+column+` > $4)
 GROUP BY 1 ORDER BY 1 LIMIT $5`,
		org.ID, repo.ID, likeEscape(strings.TrimSpace(c.Query("q"))), after, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	values := []map[string]any{}
	for rows.Next() {
		var value string
		var count int
		if err = rows.Scan(&value, &count); err != nil {
			return mgmt.Internal(err)
		}
		values = append(values, map[string]any{"value": value, "count": count})
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	next := ""
	if len(values) > limit {
		values = values[:limit]
		next = mgmt.EncodeCursor(values[len(values)-1]["value"].(string))
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "field": field,
		"values": values, "next_cursor": nullable(next)})
}

// handleFacetLookup answers for one value, so a filter taken from a URL stays
// visible even when it is not on the current page of facet values — and so an
// unknown value is reported as unavailable rather than dropped.
func (s *Service) handleFacetLookup(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	field := c.Query("field")
	column, ok := facetColumns[field]
	if !ok {
		return mgmt.Invalid("invalid_request", "field must be one of scope, owner, layer, status.")
	}
	value := c.Query("value")
	if value == "" {
		return mgmt.Invalid("invalid_request", "value is required.")
	}
	var count int
	if err := s.pool.QueryRow(c.Ctx(), `SELECT count(*) FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND `+column+`=$3`, org.ID, repo.ID, value).Scan(&count); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "field": field, "value": value,
		"count": count, "available": count > 0})
}

// handleSkill answers one skill and every revision the catalog holds for it.
func (s *Service) handleSkill(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	skillID := c.Param("skill_id")
	rows, err := s.pool.Query(c.Ctx(), `SELECT `+summaryColumns+summaryFrom+`
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.skill_id=$3`, org.ID, repo.ID, skillID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	if !rows.Next() {
		if err = rows.Err(); err != nil {
			return mgmt.Internal(err)
		}
		return mgmt.NotFound("skill_not_found", "No such skill in this repository.")
	}
	summary, err := scanSummary(rows)
	if err != nil {
		return mgmt.Internal(err)
	}
	rows.Close()

	revisions, err := s.revisionRefs(c.Ctx(), org.ID, skillID)
	if err != nil {
		return mgmt.Internal(err)
	}
	body := map[string]any{"schema_version": mgmt.SchemaVersion, "org_id": org.ID,
		"repo_id": repo.ID, "revisions": revisions}
	mergeSummary(body, summary)
	return c.JSON(http.StatusOK, body)
}

// revisionRef is the `RevisionRef` DTO.
type revisionRef struct {
	RevisionID    string     `json:"revision_id"`
	ContentSHA256 string     `json:"content_sha256"`
	CardRevision  *string    `json:"card_revision"`
	Commit        *string    `json:"commit"`
	ImportID      *string    `json:"import_id"`
	CreatedAt     *time.Time `json:"created_at"`
	Source        string     `json:"source"`
}

func (s *Service) revisionRefs(ctx context.Context, orgID, skillID string) ([]revisionRef, error) {
	rows, e := s.pool.Query(ctx, `SELECT revision_id,content_sha256,card_revision,commit,import_id::text,created_at,
 CASE WHEN proposal_id IS NULL THEN 'import' ELSE 'proposal' END
 FROM gfm.skill_revisions WHERE org_id=$1::uuid AND skill_id=$2
 ORDER BY created_at DESC,revision_id DESC LIMIT 200`, orgID, skillID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []revisionRef{}
	for rows.Next() {
		var v revisionRef
		if e = rows.Scan(&v.RevisionID, &v.ContentSHA256, &v.CardRevision, &v.Commit, &v.ImportID,
			&v.CreatedAt, &v.Source); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// mergeSummary flattens a summary into the response object, because SkillDetail
// is a SkillSummary plus revisions rather than a summary nested inside it.
func mergeSummary(into map[string]any, v skillSummary) {
	into["skill_id"] = v.SkillID
	into["name"] = v.Name
	into["description"] = v.Description
	into["scope"] = v.Scope
	into["owner"] = v.Owner
	into["source_layer"] = v.SourceLayer
	into["knowledge_layer"] = v.KnowledgeLayer
	into["source_status"] = v.SourceStatus
	into["publication_status"] = v.PublicationStatus
	into["path"] = v.Path
	into["content_sha256"] = v.ContentSHA256
	into["revision_id"] = v.RevisionID
	into["card_revision"] = v.CardRevision
	into["package_digest"] = v.PackageDigest
	into["commit"] = v.Commit
	into["updated_at"] = v.UpdatedAt
}

// revisionRow is one immutable revision as stored.
type revisionRow struct {
	RevisionID    string
	SkillID       string
	ContentSHA256 string
	// CardRevision is the identifier the delivery path and adapter telemetry
	// use for this revision, or "" while it has never entered a snapshot.
	CardRevision string
	BlobSHA256   string
	Frontmatter  string
	Commit       string
	ImportID     string
	ProposalID   string
	Origin       string
	SourcePath   string
	CreatedAt    time.Time
	Publication  string
}

// loadRevision reads one revision of one skill.
//
// The skill and the revision are matched together on purpose: asking for a
// revision that belongs to a different skill is 404, and a revision that no
// longer exists is 404 as well. Substituting the newest revision would hand the
// caller bytes they did not ask for (§9, "Rewizja niedostępna to 404").
func (s *Service) loadRevision(ctx context.Context, orgID, repoID, skillID, revisionID string) (*revisionRow, error) {
	var v revisionRow
	var commit, importID, proposalID, cardRevision *string
	e := s.pool.QueryRow(ctx, `SELECT r.revision_id,r.skill_id,r.content_sha256,r.card_revision,r.blob_sha256,
 r.frontmatter::text,r.commit,r.import_id::text,r.proposal_id::text,r.origin,r.source_path,
 r.created_at,s.publication_status
 FROM gfm.skill_revisions r JOIN gfm.skills s ON s.org_id=r.org_id AND s.skill_id=r.skill_id
 WHERE r.org_id=$1::uuid AND s.repo_id=$2 AND r.skill_id=$3 AND r.revision_id=$4`,
		orgID, repoID, skillID, revisionID).
		Scan(&v.RevisionID, &v.SkillID, &v.ContentSHA256, &cardRevision, &v.BlobSHA256, &v.Frontmatter,
			&commit, &importID, &proposalID, &v.Origin, &v.SourcePath, &v.CreatedAt, &v.Publication)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, mgmt.NotFound("revision_not_found", "No such revision of this skill.")
	}
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	v.Commit, v.ImportID, v.ProposalID = str(commit), str(importID), str(proposalID)
	v.CardRevision = str(cardRevision)
	return &v, nil
}
