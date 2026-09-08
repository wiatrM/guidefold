package knowledge_test

import (
	"bytes"
	"context"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

const gitHost = "https://github.example/acme/meridian"

// fixtureSkills is how many skills the Meridian fixture puts in the catalog. The
// tree holds 27 SKILL.md files; the 27th is the generated hierarchy index, which
// the builder lists under `generated_skipped` rather than as an inventory row,
// because Index.build makes no card for it and a catalog row without a card is a
// skill SEARCH can never return.
const fixtureSkills = 26

// catalog is one imported and parsed copy of the Meridian fixture: the read
// endpoints are only worth testing over the rows a real parse produced.
type catalog struct {
	h       *pivottest.Harness
	owner   *pivottest.Client
	org     string
	repo    string
	tree    string
	base    string
	import_ string
}

func newCatalog(t *testing.T) *catalog {
	t.Helper()
	return newCatalogWith(t, func(string) {})
}

// newCatalogWith lets a test edit the tree before it is imported.
func newCatalogWith(t *testing.T, edit func(tree string)) *catalog {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "meridian", gitHost)
	tree := pivottest.Monorepo(t)
	edit(tree)
	scratch := pivottest.Scratch(t, "knowledge")
	manifest := pivottest.Manifest(t, tree, "acme", "meridian", true)
	importID := pivottest.Push(t, owner, org, "meridian", tree, manifest, "first")
	h.RunParse(t, scratch)
	c := &catalog{h: h, owner: owner, org: org, repo: "meridian", tree: tree,
		base: pivottest.RepoBase(org, "meridian"), import_: importID}
	if state := c.importState(t); state != "ready" {
		t.Fatalf("the fixture import is %s, not ready", state)
	}
	return c
}

func (c *catalog) importState(t *testing.T) string {
	t.Helper()
	_, body, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: c.base + "/imports/" + c.import_})
	state, _ := body["state"].(string)
	return state
}

func (c *catalog) get(t *testing.T, path string) (int, map[string]any) {
	t.Helper()
	status, body, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: c.base + path})
	return status, body
}

func (c *catalog) mustGet(t *testing.T, path string) map[string]any {
	t.Helper()
	status, body := c.get(t, path)
	if status != http.StatusOK {
		t.Fatalf("GET %s: %d %v", path, status, body)
	}
	return body
}

// skillPath is the URL for one skill, with its URN encoded into one segment.
func (c *catalog) skillPath(skillID string) string {
	return "/skills/" + url.PathEscape(skillID)
}

// U4.1 — every skill of the fixture is reachable through the list, with its
// scope, owner and source, and paging never loses or repeats one.
func TestEverySkillOfTheFixtureIsReachableThroughTheList(t *testing.T) {
	c := newCatalog(t)
	seen := map[string]map[string]any{}
	cursor, pages := "", 0
	for {
		path := "/skills?limit=10"
		if cursor != "" {
			path += "&cursor=" + url.QueryEscape(cursor)
		}
		page := c.mustGet(t, path)
		for _, raw := range page["items"].([]any) {
			item := raw.(map[string]any)
			id := item["skill_id"].(string)
			if _, twice := seen[id]; twice {
				t.Fatalf("paging returned %s twice", id)
			}
			seen[id] = item
		}
		pages++
		next, _ := page["next_cursor"].(string)
		if next == "" || pages > 10 {
			break
		}
		cursor = next
	}
	if len(seen) != fixtureSkills {
		t.Fatalf("the list reached %d of the fixture's %d skills", len(seen), fixtureSkills)
	}
	if pages < 3 {
		t.Fatalf("a limit of 10 over %d skills produced %d pages", fixtureSkills, pages)
	}
	for id, item := range seen {
		if item["scope"] == "" || item["scope"] == nil {
			t.Fatalf("%s has no scope", id)
		}
		if item["path"] == "" || item["revision_id"] == nil || item["content_sha256"] == nil {
			t.Fatalf("%s has no source: %v", id, item)
		}
		if item["publication_status"] != "draft" {
			t.Fatalf("%s is %v before anything published it", id, item["publication_status"])
		}
	}
	// The scope map is the same 17 nodes the fixture declares, and every skill
	// the catalog holds is accounted for in it or named as unmapped.
	scopes := c.mustGet(t, "/map/scopes")
	if got := len(scopes["scopes"].([]any)); got != 17 {
		t.Fatalf("the scope map holds %d nodes", got)
	}
	mapped := 0
	for _, raw := range scopes["scopes"].([]any) {
		mapped += int(raw.(map[string]any)["count"].(float64))
	}
	for _, raw := range scopes["unmapped"].([]any) {
		mapped += int(raw.(map[string]any)["count"].(float64))
	}
	if mapped != fixtureSkills {
		t.Fatalf("the scope map accounts for %d of %d skills", mapped, fixtureSkills)
	}
}

// A skill whose scope is not a declared node is named as unmapped rather than
// folded into the root. The fixture's generated hierarchy index used to be that
// skill by accident; generated cards no longer reach the catalog at all, and an
// imported card always gets a declared node from `node_for`, so the only way to
// reach this branch is the way production reaches it: a node that was declared
// when the skills were imported and is not declared any more. Deleting the scope
// row is exactly that state, and it is the state the endpoint must not hide.
func TestAnUnmappedScopeIsNamedRatherThanHidden(t *testing.T) {
	c := newCatalog(t)
	before := c.mustGet(t, "/map/scopes")
	var dropped string
	var droppedCount float64
	for _, raw := range before["scopes"].([]any) {
		item := raw.(map[string]any)
		if scope, _ := item["id"].(string); scope != "_root" && item["count"].(float64) > 0 {
			dropped, droppedCount = scope, item["count"].(float64)
			break
		}
	}
	if dropped == "" {
		t.Fatal("the fixture must declare a non-root scope carrying skills")
	}
	if _, e := c.h.Pool.Exec(context.Background(),
		`DELETE FROM gfm.scopes WHERE org_id=$1::uuid AND repo_id=$2 AND scope=$3`,
		c.org, c.repo, dropped); e != nil {
		t.Fatal(e)
	}

	scopes := c.mustGet(t, "/map/scopes")
	unmapped := scopes["unmapped"].([]any)
	if len(unmapped) == 0 {
		t.Fatalf("scope %q is no longer declared and its skills vanished from the map", dropped)
	}
	found := false
	for _, raw := range unmapped {
		item := raw.(map[string]any)
		if item["scope"] == "" || item["count"].(float64) < 1 {
			t.Fatalf("unmapped entry %v", item)
		}
		if item["scope"] == dropped {
			found = true
			if item["count"].(float64) != droppedCount {
				t.Fatalf("unmapped %s counts %v, the scope carried %v",
					dropped, item["count"], droppedCount)
			}
		}
	}
	if !found {
		t.Fatalf("%q is not declared and is not named as unmapped either: %v", dropped, unmapped)
	}
	// Still every skill, just described differently.
	total := 0
	for _, raw := range append(scopes["scopes"].([]any), unmapped...) {
		total += int(raw.(map[string]any)["count"].(float64))
	}
	if total != fixtureSkills {
		t.Fatalf("the scope map accounts for %d of %d skills", total, fixtureSkills)
	}
}

// Filters echo what they were given. A value the catalog does not know returns
// an empty page and `available:false`, never a silent fall back to "All".
func TestAnUnknownFilterValueIsReportedUnavailable(t *testing.T) {
	c := newCatalog(t)
	page := c.mustGet(t, "/skills?scope=does.not.exist")
	if items := page["items"].([]any); len(items) != 0 {
		t.Fatalf("an unknown scope returned %d skills", len(items))
	}
	echo := page["filters"].(map[string]any)["scope"].(map[string]any)
	if echo["value"] != "does.not.exist" || echo["available"] != false {
		t.Fatalf("filter echo %v", echo)
	}
	lookup := c.mustGet(t, "/skills/facets/lookup?field=scope&value=does.not.exist")
	if lookup["available"] != false || lookup["count"].(float64) != 0 {
		t.Fatalf("lookup %v", lookup)
	}

	// A known value is available and its count matches the page.
	known := c.mustGet(t, "/skills?scope=atlas.identity.turnstile")
	echo = known["filters"].(map[string]any)["scope"].(map[string]any)
	if echo["available"] != true {
		t.Fatalf("a real scope was reported unavailable: %v", echo)
	}
	lookup = c.mustGet(t, "/skills/facets/lookup?field=scope&value=atlas.identity.turnstile")
	if int(lookup["count"].(float64)) != len(known["items"].([]any)) {
		t.Fatalf("lookup count %v vs page %d", lookup["count"], len(known["items"].([]any)))
	}
}

func TestFacetsCountTheCatalog(t *testing.T) {
	c := newCatalog(t)
	for _, field := range []string{"scope", "owner", "layer", "status"} {
		facets := c.mustGet(t, "/skills/facets?field="+field)
		values := facets["values"].([]any)
		if len(values) == 0 {
			t.Fatalf("field %s has no values", field)
		}
		total := 0
		for _, raw := range values {
			total += int(raw.(map[string]any)["count"].(float64))
		}
		if total > fixtureSkills {
			t.Fatalf("field %s counts %d skills, the catalog holds %d", field, total, fixtureSkills)
		}
	}
	status, body := c.get(t, "/skills/facets?field=colour")
	if status != http.StatusBadRequest || body["error"] != "invalid_request" {
		t.Fatalf("an unknown facet field: %d %v", status, body)
	}
}

// firstSkill returns one skill summary and its detail.
func (c *catalog) firstSkill(t *testing.T) (map[string]any, map[string]any) {
	t.Helper()
	page := c.mustGet(t, "/skills?limit=1")
	summary := page["items"].([]any)[0].(map[string]any)
	detail := c.mustGet(t, c.skillPath(summary["skill_id"].(string)))
	return summary, detail
}

// A URN survives the round trip through a path segment, and the detail carries
// the skill's revisions.
func TestSkillDetailCarriesItsRevisions(t *testing.T) {
	c := newCatalog(t)
	summary, detail := c.firstSkill(t)
	if detail["skill_id"] != summary["skill_id"] {
		t.Fatalf("detail is for %v, asked for %v", detail["skill_id"], summary["skill_id"])
	}
	if !strings.HasPrefix(detail["skill_id"].(string), "urn:skill:meridian:") {
		t.Fatalf("skill_id %v is not a URN", detail["skill_id"])
	}
	revisions := detail["revisions"].([]any)
	if len(revisions) != 1 {
		t.Fatalf("one import produced %d revisions", len(revisions))
	}
	ref := revisions[0].(map[string]any)
	if ref["revision_id"] != summary["revision_id"] || ref["source"] != "import" {
		t.Fatalf("revision ref %v", ref)
	}
	status, body := c.get(t, "/skills/"+url.PathEscape("urn:skill:meridian:_root:nope"))
	if status != http.StatusNotFound || body["error"] != "skill_not_found" {
		t.Fatalf("unknown skill: %d %v", status, body)
	}
}

// A revision that does not exist is 404 — never the latest one instead.
func TestAnUnknownRevisionIs404AndNeverTheLatest(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID := summary["skill_id"].(string)
	real := summary["revision_id"].(string)

	unknown := strings.Repeat("0", 64)
	status, body := c.get(t, c.skillPath(skillID)+"/revisions/"+unknown)
	if status != http.StatusNotFound || body["error"] != "revision_not_found" {
		t.Fatalf("%d %v", status, body)
	}
	if body["revision_id"] != nil || body["body"] != nil {
		t.Fatalf("the 404 carried a revision anyway: %v", body)
	}
	status, body = c.get(t, c.skillPath(skillID)+"/revisions/"+unknown+"/raw")
	if status != http.StatusNotFound || body["error"] != "revision_not_found" {
		t.Fatalf("raw: %d %v", status, body)
	}

	// Another skill's real revision id is equally unknown under this skill.
	page := c.mustGet(t, "/skills?limit=2")
	other := page["items"].([]any)[1].(map[string]any)
	status, body = c.get(t, c.skillPath(skillID)+"/revisions/"+other["revision_id"].(string))
	if status != http.StatusNotFound || body["error"] != "revision_not_found" {
		t.Fatalf("a revision of another skill: %d %v", status, body)
	}
	if real == other["revision_id"] {
		t.Fatal("two skills share a revision id; the identity derivation is broken")
	}
}

// The revision view carries the body, the frontmatter, the source link built
// from the repository's git host, and the declared relations.
func TestRevisionCarriesBodyProvenanceAndRelations(t *testing.T) {
	c := newCatalog(t)
	// A skill the fixture gives explicit `requires` edges.
	page := c.mustGet(t, "/skills?scope=atlas.identity.turnstile")
	items := page["items"].([]any)
	if len(items) == 0 {
		t.Skip("the fixture no longer holds a turnstile skill")
	}
	summary := items[0].(map[string]any)
	skillID := summary["skill_id"].(string)
	revision := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+summary["revision_id"].(string))

	body, _ := revision["body"].(string)
	if !strings.Contains(body, "---") {
		t.Fatalf("the body does not look like a SKILL.md: %.80q", body)
	}
	frontmatter, ok := revision["frontmatter"].(map[string]any)
	if !ok || frontmatter["name"] == nil {
		t.Fatalf("frontmatter %v", revision["frontmatter"])
	}
	source := revision["source"].(map[string]any)
	want := gitHost + "/blob/" + summary["commit"].(string) + "/" + summary["path"].(string)
	if source["url"] != want {
		t.Fatalf("source url %v, want %v", source["url"], want)
	}
	if len(revision["requires"].([]any)) == 0 {
		t.Fatalf("the turnstile skill declares requires, the revision shows none: %v", revision)
	}
	provenance := revision["provenance"].(map[string]any)
	if provenance["origin"] != "source" || provenance["import_id"] != c.import_ {
		t.Fatalf("provenance %v", provenance)
	}
	if revision["publication_status"] != "draft" {
		t.Fatalf("publication_status %v", revision["publication_status"])
	}
}

// A repository without a git host has no source link. A wrong permalink would
// be worse than none.
func TestARepositoryWithoutAGitHostHasNoSourceLink(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "meridian", "")
	tree := pivottest.Monorepo(t)
	pivottest.Push(t, owner, org, "meridian", tree,
		pivottest.Manifest(t, tree, "acme", "meridian", true), "first")
	h.RunParse(t, pivottest.Scratch(t, "nogit"))

	base := pivottest.RepoBase(org, "meridian")
	_, page, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: base + "/skills?limit=1"})
	summary := page["items"].([]any)[0].(map[string]any)
	_, revision, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: base + "/skills/" + url.PathEscape(summary["skill_id"].(string)) +
			"/revisions/" + summary["revision_id"].(string)})
	if revision["source"].(map[string]any)["url"] != nil {
		t.Fatalf("a repository with no git host produced a link: %v", revision["source"])
	}
}

// The raw endpoint returns the imported bytes exactly, including a NUL byte,
// with their digest in a header.
func TestRawReturnsTheExactImportedBytes(t *testing.T) {
	const oddPath = ".agents/skills/adr-process/SKILL.md"
	var uploaded []byte
	c := newCatalogWith(t, func(tree string) {
		full := filepath.Join(tree, filepath.FromSlash(oddPath))
		raw, e := os.ReadFile(full)
		if e != nil {
			t.Fatal(e)
		}
		// A NUL and a non-ASCII rune in the body, after the frontmatter, so the
		// file still parses but its bytes are not plain ASCII text.
		uploaded = append(append([]byte{}, raw...), []byte("\nodd byte:\x00 end — ✓\n")...)
		if e := os.WriteFile(full, uploaded, 0o644); e != nil {
			t.Fatal(e)
		}
	})
	page := c.mustGet(t, "/skills?q=adr-process")
	items := page["items"].([]any)
	if len(items) == 0 {
		t.Fatalf("the edited skill is not in the catalog: %v", page)
	}
	summary := items[0].(map[string]any)
	path := c.base + c.skillPath(summary["skill_id"].(string)) +
		"/revisions/" + summary["revision_id"].(string) + "/raw"
	status, got, header := c.owner.Raw(t, pivottest.Call{Method: http.MethodGet, Path: path})
	if status != http.StatusOK {
		t.Fatalf("raw: %d %s", status, got)
	}
	if !bytes.Equal(got, uploaded) {
		t.Fatalf("raw returned %d bytes, %d were uploaded", len(got), len(uploaded))
	}
	if !bytes.Contains(got, []byte{0}) {
		t.Fatal("the NUL byte did not survive the round trip")
	}
	if header.Get("X-Content-SHA256") != summary["content_sha256"] {
		t.Fatalf("X-Content-SHA256 %q vs %v", header.Get("X-Content-SHA256"), summary["content_sha256"])
	}
	if header.Get("Cache-Control") != "no-store" {
		t.Fatalf("Cache-Control %q", header.Get("Cache-Control"))
	}
}

// The three maps answer three different questions over the same catalog.
func TestTheMapsCoverTheWholeCatalog(t *testing.T) {
	c := newCatalog(t)
	root := c.mustGet(t, "/map/repository")
	names := []string{}
	for _, raw := range root["children"].([]any) {
		child := raw.(map[string]any)
		names = append(names, child["name"].(string))
		if child["kind"] == "dir" && child["count"] == nil {
			t.Fatalf("a directory carries no count: %v", child)
		}
	}
	sort.Strings(names)
	if len(names) == 0 || !contains(names, ".agents") {
		t.Fatalf("the repository root shows %v", names)
	}
	inner := c.mustGet(t, "/map/repository?path=.agents/skills")
	if len(inner["children"].([]any)) == 0 {
		t.Fatal(".agents/skills has no children")
	}

	layers := c.mustGet(t, "/map/layers")
	total := 0
	for _, raw := range layers["layers"].([]any) {
		total += int(raw.(map[string]any)["count"].(float64))
	}
	if total != fixtureSkills {
		t.Fatalf("the layer map covers %d of %d skills", total, fixtureSkills)
	}

	relations := c.mustGet(t, "/map/relations")
	if len(relations["items"].([]any)) == 0 {
		t.Fatal("the fixture declares relations, the map shows none")
	}
	if relations["truncated"] != false {
		t.Fatalf("the whole graph was reported truncated: %v", relations["truncated"])
	}
	cut := c.mustGet(t, "/map/relations?limit=1")
	if cut["truncated"] != true || len(cut["items"].([]any)) != 1 {
		t.Fatalf("a cut answer does not say so: %v", cut)
	}
	status, body := c.get(t, "/map/relations?type=nonsense")
	if status != http.StatusBadRequest || body["error"] != "invalid_request" {
		t.Fatalf("unknown relation type: %d %v", status, body)
	}
}

func contains(list []string, want string) bool {
	for _, v := range list {
		if v == want {
			return true
		}
	}
	return false
}

// A module page names its owner, orders its skills so prerequisites come first
// and lists what it borrows from other scopes.
func TestModulePageReadsAsAModule(t *testing.T) {
	c := newCatalog(t)
	module := c.mustGet(t, "/modules/atlas.identity")
	if module["owner"] != "identity-platform" {
		t.Fatalf("owner %v", module["owner"])
	}
	skills := module["skills"].([]any)
	order := module["reading_order"].([]any)
	if len(order) != len(skills) {
		t.Fatalf("reading order holds %d of %d skills", len(order), len(skills))
	}
	inOrder := map[string]int{}
	for i, raw := range order {
		inOrder[raw.(string)] = i
	}
	for _, raw := range skills {
		if _, ok := inOrder[raw.(map[string]any)["skill_id"].(string)]; !ok {
			t.Fatalf("a skill is missing from the reading order: %v", raw)
		}
	}
	status, body := c.get(t, "/modules/no.such.scope")
	if status != http.StatusNotFound || body["error"] != "not_found" {
		t.Fatalf("unknown module: %d %v", status, body)
	}
}

// A judgment becomes an event in the ledger and comes back on the revision. It
// changes nothing about the skill: an observation is not a decision.
func TestFeedbackBecomesALedgerEventOnTheRevision(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID, revisionID := summary["skill_id"].(string), summary["revision_id"].(string)
	path := c.skillPath(skillID) + "/revisions/" + revisionID + "/feedback"

	status, body, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: c.base + path,
		Body: map[string]any{"idempotency_key": "j1", "verdict": "helped",
			"reason": "found the right runbook", "task_id": "task-1"}, Key: "j1"})
	if status != http.StatusOK || body["judgment_id"] == nil {
		t.Fatalf("feedback: %d %v", status, body)
	}
	judgment := body["judgment_id"].(string)

	if len(c.h.Events.Events) != 1 {
		t.Fatalf("the ledger received %d events", len(c.h.Events.Events))
	}
	event := c.h.Events.Events[0]
	for key, want := range map[string]any{"event_type": "skill_feedback", "verdict": "helped",
		"skill_id": skillID, "revision": revisionID, "source": "ui", "judgment_id": judgment} {
		if event[key] != want {
			t.Fatalf("event %s is %v, want %v", key, event[key], want)
		}
	}

	revision := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+revisionID)
	entries := revision["feedback"].([]any)
	if len(entries) != 1 {
		t.Fatalf("the revision shows %d judgments", len(entries))
	}
	entry := entries[0].(map[string]any)
	if entry["judgment_id"] != judgment || entry["verdict"] != "helped" {
		t.Fatalf("feedback entry %v", entry)
	}
	// The skill itself is untouched.
	if revision["publication_status"] != "draft" {
		t.Fatalf("feedback changed the publication status to %v", revision["publication_status"])
	}

	status, body, _ = c.owner.Call(t, pivottest.Call{Method: http.MethodPost, Path: c.base + path,
		Body: map[string]any{"idempotency_key": "j2", "verdict": "excellent"}, Key: "j2"})
	if status != http.StatusBadRequest || body["error"] != "invalid_request" {
		t.Fatalf("an unknown verdict: %d %v", status, body)
	}
}

// U3.3 — organisation B cannot read organisation A's catalog, and gets the same
// answer it would get for an organisation that does not exist.
func TestAnotherOrganisationCannotReadTheCatalog(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID := summary["skill_id"].(string)
	revisionID := summary["revision_id"].(string)

	stranger := c.h.SignIn(t, "stranger", "stranger@example.test")
	stranger.CreateOrg(t, "other")
	for _, path := range []string{
		"/skills",
		"/skills/facets?field=scope",
		c.skillPath(skillID),
		c.skillPath(skillID) + "/revisions/" + revisionID,
		c.skillPath(skillID) + "/revisions/" + revisionID + "/raw",
		"/map/repository", "/map/scopes", "/map/layers", "/map/relations",
		"/modules/atlas.identity",
	} {
		status, denied, _ := stranger.Call(t, pivottest.Call{Method: http.MethodGet, Path: c.base + path})
		if status != http.StatusForbidden || denied["error"] != "forbidden" {
			t.Fatalf("%s answered %d %v to another organisation", path, status, denied)
		}
		_, unknown, _ := stranger.Call(t, pivottest.Call{Method: http.MethodGet,
			Path: strings.Replace(c.base+path, "/orgs/"+c.org+"/", "/orgs/does-not-exist/", 1)})
		if denied["message"] != unknown["message"] {
			t.Fatalf("%s distinguishes a foreign organisation from a missing one:\n %v\n %v",
				path, denied, unknown)
		}
	}
	// The stranger's own repository, with the same repo_id, is a separate and
	// empty catalog.
	stranger.CreateRepo(t, "other", "meridian", gitHost)
	page := map[string]any{}
	status, page, _ := stranger.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: pivottest.RepoBase("other", "meridian") + "/skills"})
	if status != http.StatusOK {
		t.Fatalf("the stranger's own repository: %d %v", status, page)
	}
	if items := page["items"].([]any); len(items) != 0 {
		t.Fatalf("the same repo_id in another organisation shows %d skills", len(items))
	}
}

// A member reads; nothing here is an owner-only route.
func TestAMemberCanReadTheCatalog(t *testing.T) {
	c := newCatalog(t)
	member := c.h.SignIn(t, "member", "member@example.test")
	status, invitation, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + c.org + "/invitations",
		Body: map[string]any{"email": "member@example.test", "role": "member"}, Key: "invite"})
	if status != http.StatusCreated {
		t.Fatalf("invite: %d %v", status, invitation)
	}
	accept := invitation["accept_url"].(string)
	accept = accept[strings.Index(accept, "/api/v1/"):]
	if status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: accept, Key: "accept"}); status != http.StatusOK {
		t.Fatalf("accept: %d %v", status, body)
	}
	status, page, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: c.base + "/skills"})
	if status != http.StatusOK || len(page["items"].([]any)) == 0 {
		t.Fatalf("a member cannot read the catalog: %d %v", status, page)
	}
}

// A cursor that did not come from a previous page is an error, not a silent
// restart: paging that quietly begins again loses rows.
func TestAMalformedCursorIsRejected(t *testing.T) {
	c := newCatalog(t)
	status, body := c.get(t, "/skills?cursor=not-a-cursor")
	if status != http.StatusBadRequest || body["error"] != "invalid_cursor" {
		t.Fatalf("%d %v", status, body)
	}
}
