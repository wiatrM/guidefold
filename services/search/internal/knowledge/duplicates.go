package knowledge

import (
	"net/http"
	"strconv"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// duplicateMember is one skill of a `DuplicateGroup`.
type duplicateMember struct {
	SkillID           string  `json:"skill_id"`
	RepoID            string  `json:"repo_id"`
	Scope             string  `json:"scope"`
	Path              string  `json:"path"`
	ContentSHA256     *string `json:"content_sha256"`
	PublicationStatus string  `json:"publication_status"`
}

// duplicateGroup is the `DuplicateGroup` DTO.
type duplicateGroup struct {
	Name      string            `json:"name"`
	Repos     []string          `json:"repos"`
	Count     int               `json:"count"`
	Identical bool              `json:"identical"`
	Skills    []duplicateMember `json:"skills"`
}

// handleDuplicates answers one keyset page of skill names that appear in at
// least two readable repositories (API-CONTRACT §4.10 item 9).
//
// Name equality is exact on purpose. Similar-but-different instructions are a
// judgement, and judgements are proposals of kind `consolidation`; this read
// only reports what is certainly the same name in more than one place.
func (s *Service) handleDuplicates(c *mgmt.Context) error {
	org, scope, e := c.AuthorizeScope("org", "", mgmt.RoleAny)
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
	var afterCount *int
	afterName := ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 2)
		if err != nil {
			return err
		}
		n, convErr := strconv.Atoi(parts[0])
		if convErr != nil {
			return mgmt.Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
		}
		afterCount, afterName = &n, parts[1]
	}

	// With repo=X the scope is X alone, but X's duplicates live in the other
	// repositories, so the members always come from the full readable set.
	narrowed := ""
	repos := scope.Repos
	if scope.Single() {
		narrowed = scope.Repo.ID
		if repos, e = c.ReadableRepos(org); e != nil {
			return e
		}
	}
	body := map[string]any{"schema_version": mgmt.SchemaVersion, "org_id": org.ID,
		"repo_id": scope.RepoID(), "items": []duplicateGroup{}, "next_cursor": nil}
	if len(repos) < 2 {
		return c.JSON(http.StatusOK, body)
	}

	rows, err := s.pool.Query(c.Ctx(), `SELECT s.name, count(*)::int,
   array_agg(DISTINCT s.repo_id ORDER BY s.repo_id),
   count(DISTINCT r.content_sha256)=1 AND bool_and(r.content_sha256 IS NOT NULL)
 FROM gfm.skills s
 LEFT JOIN gfm.skill_revisions r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id = ANY($2::text[]) AND s.source_status <> 'removed'
 GROUP BY s.name
 HAVING count(DISTINCT s.repo_id) >= 2
   AND ($3='' OR bool_or(s.repo_id=$3))
   AND ($4::int IS NULL OR count(*) < $4::int OR (count(*) = $4::int AND s.name > $5))
 ORDER BY count(*) DESC, s.name LIMIT $6`,
		org.ID, repos, narrowed, afterCount, afterName, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	groups := []duplicateGroup{}
	for rows.Next() {
		g := duplicateGroup{Skills: []duplicateMember{}}
		if err = rows.Scan(&g.Name, &g.Count, &g.Repos, &g.Identical); err != nil {
			return mgmt.Internal(err)
		}
		groups = append(groups, g)
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	rows.Close()
	if len(groups) > limit {
		groups = groups[:limit]
		last := groups[len(groups)-1]
		body["next_cursor"] = mgmt.EncodeCursor(strconv.Itoa(last.Count), last.Name)
	}
	if len(groups) == 0 {
		return c.JSON(http.StatusOK, body)
	}

	names := make([]string, len(groups))
	index := make(map[string]int, len(groups))
	for i, g := range groups {
		names[i], index[g.Name] = g.Name, i
	}
	members, err := s.pool.Query(c.Ctx(), `SELECT s.name,s.skill_id,s.repo_id,s.scope,s.path,
   r.content_sha256,s.publication_status
 FROM gfm.skills s
 LEFT JOIN gfm.skill_revisions r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id = ANY($2::text[]) AND s.source_status <> 'removed'
   AND s.name = ANY($3::text[])
 ORDER BY s.name,s.repo_id,s.skill_id`, org.ID, repos, names)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer members.Close()
	for members.Next() {
		var name string
		var m duplicateMember
		if err = members.Scan(&name, &m.SkillID, &m.RepoID, &m.Scope, &m.Path,
			&m.ContentSHA256, &m.PublicationStatus); err != nil {
			return mgmt.Internal(err)
		}
		g := &groups[index[name]]
		g.Skills = append(g.Skills, m)
	}
	if err = members.Err(); err != nil {
		return mgmt.Internal(err)
	}
	body["items"] = groups
	return c.JSON(http.StatusOK, body)
}
