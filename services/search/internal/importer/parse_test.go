package importer_test

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// The worker tests run the real tools/worker/build_tree.py over a real
// materialised tree. They are the only place the import pipeline is proved end
// to end: a fake builder would prove that the Go code calls something, not that
// the catalog matches what the ranker's own parser sees.

// fixtureSkills is how many skills the Meridian fixture puts in the catalog. Its tree holds 27
// SKILL.md files; the 27th is the generated hierarchy index, which build_tree.py reports under
// `generated_skipped` instead of as an inventory row, because Index.build makes no card for it
// and a catalog row without a card is a skill SEARCH can never return (W3).
const fixtureSkills = 26

type parsed struct {
	*fixture
	scratch  string
	importID string
}

func newParsed(t *testing.T, complete bool) *parsed {
	t.Helper()
	f := newFixture(t)
	scratch := pivottest.Scratch(t, "parse")
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, complete), "first")
	if ran := f.h.RunParse(t, scratch); ran != 1 {
		t.Fatalf("the worker ran %d parse jobs, want 1", ran)
	}
	return &parsed{fixture: f, scratch: scratch, importID: importID}
}

func (p *parsed) status(t *testing.T) map[string]any {
	t.Helper()
	status, body, _ := p.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: p.base + "/imports/" + p.importID})
	if status != http.StatusOK {
		t.Fatalf("import status: %d %v", status, body)
	}
	return body
}

func (p *parsed) count(t *testing.T, query string, args ...any) int {
	t.Helper()
	var n int
	if e := p.h.Pool.QueryRow(context.Background(), query, args...).Scan(&n); e != nil {
		t.Fatal(e)
	}
	return n
}

// U4.1 — every skill of the fixture reaches the catalog with its scope and
// owner, and the import reports itself ready.
func TestParsingTheFixtureFillsTheCatalog(t *testing.T) {
	p := newParsed(t, true)
	view := p.status(t)
	if view["state"] != "ready" {
		t.Fatalf("state %v (error %v)", view["state"], view["error"])
	}
	counts := view["counts"].(map[string]any)
	if counts["failed"].(float64) != 0 {
		t.Fatalf("counts %v", counts)
	}
	// 27 SKILL.md files in the tree; the 27th is the generated hierarchy index, which the
	// builder skips because Index.build makes no card for it (W3).
	if got := p.count(t, `SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, p.org); got != fixtureSkills {
		t.Fatalf("the catalog holds %d of the fixture's %d skills", got, fixtureSkills)
	}
	if got := p.count(t, `SELECT count(*) FROM gfm.skill_revisions WHERE org_id=$1::uuid`, p.org); got != fixtureSkills {
		t.Fatalf("%d revisions for %d skills", got, fixtureSkills)
	}
	// Every skill carries the scope the builder resolved, not a directory guess.
	if got := p.count(t, `SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid AND scope=''`, p.org); got != 0 {
		t.Fatalf("%d skills have no scope", got)
	}
	// The scope map came from guidefold.yaml, which declares 17 nodes.
	if got := p.count(t, `SELECT count(*) FROM gfm.scopes WHERE org_id=$1::uuid`, p.org); got != 17 {
		t.Fatalf("the scope map holds %d nodes, guidefold.yaml declares 17", got)
	}
	if got := p.count(t, `SELECT count(*) FROM gfm.documents WHERE org_id=$1::uuid`, p.org); got == 0 {
		t.Fatal("no documents were imported")
	}
	if got := p.count(t, `SELECT count(*) FROM gfm.relations
 WHERE org_id=$1::uuid AND type='requires'`, p.org); got == 0 {
		t.Fatal("no requires edges were recorded")
	}
}

// U2.1 — one broken SKILL.md fails on its own; the rest are accepted and the
// import is partial rather than failed.
func TestOneBrokenSkillFileMakesTheImportPartial(t *testing.T) {
	f := newFixture(t)
	broken := filepath.Join(f.tree, ".agents", "skills", "adr-process", "SKILL.md")
	if e := os.WriteFile(broken, []byte("---\nname: [unclosed\n---\nbody\n"), 0o644); e != nil {
		t.Fatal(e)
	}
	scratch := pivottest.Scratch(t, "partial")
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	f.h.RunParse(t, scratch)

	status, view, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/imports/" + importID})
	if status != http.StatusOK || view["state"] != "partial" {
		t.Fatalf("state %v", view["state"])
	}
	failed, accepted := 0, 0
	for _, raw := range view["files"].([]any) {
		file := raw.(map[string]any)
		switch file["status"] {
		case "failed":
			failed++
			if file["path"] != ".agents/skills/adr-process/SKILL.md" {
				t.Fatalf("the wrong file failed: %v", file)
			}
			if reason, _ := file["reason"].(string); reason == "" {
				t.Fatalf("a failed file has no reason: %v", file)
			}
		case "accepted":
			accepted++
		}
	}
	if failed != 1 || accepted < 30 {
		t.Fatalf("%d failed, %d accepted", failed, accepted)
	}
	var skills int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, f.org).Scan(&skills); e != nil {
		t.Fatal(e)
	}
	if skills != fixtureSkills-1 {
		t.Fatalf("one broken file cost %d of the %d remaining skills",
			fixtureSkills-1-skills, fixtureSkills-1)
	}
}

// U1.5 — a worker that died after a checkpoint resumes without writing a second
// copy of anything.
func TestRestartingTheParseAfterACheckpointWritesNoDuplicates(t *testing.T) {
	p := newParsed(t, true)
	tables := []string{"skills", "skill_revisions", "skill_resources", "relations",
		"documents", "scopes", "owner_queue"}
	before := map[string]int{}
	for _, table := range tables {
		before[table] = p.count(t, `SELECT count(*) FROM gfm.`+table+` WHERE org_id=$1::uuid`, p.org)
	}
	job := p.h.JobOf(t, p.importID, "import.parse")
	var checkpoint map[string]any
	if e := json.Unmarshal(job.Checkpoint, &checkpoint); e != nil {
		t.Fatalf("the finished job stored no checkpoint: %v", e)
	}
	if checkpoint["stage"] != "written" {
		t.Fatalf("checkpoint %v", checkpoint)
	}

	// Put the job back the way a killed worker leaves it: terminal write never
	// happened, checkpoint intact, tree still on disk.
	p.h.Requeue(t, p.importID)
	if _, e := p.h.Pool.Exec(context.Background(),
		`UPDATE gfm.imports SET state='queued' WHERE import_id=$1::uuid`, p.importID); e != nil {
		t.Fatal(e)
	}
	if ran := p.h.RunParse(t, p.scratch); ran != 1 {
		t.Fatalf("the restarted worker ran %d jobs", ran)
	}
	for _, table := range tables {
		got := p.count(t, `SELECT count(*) FROM gfm.`+table+` WHERE org_id=$1::uuid`, p.org)
		if got != before[table] {
			t.Fatalf("%s: %d rows after the restart, %d before", table, got, before[table])
		}
	}
	if p.status(t)["state"] != "ready" {
		t.Fatal("the restarted import did not finish")
	}
}

// U1.7 — a file under a skill directory becomes a package resource, and one the
// frontmatter names in metadata.references is required.
func TestPackageResourcesCarryTheirRequiredFlag(t *testing.T) {
	f := newFixture(t)
	dir := filepath.Join(f.tree, ".agents", "skills", "adr-process")
	if e := os.MkdirAll(filepath.Join(dir, "references"), 0o755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(dir, "references", "template.md"),
		[]byte("# ADR template\n"), 0o644); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(dir, "references", "extra.md"),
		[]byte("# Not declared\n"), 0o644); e != nil {
		t.Fatal(e)
	}
	skill := filepath.Join(dir, "SKILL.md")
	raw, e := os.ReadFile(skill)
	if e != nil {
		t.Fatal(e)
	}
	// Declare one of the two files in the frontmatter's metadata.references.
	body := strings.Replace(string(raw), "\n  status:",
		"\n  references: references/template.md\n  status:", 1)
	if body == string(raw) {
		t.Fatal("the fixture's frontmatter changed shape; the test needs updating")
	}
	if e := os.WriteFile(skill, []byte(body), 0o644); e != nil {
		t.Fatal(e)
	}

	scratch := pivottest.Scratch(t, "resources")
	pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	f.h.RunParse(t, scratch)

	rows, err := f.h.Pool.Query(context.Background(), `SELECT r.path,r.required,r.available,r.type
 FROM gfm.skill_resources r JOIN gfm.skill_revisions v
  ON v.org_id=r.org_id AND v.revision_id=r.revision_id
 WHERE r.org_id=$1::uuid AND v.source_path=$2 ORDER BY r.path`,
		f.org, ".agents/skills/adr-process/SKILL.md")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	found := map[string]bool{}
	for rows.Next() {
		var path, kind string
		var required, available bool
		if err = rows.Scan(&path, &required, &available, &kind); err != nil {
			t.Fatal(err)
		}
		found[path] = required
		if !available {
			t.Fatalf("%s was uploaded but is marked unavailable", path)
		}
		if kind != "references" {
			t.Fatalf("%s has type %q", path, kind)
		}
	}
	declared := ".agents/skills/adr-process/references/template.md"
	extra := ".agents/skills/adr-process/references/extra.md"
	if required, ok := found[declared]; !ok || !required {
		t.Fatalf("the declared reference is %v (present: %v)", required, ok)
	}
	if required, ok := found[extra]; !ok || required {
		t.Fatalf("the undeclared file is required=%v (present: %v)", required, ok)
	}
}

// ADR-0050 (owner decision 2026-09-15): a tree without guidefold.yaml is
// imported, not rejected. The scope map is inferred from the tree's own skill
// directories (and CODEOWNERS, when it has one) by the same cli.infer_map
// every guidefold command uses, and gfm.scopes records source='inferred'.
// This test asserted the opposite ("fails the import") until that decision.
func TestATreeWithoutTheScopeMapIsImportedWithAnInferredMap(t *testing.T) {
	f := newFixture(t)
	if e := os.Remove(filepath.Join(f.tree, "guidefold.yaml")); e != nil {
		t.Fatal(e)
	}
	scratch := pivottest.Scratch(t, "noconfig")
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	f.h.RunParse(t, scratch)

	_, view, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/imports/" + importID})
	if view["state"] != "ready" {
		t.Fatalf("state %v (%v), want ready", view["state"], view["error"])
	}
	var skills int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, f.org).Scan(&skills); e != nil {
		t.Fatal(e)
	}
	if skills == 0 {
		t.Fatal("an inferred import wrote no skills")
	}
	// Every scope this import stored is marked as inferred, and the node names
	// follow the directories (platforms.atlas), not the names guidefold.yaml
	// gave them (atlas) — that difference is the point of writing the file.
	var declared, inferred int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT
 count(*) FILTER (WHERE source='guidefold_yaml'), count(*) FILTER (WHERE source='inferred')
 FROM gfm.scopes WHERE org_id=$1::uuid`, f.org).Scan(&declared, &inferred); e != nil {
		t.Fatal(e)
	}
	if declared != 0 || inferred == 0 {
		t.Fatalf("gfm.scopes source: %d guidefold_yaml, %d inferred", declared, inferred)
	}
	var named int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.scopes WHERE org_id=$1::uuid AND scope='platforms.atlas'`,
		f.org).Scan(&named); e != nil {
		t.Fatal(e)
	}
	if named != 1 {
		t.Fatalf("no inferred scope named after its directory (platforms.atlas): %d", named)
	}
}

// A cancelled import is skipped rather than parsed into a cancelled row.
func TestACancelledImportIsSkippedByTheWorker(t *testing.T) {
	f := newFixture(t)
	scratch := pivottest.Scratch(t, "cancel")
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports/" + importID + "/cancel",
		Body: map[string]any{"idempotency_key": "cancel"}, Key: "cancel"})
	if status != http.StatusOK {
		t.Fatalf("cancel: %d %v", status, body)
	}
	// Cancellation cancels the job too, so there is nothing left to lease.
	if ran := f.h.RunParse(t, scratch); ran != 0 {
		t.Fatalf("the worker ran %d jobs for a cancelled import", ran)
	}
	var skills int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, f.org).Scan(&skills); e != nil {
		t.Fatal(e)
	}
	if skills != 0 {
		t.Fatalf("a cancelled import wrote %d skills", skills)
	}
}

// U2.1 — gfm.skills is keyed per organisation, so a second repository whose tree
// yields the same skill ids must fail those files instead of rewriting the
// first repository's catalog rows in place.
func TestASecondRepositoryCannotOverwriteAnotherRepositorysSkill(t *testing.T) {
	p := newParsed(t, true)
	if p.status(t)["state"] != "ready" {
		t.Fatal("the first import did not finish")
	}
	p.owner.CreateRepo(t, p.org, "second", "")
	secondID := pivottest.Push(t, p.owner, p.org, "second", p.tree,
		pivottest.Manifest(t, p.tree, "acme", "second", true), "second")
	if ran := p.h.RunParse(t, pivottest.Scratch(t, "second")); ran != 1 {
		t.Fatalf("the worker ran %d parse jobs, want 1", ran)
	}

	status, view, _ := p.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: pivottest.RepoBase(p.org, "second") + "/imports/" + secondID})
	if status != http.StatusOK {
		t.Fatalf("second import status: %d %v", status, view)
	}
	if view["state"] != "partial" {
		t.Fatalf("state %v (error %v)", view["state"], view["error"])
	}
	counts := view["counts"].(map[string]any)
	if counts["failed"].(float64) != fixtureSkills {
		t.Fatalf("counts %v, want %d failed", counts, fixtureSkills)
	}
	conflicts := 0
	for _, raw := range view["files"].([]any) {
		file := raw.(map[string]any)
		if file["status"] != "failed" {
			continue
		}
		reason, _ := file["reason"].(string)
		if !strings.HasPrefix(reason, "repo_conflict: meridian already holds urn:skill:meridian:") {
			t.Fatalf("unexpected failure: %v", file)
		}
		conflicts++
	}
	if conflicts != fixtureSkills {
		t.Fatalf("%d repo_conflict files, want %d", conflicts, fixtureSkills)
	}

	if got := p.count(t, `SELECT count(*) FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id='meridian' AND last_import_id=$2::uuid`, p.org, p.importID); got != fixtureSkills {
		t.Fatalf("%d of meridian's %d skills still carry its own import", got, fixtureSkills)
	}
	if got := p.count(t, `SELECT count(*) FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id='second'`, p.org); got != 0 {
		t.Fatalf("the second repository holds %d skills, want 0", got)
	}
}
