package domain_test

import (
	"encoding/json"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
)

// The domain rules are tested without a database, an HTTP server or a Python
// interpreter: they are decisions, and a decision that needs I/O to be checked
// is in the wrong layer.

// The canonical encoding has to match the CLI's `_canonical_json` byte for byte:
// the client's idempotency key and the server's manifest_digest are the same
// value computed on two machines, and Go's own encoder is not the same encoder.
// Each expectation below was produced by Python's
// json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":")).
func TestCanonicalJSONMatchesThePythonEncoder(t *testing.T) {
	for _, x := range []struct{ name, input, want string }{
		{"keys are sorted", `{"b": 1, "a": "x"}`, `{"a":"x","b":1}`},
		{"nested and null", `{"z": [1, 2, {"k": null}], "a": true}`,
			`{"a":true,"z":[1,2,{"k":null}]}`},
		// The two-line form keeps the literal control bytes out of this file:
		// the input is JSON-escaped, and so is the expected output.
		{"control characters",
			`{"s": "quote\" back\\ tab\t nl\n cr\r bs\b ff\f nul\u0000 ctrl\u001f"}`,
			`{"s":"quote\" back\\ tab\t nl\n cr\r bs\b ff\f nul\u0000 ctrl\u001f"}`},
		{"non-ASCII stays UTF-8",
			`{"unicode": "\u017c\u00f3\u0142\u0107 \u2014 \u2713 \u2028"}`,
			"{\"unicode\":\"\u017c\u00f3\u0142\u0107 \u2014 \u2713 \u2028\"}"},
		{"HTML characters are not escaped", `{"html": "<a & b>"}`, `{"html":"<a & b>"}`},
		{"numbers are verbatim", `{"n": [0, -1, 1000000, 1.5]}`, `{"n":[0,-1,1000000,1.5]}`},
	} {
		t.Run(x.name, func(t *testing.T) {
			got, e := domain.CanonicalJSON([]byte(x.input))
			if e != nil {
				t.Fatal(e)
			}
			if string(got) != x.want {
				t.Fatalf("got  %q\nwant %q", got, x.want)
			}
		})
	}
}

// The digest is stable across formatting: the same document, differently
// spaced, is the same tree.
func TestManifestDigestIgnoresFormatting(t *testing.T) {
	a, e := domain.ManifestDigest([]byte(`{"a":1,"b":[2,3]}`))
	if e != nil {
		t.Fatal(e)
	}
	b, e := domain.ManifestDigest([]byte("{\n  \"b\" : [ 2, 3 ],\n  \"a\": 1\n}"))
	if e != nil {
		t.Fatal(e)
	}
	if a != b {
		t.Fatalf("%s != %s", a, b)
	}
	if len(a) != 64 {
		t.Fatalf("digest %q", a)
	}
}

func manifest(t *testing.T, files string) *domain.Manifest {
	t.Helper()
	raw := `{"format":"guidefold-import-manifest-v1","org":"acme","repo":"mono",
 "commit":null,"complete":true,"dirty":false,"cli_version":"t","scan_profile":"default",
 "root":".","files":` + files + `,"excluded":[],"aliases":[],"suggestions":[],
 "limits":{"max_files":10,"max_bytes":100}}`
	m, e := domain.ParseManifest([]byte(raw))
	if e != nil {
		t.Fatal(e)
	}
	return m
}

const goodSHA = "0000000000000000000000000000000000000000000000000000000000000001"

func TestManifestValidationNamesWhatIsWrong(t *testing.T) {
	for _, x := range []struct{ name, files, code string }{
		{"a path that escapes the tree",
			`[{"path":"../etc/passwd","sha256":"` + goodSHA + `","size":1,"kind":"skill","mode":"100644"}]`,
			"invalid_request"},
		{"an absolute path",
			`[{"path":"/etc/passwd","sha256":"` + goodSHA + `","size":1,"kind":"skill","mode":"100644"}]`,
			"invalid_request"},
		{"a digest that is not sha256",
			`[{"path":"a","sha256":"abc","size":1,"kind":"skill","mode":"100644"}]`,
			"invalid_request"},
		{"an unknown kind",
			`[{"path":"a","sha256":"` + goodSHA + `","size":1,"kind":"binary","mode":"100644"}]`,
			"invalid_request"},
		{"the same path twice",
			`[{"path":"a","sha256":"` + goodSHA + `","size":1,"kind":"skill","mode":"100644"},
			  {"path":"a","sha256":"` + goodSHA + `","size":2,"kind":"skill","mode":"100644"}]`,
			"invalid_request"},
		{"a file over the blob limit",
			`[{"path":"a","sha256":"` + goodSHA + `","size":9000000,"kind":"skill","mode":"100644"}]`,
			"limit_exceeded"},
	} {
		t.Run(x.name, func(t *testing.T) {
			e := manifest(t, x.files).Validate("mono")
			var fault *domain.Fault
			if e == nil {
				t.Fatal("accepted")
			}
			if !asFault(e, &fault) || fault.Code != x.code {
				t.Fatalf("%v", e)
			}
		})
	}
	good := manifest(t, `[{"path":"a/b.md","sha256":"`+goodSHA+`","size":1,"kind":"document","mode":"100644"}]`)
	if e := good.Validate("mono"); e != nil {
		t.Fatalf("a valid manifest was refused: %v", e)
	}
	if e := good.Validate("other"); e == nil {
		t.Fatal("a manifest scanned for another repository was accepted")
	}
}

func asFault(e error, out **domain.Fault) bool {
	f, ok := e.(*domain.Fault)
	if ok {
		*out = f
	}
	return ok
}

// Only a hash the manifest lists may be uploaded. This is the rule that keeps
// excluded content out of the store (U1.3).
func TestWantsOnlyListsTheManifestsOwnDigests(t *testing.T) {
	m := manifest(t, `[{"path":"a","sha256":"`+goodSHA+`","size":1,"kind":"skill","mode":"100644"}]`)
	if !m.Wants(goodSHA) {
		t.Fatal("the manifest does not want its own file")
	}
	if m.Wants("0000000000000000000000000000000000000000000000000000000000000002") {
		t.Fatal("the manifest wants a digest it does not list")
	}
}

// publish defaults to true; only an explicit false suppresses the publication.
func TestPublishDefaultsToTrue(t *testing.T) {
	if !manifest(t, "[]").Publishes() {
		t.Fatal("a manifest without publish did not publish")
	}
	m, e := domain.ParseManifest([]byte(`{"format":"guidefold-import-manifest-v1","org":"a","repo":"b",
 "commit":null,"complete":true,"dirty":false,"cli_version":"t","scan_profile":"d","root":".",
 "files":[],"excluded":[],"aliases":[],"suggestions":[],"limits":{"max_files":1,"max_bytes":1},
 "publish":false}`))
	if e != nil {
		t.Fatal(e)
	}
	if m.Publishes() {
		t.Fatal("publish:false still published")
	}
}

// A revision id is derived, not minted: the same skill and the same bytes are
// the same revision however often the import runs (U1.5).
func TestRevisionIDIsDerivedFromIdentityAndBytes(t *testing.T) {
	a := domain.RevisionID("urn:skill:x:y:z", goodSHA)
	if a != domain.RevisionID("urn:skill:x:y:z", goodSHA) {
		t.Fatal("the same skill and bytes produced two revision ids")
	}
	if a == domain.RevisionID("urn:skill:x:y:other", goodSHA) {
		t.Fatal("two skills with identical bytes share a revision id")
	}
	if len(a) != 64 {
		t.Fatalf("revision id %q", a)
	}
}

func TestDriftRules(t *testing.T) {
	published := domain.SkillState{SkillID: "s1", Path: "p1", ContentSHA256: "old",
		PublicationStatus: domain.StatusPublished, CurrentRevisionID: "r0"}
	draft := domain.SkillState{SkillID: "s2", Path: "p2", ContentSHA256: "old",
		PublicationStatus: domain.StatusDraft, CurrentRevisionID: "r1"}
	changed := domain.ParsedSkill{SkillID: "s1", Path: "p1", ContentSHA256: "new", RevisionID: "r2"}
	same := domain.ParsedSkill{SkillID: "s1", Path: "p1", ContentSHA256: "old", RevisionID: "r0"}

	t.Run("an unchanged source is not an observation", func(t *testing.T) {
		if got := domain.Drift([]domain.SkillState{published}, []domain.ParsedSkill{same}, true, "i"); len(got) != 0 {
			t.Fatalf("%v", got)
		}
	})
	t.Run("a changed published source needs review", func(t *testing.T) {
		got := domain.Drift([]domain.SkillState{published}, []domain.ParsedSkill{changed}, true, "i1")
		if len(got) != 1 || got[0].Reason != domain.ReasonSourceChanged {
			t.Fatalf("%v", got)
		}
		if got[0].PublicationStatus != domain.StatusNeedsReview || got[0].RevisionID != "r2" {
			t.Fatalf("%v", got[0])
		}
		if got[0].Evidence["import_id"] != "i1" {
			t.Fatalf("evidence %v", got[0].Evidence)
		}
	})
	t.Run("a changed draft is not a question for the owner", func(t *testing.T) {
		altered := domain.ParsedSkill{SkillID: "s2", Path: "p2", ContentSHA256: "new", RevisionID: "r3"}
		if got := domain.Drift([]domain.SkillState{draft}, []domain.ParsedSkill{altered}, true, "i"); len(got) != 0 {
			t.Fatalf("%v", got)
		}
	})
	t.Run("a complete scan archives what is gone", func(t *testing.T) {
		got := domain.Drift([]domain.SkillState{published}, nil, true, "i")
		if len(got) != 1 || got[0].Reason != domain.ReasonSourceRemoved {
			t.Fatalf("%v", got)
		}
		if got[0].PublicationStatus != domain.StatusArchived || got[0].SourceStatus != "removed" {
			t.Fatalf("%v", got[0])
		}
		if got[0].RevisionID != "r0" {
			t.Fatalf("a removal must name the revision it removed, got %q", got[0].RevisionID)
		}
	})
	t.Run("a partial scan removes nothing", func(t *testing.T) {
		if got := domain.Drift([]domain.SkillState{published}, nil, false, "i"); len(got) != 0 {
			t.Fatalf("%v", got)
		}
	})
	t.Run("an already archived skill is not archived twice", func(t *testing.T) {
		archived := published
		archived.PublicationStatus = domain.StatusArchived
		if got := domain.Drift([]domain.SkillState{archived}, nil, true, "i"); len(got) != 0 {
			t.Fatalf("%v", got)
		}
	})
}

// A package resource is a file under the skill's own directory; a reference the
// frontmatter declares is required, and one that was not carried is required
// and unavailable rather than dropped (U1.7).
func TestResourcesForOneSkillPackage(t *testing.T) {
	skill := &domain.InventorySkill{Path: ".agents/skills/x/SKILL.md"}
	files := []domain.File{
		{Path: ".agents/skills/x/SKILL.md", SHA256: goodSHA, Size: 10},
		{Path: ".agents/skills/x/references/a.md", SHA256: goodSHA, Size: 20},
		{Path: ".agents/skills/x/scripts/run.sh", SHA256: goodSHA, Size: 30},
		{Path: "docs/elsewhere.md", SHA256: goodSHA, Size: 40},
		{Path: "libs/db/README.md", SHA256: goodSHA, Size: 50},
	}
	declared := []string{"references/a.md", "references/missing.md#anchor", "../../../docs/elsewhere.md",
		"libs/db/README.md", "libs/db/pool.go", "WORKSPACE"}
	got := domain.ResourcesFor(skill, declared, files)

	byPath := map[string]domain.Resource{}
	for _, r := range got {
		byPath[r.Path] = r
	}
	if len(byPath) != 3 {
		t.Fatalf("resources %v", got)
	}
	if r := byPath[".agents/skills/x/references/a.md"]; !r.Required || !r.Available || r.Type != "references" {
		t.Fatalf("declared reference %+v", r)
	}
	if r := byPath[".agents/skills/x/scripts/run.sh"]; r.Required || !r.Available || r.Type != "scripts" {
		t.Fatalf("undeclared package file %+v", r)
	}
	if r := byPath[".agents/skills/x/references/missing.md"]; !r.Required || r.Available {
		t.Fatalf("a declared file that was not carried must be required and unavailable: %+v", r)
	}
	if _, ok := byPath["docs/elsewhere.md"]; ok {
		t.Fatal("a repository document became a package resource")
	}
	// A repository-relative reference is a document the skill points at, whether
	// or not the scan carried it. Joining it under the package would invent a
	// path that exists nowhere and block publication on its absence (U1.7).
	for _, phantom := range []string{".agents/skills/x/libs/db/README.md",
		".agents/skills/x/libs/db/pool.go", ".agents/skills/x/WORKSPACE"} {
		if _, ok := byPath[phantom]; ok {
			t.Fatalf("%s became a phantom package resource: %v", phantom, got)
		}
	}
	if skill.Directory() != ".agents/skills/x" {
		t.Fatalf("directory %q", skill.Directory())
	}
}

// A path is mapped to the most specific node that claims it, and an unclaimed
// path has no scope rather than a guessed one.
func TestScopeOfPrefersTheMostSpecificNode(t *testing.T) {
	nodes := map[string]domain.Node{
		"_root":         {Paths: []string{"**"}},
		"atlas":         {Paths: []string{"platforms/atlas/**"}},
		"atlas.geo":     {Paths: []string{"platforms/atlas/geo/**"}},
		"shared":        {Paths: []string{"libs/**"}},
		"emptyPathNode": {},
	}
	for path, want := range map[string]string{
		"platforms/atlas/geo/a.md": "atlas.geo",
		"platforms/atlas/a.md":     "atlas",
		"libs/auth/a.md":           "shared",
		"README.md":                "_root",
	} {
		if got := domain.ScopeOf(nodes, path); got != want {
			t.Fatalf("%s mapped to %q, want %q", path, got, want)
		}
	}
	if got := domain.ScopeOf(map[string]domain.Node{"a": {Paths: []string{"x/**"}}}, "y/z"); got != "" {
		t.Fatalf("an unclaimed path was given the scope %q", got)
	}
	if got := domain.ParentScope("atlas.identity.turnstile"); got != "atlas.identity" {
		t.Fatalf("parent %q", got)
	}
	if got := domain.ParentScope("_root"); got != "" {
		t.Fatalf("a root node has the parent %q", got)
	}
}

// An alias maps the new path to the path it replaces, which is what lets a
// rename keep its identity.
func TestAliasTargets(t *testing.T) {
	raw := `{"format":"guidefold-import-manifest-v1","org":"a","repo":"b","commit":null,
 "complete":true,"dirty":false,"cli_version":"t","scan_profile":"d","root":".","files":[],
 "excluded":[],"aliases":[{"from":"old/SKILL.md","to":"new/SKILL.md"}],"suggestions":[],
 "limits":{"max_files":1,"max_bytes":1}}`
	m, e := domain.ParseManifest([]byte(raw))
	if e != nil {
		t.Fatal(e)
	}
	if got := m.AliasTargets()["new/SKILL.md"]; got != "old/SKILL.md" {
		t.Fatalf("alias %q", got)
	}
}

// A field this server does not model is a client bug, not a setting to ignore.
func TestUnknownManifestFieldIsRefused(t *testing.T) {
	_, e := domain.ParseManifest([]byte(`{"format":"guidefold-import-manifest-v1","surprise":1}`))
	if e == nil {
		t.Fatal("an unknown field was accepted")
	}
}

// The inventory the builder writes decodes into the domain's own view of it.
func TestInventoryDecodes(t *testing.T) {
	var inv domain.Inventory
	raw := `{"format":"guidefold-import-inventory-v1","repo_id":"r","revision":"c",
 "skills":[{"path":"a/SKILL.md","urn":"urn:skill:p:n:a","name":"a","scope":"n","owner":"t",
   "layer":"team","status":"active","kind":null,"generated":false,"description":"d",
   "requires":["urn:skill:p:n:b"],"refines":[],"replaces":[],"references":[],"triggers":[],
   "negative_triggers":[],"sha256":"` + goodSHA + `","size":1,"frontmatter":{"name":"a"}}],
 "errors":[{"path":"b/SKILL.md","error":"ParserError: boom"}]}`
	if e := json.Unmarshal([]byte(raw), &inv); e != nil {
		t.Fatal(e)
	}
	if inv.Format != domain.InventoryFormat || len(inv.Skills) != 1 || len(inv.Errors) != 1 {
		t.Fatalf("%+v", inv)
	}
	s := inv.Skills[0]
	if s.OwnerOrEmpty() != "t" || s.LayerOrEmpty() != "team" || s.StatusOrEmpty() != "active" {
		t.Fatalf("%+v", s)
	}
	if s.Kind != nil {
		t.Fatalf("an absent kind became %v", *s.Kind)
	}
}
