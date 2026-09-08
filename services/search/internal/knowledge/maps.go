package knowledge

import (
	"context"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// The three maps are deliberately three endpoints over the same catalog rather
// than one tree with a mode switch. They answer different questions — where a
// file lives, which team owns a scope, how abstract a skill is — and a reader
// who conflates them ends up believing directory depth is a knowledge layer.

// mapChild is one entry of the repository tree.
type mapChild struct {
	Name    string  `json:"name"`
	Path    string  `json:"path"`
	Kind    string  `json:"kind"` // dir|skill|document
	SkillID *string `json:"skill_id"`
	Count   *int    `json:"count"`
}

// handleMapRepository lists the direct children of one path: the source tree as
// the scan saw it, not a rendering of the scope map.
func (s *Service) handleMapRepository(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	path := strings.Trim(c.Query("path"), "/")
	prefix := ""
	if path != "" {
		prefix = path + "/"
	}
	after := ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 1)
		if err != nil {
			return err
		}
		after = parts[0]
	}
	type entry struct {
		child mapChild
		count int
	}
	children := map[string]*entry{}
	add := func(full, kind, skillID string) {
		if !strings.HasPrefix(full, prefix) {
			return
		}
		rest := full[len(prefix):]
		if rest == "" {
			return
		}
		name, leaf := rest, true
		if cut := strings.IndexByte(rest, '/'); cut >= 0 {
			name, leaf = rest[:cut], false
		}
		v, ok := children[name]
		if !ok {
			v = &entry{child: mapChild{Name: name, Path: prefix + name, Kind: "dir"}}
			children[name] = v
		}
		v.count++
		if leaf {
			v.child.Kind = kind
			if skillID != "" {
				id := skillID
				v.child.SkillID = &id
			}
		}
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT path,skill_id FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	for rows.Next() {
		var p, id string
		if err = rows.Scan(&p, &id); err != nil {
			rows.Close()
			return mgmt.Internal(err)
		}
		add(p, "skill", id)
	}
	rows.Close()
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	docs, err := s.pool.Query(c.Ctx(), `SELECT DISTINCT path FROM gfm.documents
 WHERE org_id=$1::uuid AND repo_id=$2`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	for docs.Next() {
		var p string
		if err = docs.Scan(&p); err != nil {
			docs.Close()
			return mgmt.Internal(err)
		}
		add(p, "document", "")
	}
	docs.Close()
	if err = docs.Err(); err != nil {
		return mgmt.Internal(err)
	}

	names := make([]string, 0, len(children))
	for name := range children {
		if after == "" || name > after {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	const limit = 200
	next := ""
	if len(names) > limit {
		names = names[:limit]
		next = mgmt.EncodeCursor(names[len(names)-1])
	}
	items := make([]mapChild, 0, len(names))
	for _, name := range names {
		v := children[name]
		if v.child.Kind == "dir" {
			count := v.count
			v.child.Count = &count
		}
		items = append(items, v.child)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "path": path,
		"children": items, "next_cursor": nullable(next)})
}

// scopeView is one node of the scope map.
type scopeView struct {
	ID     string   `json:"id"`
	Owner  *string  `json:"owner"`
	Parent *string  `json:"parent"`
	Paths  []string `json:"paths"`
	Source string   `json:"source"`
	Count  int      `json:"count"`
}

// handleMapScopes answers the scope axis: the guidefold.yaml mapping, the
// skills each node holds, and — separately — the skills whose scope is not a
// declared node. An unmapped skill is shown as unmapped rather than folded into
// the root, because "we do not know who owns this" is the finding (U1).
func (s *Service) handleMapScopes(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	scope := c.Query("scope")
	counts := map[string]int{}
	rows, err := s.pool.Query(c.Ctx(), `SELECT scope,count(*) FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 GROUP BY scope`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	for rows.Next() {
		var name string
		var n int
		if err = rows.Scan(&name, &n); err != nil {
			rows.Close()
			return mgmt.Internal(err)
		}
		counts[name] = n
	}
	rows.Close()
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}

	nodes, err := s.scopes(c.Ctx(), org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	known := map[string]bool{}
	items := []scopeView{}
	var selected *scopeView
	for i := range nodes {
		node := nodes[i]
		known[node.ID] = true
		node.Count = counts[node.ID]
		if node.ID == scope {
			copied := node
			selected = &copied
		}
		if scope == "" || strings.HasPrefix(node.ID, scope+".") {
			items = append(items, node)
		}
	}
	if scope != "" && selected == nil {
		return mgmt.NotFound("not_found", "No such scope in this repository.")
	}

	skills, err := s.summariesForScope(c.Ctx(), org.ID, repo.ID, scope)
	if err != nil {
		return mgmt.Internal(err)
	}
	unmapped := []map[string]any{}
	for name, n := range counts {
		if !known[name] {
			unmapped = append(unmapped, map[string]any{"scope": name, "count": n})
		}
	}
	sort.Slice(unmapped, func(i, j int) bool {
		return unmapped[i]["scope"].(string) < unmapped[j]["scope"].(string)
	})
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "scope": selected,
		"scopes": items, "skills": skills, "unmapped": unmapped})
}

func (s *Service) scopes(ctx context.Context, orgID, repoID string) ([]scopeView, error) {
	rows, e := s.pool.Query(ctx, `SELECT scope,owner,parent,paths,source FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2 ORDER BY scope`, orgID, repoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []scopeView{}
	for rows.Next() {
		var v scopeView
		if e = rows.Scan(&v.ID, &v.Owner, &v.Parent, &v.Paths, &v.Source); e != nil {
			return nil, e
		}
		if v.Paths == nil {
			v.Paths = []string{}
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

func (s *Service) summariesForScope(ctx context.Context, orgID, repoID, scope string) ([]skillSummary, error) {
	rows, e := s.pool.Query(ctx, `SELECT `+summaryColumns+summaryFrom+`
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND ($3='' OR s.scope=$3 OR s.scope LIKE $3||'.%')
 ORDER BY s.name,s.skill_id LIMIT 1000`, orgID, repoID, scope)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []skillSummary{}
	for rows.Next() {
		v, e := scanSummary(rows)
		if e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// handleMapLayers answers the knowledge axis. It is a different question from
// the scope map: a layer says how abstract a skill is, not who owns it, and it
// never follows from directory depth (API-CONTRACT §5.3).
func (s *Service) handleMapLayers(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT knowledge_layer,count(*) FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 GROUP BY 1 ORDER BY 1`, org.ID, repo.ID)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	layers := []map[string]any{}
	for rows.Next() {
		var layer string
		var count int
		if err = rows.Scan(&layer, &count); err != nil {
			return mgmt.Internal(err)
		}
		layers = append(layers, map[string]any{"layer": layer, "count": count})
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "layers": layers})
}

// handleMapRelations answers the neighbourhood of one skill, or the whole
// declared graph when none is named. `truncated` says outright when the answer
// was cut, so a reader never mistakes a page for the whole graph.
func (s *Service) handleMapRelations(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	limit := 200
	if v := c.Query("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > 1000 {
			return mgmt.Invalid("invalid_request", "limit must be between 1 and 1000.")
		}
		limit = n
	}
	kind := c.Query("type")
	if kind != "" && !relationTypes[kind] {
		return mgmt.Invalid("invalid_request",
			"type must be one of derived_from, requires, refines, similar, conflicts_with.")
	}
	skillID := c.Param("skill_id")
	if v := c.Query("skill_id"); v != "" {
		skillID = v
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT r.from_skill_id,r.to_skill_id,r.type,r.provenance,
 COALESCE(r.revision_id,'') FROM gfm.relations r
 JOIN gfm.skills s ON s.org_id=r.org_id AND s.skill_id=r.from_skill_id AND s.repo_id=$2
 WHERE r.org_id=$1::uuid
   AND ($3='' OR r.from_skill_id=$3 OR r.to_skill_id=$3)
   AND ($4='' OR r.type=$4)
 ORDER BY r.from_skill_id,r.type,r.to_skill_id LIMIT $5`,
		org.ID, repo.ID, skillID, kind, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []relationEdge{}
	for rows.Next() {
		var v relationEdge
		if err = rows.Scan(&v.From, &v.To, &v.Type, &v.Provenance, &v.Revision); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, v)
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	truncated := len(items) > limit
	next := ""
	if truncated {
		items = items[:limit]
		last := items[len(items)-1]
		next = mgmt.EncodeCursor(last.From, last.Type, last.To)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "items": items,
		"next_cursor": nullable(next), "truncated": truncated})
}

var relationTypes = map[string]bool{"derived_from": true, "requires": true, "refines": true,
	"similar": true, "conflicts_with": true}

// handleModule answers one scope as a module: who owns it, what to read and in
// which order, what it borrows from elsewhere and which documents belong to it.
func (s *Service) handleModule(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	scope := c.Param("scope")
	var owner *string
	var paths []string
	if err := s.pool.QueryRow(c.Ctx(), `SELECT owner,paths FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2 AND scope=$3`, org.ID, repo.ID, scope).
		Scan(&owner, &paths); err != nil {
		return mgmt.NotFound("not_found", "No such scope in this repository.")
	}
	skills, err := s.summariesForScope(c.Ctx(), org.ID, repo.ID, scope)
	if err != nil {
		return mgmt.Internal(err)
	}
	inScope := map[string]bool{}
	for _, sk := range skills {
		inScope[sk.SkillID] = true
	}
	edges, err := s.relations(c.Ctx(), org.ID, "", "", "", 1000)
	if err != nil {
		return mgmt.Internal(err)
	}
	// Reading order: what a skill requires comes before the skill itself, so a
	// newcomer reads the foundation first. Cycles and unknown edges fall back
	// to name order rather than dropping a skill from the list.
	order := readingOrder(skills, edges, inScope)
	shared := map[string][]string{}
	for _, edge := range edges {
		if inScope[edge.From] && !inScope[edge.To] {
			shared[edge.To] = append(shared[edge.To], edge.From)
		}
	}
	borrowed := []map[string]any{}
	for id, users := range shared {
		sort.Strings(users)
		borrowed = append(borrowed, map[string]any{"skill_id": id, "used_by": users})
	}
	sort.Slice(borrowed, func(i, j int) bool {
		return borrowed[i]["skill_id"].(string) < borrowed[j]["skill_id"].(string)
	})
	documents, err := s.documentsOfScope(c.Ctx(), org.ID, repo.ID, scope)
	if err != nil {
		return mgmt.Internal(err)
	}
	if paths == nil {
		paths = []string{}
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "scope": scope, "owner": owner, "paths": paths,
		"skills": skills, "reading_order": order, "shared": borrowed, "documents": documents})
}

// readingOrder sorts the module's skills so that a skill's own prerequisites
// come first. It is a stable topological order over the intra-scope `requires`
// edges; anything it cannot order stays in name order.
func readingOrder(skills []skillSummary, edges []relationEdge, inScope map[string]bool) []string {
	needs := map[string]map[string]bool{}
	for _, sk := range skills {
		needs[sk.SkillID] = map[string]bool{}
	}
	for _, edge := range edges {
		if edge.Type != "requires" || !inScope[edge.From] || !inScope[edge.To] {
			continue
		}
		needs[edge.From][edge.To] = true
	}
	done := map[string]bool{}
	order := []string{}
	for len(order) < len(skills) {
		progress := false
		for _, sk := range skills { // skills are already in name order
			if done[sk.SkillID] {
				continue
			}
			ready := true
			for need := range needs[sk.SkillID] {
				if !done[need] {
					ready = false
					break
				}
			}
			if ready {
				done[sk.SkillID] = true
				order = append(order, sk.SkillID)
				progress = true
			}
		}
		if !progress { // a cycle: keep every skill, in name order
			for _, sk := range skills {
				if !done[sk.SkillID] {
					done[sk.SkillID] = true
					order = append(order, sk.SkillID)
				}
			}
		}
	}
	return order
}

func (s *Service) documentsOfScope(ctx context.Context, orgID, repoID, scope string) ([]map[string]any, error) {
	rows, e := s.pool.Query(ctx, `SELECT DISTINCT path,kind FROM gfm.documents
 WHERE org_id=$1::uuid AND repo_id=$2 AND scope=$3 ORDER BY path LIMIT 500`, orgID, repoID, scope)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var path, kind string
		if e = rows.Scan(&path, &kind); e != nil {
			return nil, e
		}
		out = append(out, map[string]any{"path": path, "kind": kind})
	}
	return out, rows.Err()
}
