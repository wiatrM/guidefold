package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

// Contract 1.2 on the delivery path (PIVOT-ARCHITECTURE, gate 2).
//
// 1.2 is additive and nothing else. A 1.1 request produces byte-for-byte the
// response it produced before: the closure, the resource manifest and the
// snapshot check below only run when the caller *asked* for 1.2. An old client
// does not get new guarantees by accident, and a new label never changes the
// meaning of an existing field (api-contract-versioning).
//
// What 1.2 adds is the thing 1.1 could not say: whether the dependencies of the
// skill it just hydrated are actually loadable. 1.1 answers with a body and
// leaves the adapter to guess; `closure.status` says `complete`, `unresolved`
// or `cannot_fit`, and a truncated closure is never dressed up as a full one.

// closureDepthLimit bounds traversal. Eight is deep enough for a real
// `requires` chain and shallow enough that a pathological graph cannot turn one
// USE into a walk of the catalog.
const closureDepthLimit = 8

// defaultMaxCards is the contract's card budget when the caller sends none.
const defaultMaxCards = 4

// dependency is one entry of `closure.requires`.
type dependency struct {
	skillID  string
	revision string
	status   string
	depth    int
}

// Dependency statuses. `loaded` is the caller's own claim, verified against the
// snapshot; `available` can be delivered; `denied` is outside the resolved
// scope; `missing` is not in this snapshot at all.
const (
	depLoaded    = "loaded"
	depAvailable = "available"
	depDenied    = "denied"
	depMissing   = "missing"
)

// closureFor walks `requires` from one skill and reports what a harness would
// need in order to run it.
//
// Traversal is breadth-first so `depth` means "hops from the requested skill",
// which is what a depth limit has to mean for the number to be honest. A skill
// the caller already holds is counted as loaded and does not consume budget —
// that is the whole point of sending `loaded_skills`.
func closureFor(c *Catalog, root string, allowed map[string]bool, loaded map[string]string,
	maxCards int64) ([]dependency, string, []string) {
	if maxCards <= 0 {
		maxCards = defaultMaxCards
	}
	seen := map[string]bool{root: true}
	queue := []dependency{{skillID: root, depth: 0}}
	out := []dependency{}
	loadedIDs := []string{}
	truncated := false
	for i := 0; i < len(queue); i++ {
		current := queue[i]
		card := c.Cards[current.skillID]
		if card == nil {
			continue
		}
		if current.depth >= closureDepthLimit {
			// The chain is deeper than the limit: say so rather than reporting a
			// complete closure that stops where the walk did.
			truncated = true
			continue
		}
		for _, target := range stringList(card["requires"]) {
			if target == "" || seen[target] {
				continue
			}
			seen[target] = true
			d := dependency{skillID: target, revision: c.Revisions[target],
				depth: current.depth + 1}
			switch {
			case c.Cards[target] == nil:
				d.status = depMissing
			case loaded[target] != "" && loaded[target] == c.Revisions[target]:
				d.status = depLoaded
				loadedIDs = append(loadedIDs, target)
			case allowed != nil && !allowed[target]:
				// A dependency the caller may not read is named, not delivered
				// and not silently dropped: the adapter has to know that the
				// package it holds is incomplete for a reason.
				d.status = depDenied
			default:
				d.status = depAvailable
			}
			out = append(out, d)
			if d.status != depMissing {
				queue = append(queue, d)
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].depth != out[j].depth {
			return out[i].depth < out[j].depth
		}
		return out[i].skillID < out[j].skillID
	})
	// The requested skill occupies one card of the budget; the dependencies the
	// caller does not already hold occupy the rest.
	need := int64(1)
	status := "complete"
	for _, d := range out {
		switch d.status {
		case depAvailable:
			need++
		case depMissing, depDenied:
			status = "unresolved"
		}
	}
	if truncated {
		status = "unresolved"
	}
	if need > maxCards {
		// Too big to deliver honestly. `cannot_fit` is not "here is part of it".
		status = "cannot_fit"
	}
	sort.Strings(loadedIDs)
	return out, status, loadedIDs
}

// resourceRow is one entry of the 1.2 `resources` manifest.
type resourceRow struct {
	Path     string
	SHA256   string
	Size     int64
	Required bool
}

// resourcesFor lists the package files of the revision a snapshot is actually
// serving.
//
// The join is deliberately keyed on `published_snapshot_id`: a resource list
// assembled from a newer, unpublished revision would describe a package nobody
// can fetch. A tenant that is not an organisation — the legacy operator profile
// — has no management catalog behind it and gets an empty list rather than an
// error, because 1.1 never promised resources at all.
func (s *Store) resourcesFor(ctx context.Context, tenant, repo, snapshot, urn string) ([]resourceRow, string, error) {
	if !isUUID(tenant) {
		return []resourceRow{}, "", nil
	}
	var skillPath, revisionID string
	e := s.Pool.QueryRow(ctx, `SELECT path,COALESCE(published_revision_id,'') FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=$3 AND published_snapshot_id=$4`,
		tenant, repo, urn, snapshot).Scan(&skillPath, &revisionID)
	if e != nil || revisionID == "" {
		return []resourceRow{}, "", nil
	}
	rows, e := s.Pool.Query(ctx, `SELECT path,sha256,size_bytes,required,available
 FROM gfm.skill_resources WHERE org_id=$1::uuid AND revision_id=$2 ORDER BY path`,
		tenant, revisionID)
	if e != nil {
		return nil, "", e
	}
	defer rows.Close()
	dir := packageDir(skillPath)
	out := []resourceRow{}
	for rows.Next() {
		var r resourceRow
		var available bool
		if e = rows.Scan(&r.Path, &r.SHA256, &r.Size, &r.Required, &available); e != nil {
			return nil, "", e
		}
		if r.Required && !available {
			// A required resource whose bytes are gone is an error, not an entry
			// with a broken link (U1.7, U5.5).
			return nil, "", fail(409, "missing_required_resource")
		}
		if !available {
			continue
		}
		// Relative to the skill package, which is where a harness writes it.
		r.Path = strings.TrimPrefix(r.Path, dir+"/")
		out = append(out, r)
	}
	return out, dir, rows.Err()
}

func packageDir(skillPath string) string {
	if i := strings.LastIndex(skillPath, "/"); i >= 0 {
		return skillPath[:i]
	}
	return ""
}

func isUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, c := range s {
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return false
			}
		default:
			if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
				return false
			}
		}
	}
	return true
}

// resourceURL is the address of one package file. It carries the exact revision
// the caller was served, so following it can never return the bytes of another.
func resourceURL(skillID, revision, path string) string {
	return "/v1/skills/" + urlEscape(skillID) + "/revisions/" + urlEscape(revision) +
		"/resources/" + path
}

func urlEscape(s string) string { return url.PathEscape(s) }

// resourcePath is the parsed form of GET /v1/skills/{id}/revisions/{rev}/resources/{path...}.
type resourcePath struct {
	SkillID  string
	Revision string
	Path     string
}

// parseResourcePath reads the delivery resource route. It is parsed here rather
// than by a mux because /v1 is one handler, and because the trailing path may
// contain slashes: a package file keeps the relative path it has on disk.
func parseResourcePath(urlPath string) (resourcePath, bool) {
	const prefix = "/v1/skills/"
	if !strings.HasPrefix(urlPath, prefix) {
		return resourcePath{}, false
	}
	rest := urlPath[len(prefix):]
	i := strings.Index(rest, "/revisions/")
	if i <= 0 {
		return resourcePath{}, false
	}
	skillID, rest := rest[:i], rest[i+len("/revisions/"):]
	j := strings.Index(rest, "/resources/")
	if j <= 0 {
		return resourcePath{}, false
	}
	revision, file := rest[:j], rest[j+len("/resources/"):]
	id, e1 := urlUnescape(skillID)
	rev, e2 := urlUnescape(revision)
	name, e3 := urlUnescape(file)
	if e1 != nil || e2 != nil || e3 != nil || id == "" || rev == "" || name == "" {
		return resourcePath{}, false
	}
	// A path that tries to leave the package is refused before it reaches a
	// query: the service never opens a path a request supplied.
	if strings.HasPrefix(name, "/") || strings.Contains(name, `\`) ||
		strings.ContainsRune(name, 0) {
		return resourcePath{}, false
	}
	for _, seg := range strings.Split(name, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return resourcePath{}, false
		}
	}
	return resourcePath{SkillID: id, Revision: rev, Path: name}, true
}

func urlUnescape(s string) (string, error) { return url.PathUnescape(s) }

// writeDeliveryError renders the /v1 error envelope for the routes that answer
// bytes rather than JSON. It is the same shape the JSON endpoints use, so a
// client parses one error format on the whole delivery surface.
func writeDeliveryError(w http.ResponseWriter, e error) {
	status, code := 503, "backend_unavailable"
	var api *APIError
	if errors.As(e, &api) {
		status, code = api.Status, api.Code
	} else if errors.Is(e, context.DeadlineExceeded) || errors.Is(e, context.Canceled) {
		status, code = 504, "deadline_exceeded"
	}
	body, _ := json.Marshal(M{"error": code})
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

// serveResource answers the exact bytes of one package file.
//
// Access is re-checked here, not inherited from the USE that listed it: the
// caller may have lost the scope, the head may have moved, and a URL is not a
// capability.
func (a *App) serveResource(w http.ResponseWriter, r *http.Request) {
	ref, ok := parseResourcePath(r.URL.Path)
	if !ok {
		writeDeliveryError(w, fail(404, "revision_not_found"))
		return
	}
	principal, authErr := a.authenticate(r, "use")
	if authErr != nil {
		writeDeliveryError(w, authErr)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	tenant, e := a.resolveTenant(ctx, principal, r)
	if e != nil {
		writeDeliveryError(w, e)
		return
	}
	repo, e := a.resolveRepo(ctx, principal, r, M{}, tenant)
	if e != nil {
		writeDeliveryError(w, e)
		return
	}
	c, e := a.Store.catalog(ctx, tenant, repo)
	if e != nil {
		writeDeliveryError(w, e)
		return
	}
	card, ok := c.Cards[ref.SkillID]
	if !ok {
		writeDeliveryError(w, fail(404, "skill_not_found"))
		return
	}
	if c.Revisions[ref.SkillID] != ref.Revision {
		// Never the newest one instead: hydrating a revision nobody asked for is
		// how an agent ends up acting on unreviewed instructions.
		writeDeliveryError(w, fail(404, "revision_not_found"))
		return
	}
	if str(card["status"]) != "active" {
		writeDeliveryError(w, fail(409, "skill_not_active"))
		return
	}
	rows, dir, e := a.Store.resourcesFor(ctx, tenant, repo, c.ID, ref.SkillID)
	if e != nil {
		writeDeliveryError(w, e)
		return
	}
	var found *resourceRow
	for i := range rows {
		if rows[i].Path == ref.Path {
			found = &rows[i]
			break
		}
	}
	if found == nil {
		writeDeliveryError(w, fail(404, "revision_not_found"))
		return
	}
	data, e := a.Store.blobBytes(ctx, tenant, found.SHA256)
	if e != nil {
		if found.Required {
			writeDeliveryError(w, fail(409, "missing_required_resource"))
			return
		}
		writeDeliveryError(w, fail(404, "revision_not_found"))
		return
	}
	_ = dir
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("X-Content-SHA256", found.SHA256)
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(data)
}

// blobBytes reads one stored object of an organisation.
func (s *Store) blobBytes(ctx context.Context, tenant, sha string) ([]byte, error) {
	if !isUUID(tenant) {
		return nil, fail(404, "revision_not_found")
	}
	var content []byte
	e := s.Pool.QueryRow(ctx, `SELECT content FROM gfm.blobs
 WHERE org_id=$1::uuid AND sha256=$2`, tenant, sha).Scan(&content)
	return content, e
}

// schemaVersion12 is the additive delivery contract of PIVOT-ARCHITECTURE gate 2.
const schemaVersion12 = "1.2"

// decorate12 adds the two things 1.2 promises over 1.1: the dependency closure
// of the hydrated skill, and the manifest of its package resources.
//
// Both are computed from the snapshot that answered the request, so a client
// that follows a resource URL gets a file belonging to the exact revision it
// was handed.
func (s *Store) decorate12(ctx context.Context, c *Catalog, p M, result M, id string,
	reachable map[string]bool) error {
	loaded := map[string]string{}
	for _, x := range arr(p["loaded_skills"]) {
		l := obj(x)
		if str(l["state"]) == "hydrated" {
			loaded[str(l["skill_id"])] = str(l["revision"])
		}
	}
	budget := obj(p["budget"])
	requires, status, loadedIDs := closureFor(c, id, reachable, loaded,
		integer(budget, "max_cards", defaultMaxCards))
	entries := []M{}
	for _, d := range requires {
		entries = append(entries, M{"skill_id": d.skillID, "revision": nullString(d.revision),
			"status": d.status, "depth": d.depth})
	}
	if loadedIDs == nil {
		loadedIDs = []string{}
	}
	result["closure"] = M{"status": status, "requires": entries,
		"depth_limit": closureDepthLimit, "loaded": loadedIDs}

	rows, _, e := s.resourcesFor(ctx, c.Tenant, c.Repo, c.ID, id)
	if e != nil {
		return e
	}
	resources := []M{}
	for _, r := range rows {
		resources = append(resources, M{"path": r.Path, "sha256": r.SHA256, "size": r.Size,
			"required": r.Required, "url": resourceURL(id, c.Revisions[id], r.Path)})
	}
	result["resources"] = resources

	// Where the hydrated skill sits in the pyramid, and what sits next to it.
	// The closure above answers "what else do I need to run this"; the family
	// answers "is there a version of this written for my scope" — a different
	// question, and the one an agent holding an abstraction actually has (P08).
	layers := s.knowledgeLayers(ctx, c.Tenant, c.familyIDs([]string{id}))
	result["family"] = c.familyFor(id, layers)
	return nil
}

// nullString keeps "unknown" out of the response as null rather than "".
func nullString(v string) any {
	if v == "" {
		return nil
	}
	return v
}
