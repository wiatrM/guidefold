package domain_test

import (
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review/domain"
)

func node(scope, parent, owner string, paths ...domain.ScopePath) domain.ScopeMapNode {
	return domain.ScopeMapNode{Scope: scope, Parent: parent, Owner: owner, Paths: paths,
		Confidence: 0.8, Reason: "the directories under it share one subject"}
}

func path(repo, p string) domain.ScopePath { return domain.ScopePath{RepoID: repo, Path: p} }

func teams(repo string, names ...string) map[string]map[string]bool {
	set := map[string]bool{}
	for _, n := range names {
		set[n] = true
	}
	return map[string]map[string]bool{repo: set}
}

func has(findings []string, substr string) bool {
	for _, f := range findings {
		if strings.Contains(f, substr) {
			return true
		}
	}
	return false
}

// A map that names a real hierarchy over two repositories is accepted. This is
// the case ADR-0051 exists for: one node collecting directories from more than
// one repository of the organisation.
func TestValidateScopeMapAcceptsCrossRepositoryHierarchy(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha", "beta"},
		Nodes: []domain.ScopeMapNode{
			node("_root", "", ""),
			node("atlas", "_root", "@acme/atlas", path("alpha", "platforms/atlas")),
			node("atlas.geo", "atlas", "@acme/atlas", path("alpha", "platforms/atlas/geo"),
				path("beta", "services/atlas-geo")),
		}}
	owners := map[string]map[string]bool{
		"alpha": {"@acme/atlas": true}, "beta": {"@acme/atlas": true}}
	if f := domain.ValidateScopeMap(m, []string{"alpha", "beta"}, owners); len(f) != 0 {
		t.Fatalf("expected a valid map, got findings %v", f)
	}
}

// The same path string in two different repositories is not a conflict. This is
// the rule a global path set would get wrong, and it is the likeliest silent
// way to write rows for the wrong repository (ADR-0047 decision 4).
func TestValidateScopeMapAllowsSamePathInTwoRepositories(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginInferred, Repos: []string{"alpha", "beta"},
		Nodes: []domain.ScopeMapNode{
			node("alpha-api", "", "", path("alpha", "services/api")),
			node("beta-api", "", "", path("beta", "services/api")),
		}}
	if f := domain.ValidateScopeMap(m, []string{"alpha", "beta"}, nil); len(f) != 0 {
		t.Fatalf("expected the same path in two repositories to be fine, got %v", f)
	}
}

// The same path in the *same* repository under two nodes is rejected, and both
// claimants are named.
func TestValidateScopeMapRejectsOverlapWithinOneRepository(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginInferred, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{
			node("first", "", "", path("alpha", "services/api")),
			node("second", "", "", path("alpha", "services/api")),
		}}
	f := domain.ValidateScopeMap(m, []string{"alpha"}, nil)
	if !has(f, "claimed by both") || !has(f, "first") || !has(f, "second") {
		t.Fatalf("expected both claimants named, got %v", f)
	}
}

// A cycle is rejected and the loop is named, because a rejection has to tell an
// owner which nodes form it.
func TestValidateScopeMapNamesTheParentCycle(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{
			node("a", "b", "", path("alpha", "a")),
			node("b", "c", "", path("alpha", "b")),
			node("c", "a", "", path("alpha", "c")),
		}}
	f := domain.ValidateScopeMap(m, []string{"alpha"}, nil)
	if !has(f, "parent cycle") {
		t.Fatalf("expected a cycle finding, got %v", f)
	}
	for _, want := range []string{"a", "b", "c"} {
		if !has(f, want) {
			t.Fatalf("cycle finding does not name %q: %v", want, f)
		}
	}
}

func TestValidateScopeMapRejectsParentOutsideTheMap(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{node("a", "missing", "", path("alpha", "a"))}}
	if f := domain.ValidateScopeMap(m, []string{"alpha"}, nil); !has(f, "not in the map") {
		t.Fatalf("expected a missing-parent finding, got %v", f)
	}
}

// An owner the repository's CODEOWNERS does not name is a finding, not a silent
// pass: an owner nobody can check is exactly the uncertain owner U1 forbids
// from becoming policy.
func TestKnownOwnersAcceptsAnOwnerTheRepositoryAlreadyDeclares(t *testing.T) {
	// A repository that wrote its hierarchy in guidefold.yaml has already named
	// its owners, and that file outranks any proposal (ADR-0050). Keeping such a
	// node must not be rejected for a CODEOWNERS that never mentioned the team.
	existing := []domain.ExistingScope{{RepoID: "alpha", Scope: "a", Owner: "@acme/declared"}}
	known := domain.KnownOwners(map[string]bool{"@acme/real": true}, existing)
	m := domain.ScopeMap{Origin: domain.OriginInferred, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{node("a", "", "@acme/declared", path("alpha", "a"))}}
	if f := domain.ValidateScopeMap(m, []string{"alpha"}, map[string]map[string]bool{"alpha": known}); len(f) != 0 {
		t.Fatalf("a declared owner must be accepted, got %v", f)
	}
}

func TestValidateScopeMapRejectsAnOwnerCodeownersDoesNotName(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{node("a", "", "@acme/invented", path("alpha", "a"))}}
	f := domain.ValidateScopeMap(m, []string{"alpha"}, teams("alpha", "@acme/real"))
	if !has(f, "neither declares nor lists in CODEOWNERS") {
		t.Fatalf("expected an owner finding, got %v", f)
	}
}

func TestValidateScopeMapRejectsPathsOutsideTheOrganisation(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{node("a", "", "", path("someone-elses-repo", "a"))}}
	if f := domain.ValidateScopeMap(m, []string{"alpha"}, nil); !has(f, "not part of this organisation") {
		t.Fatalf("expected a repository finding, got %v", f)
	}
}

func TestValidateScopeName(t *testing.T) {
	for _, ok := range []string{"_root", "atlas", "atlas.identity", "atlas.auth-sdk.v2", "a1.b2"} {
		if f := domain.ValidateScopeName(ok); f != "" {
			t.Errorf("%q should be a valid node name, got %q", ok, f)
		}
	}
	// `--` breaks ADR-0008's registry id mapping, which joins the publisher,
	// the node and the name with exactly that separator.
	for _, bad := range []string{"Atlas", "atlas..identity", "atlas.-identity", "atlas.a--b",
		"atlas.ident_ity", "a.b.c.d.e.f.g", ""} {
		if f := domain.ValidateScopeName(bad); f == "" {
			t.Errorf("%q should not be a valid node name", bad)
		}
	}
}

// The diff is per (repository, node): one node spanning two repositories is two
// rows, and each is compared with the row that repository actually has.
func TestDiffScopeMapIsPerRepository(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha", "beta"},
		Nodes: []domain.ScopeMapNode{
			node("atlas", "_root", "@acme/atlas",
				path("alpha", "platforms/atlas"), path("beta", "services/atlas")),
		}}
	existing := []domain.ExistingScope{
		{RepoID: "alpha", Scope: "atlas", Parent: "_root", Owner: "@acme/old",
			Paths: []string{"platforms/atlas"}, Source: "guidefold_yaml"},
	}
	d := domain.DiffScopeMap(m, existing)
	if len(d.Added) != 1 || d.Added[0] != "beta/atlas" {
		t.Fatalf("expected only beta/atlas added, got %v", d.Added)
	}
	if len(d.OwnerChanged) != 1 || d.OwnerChanged[0].RepoID != "alpha" ||
		d.OwnerChanged[0].From != "@acme/old" || d.OwnerChanged[0].To != "@acme/atlas" {
		t.Fatalf("expected one owner change on alpha, got %+v", d.OwnerChanged)
	}
	if len(d.PathsChanged) != 0 {
		t.Fatalf("alpha's paths did not move, got %+v", d.PathsChanged)
	}
}

// A scope the map does not mention is not a removal and has no list: approving
// never deletes a row (API-CONTRACT §6).
func TestDiffScopeMapNeverReportsARemoval(t *testing.T) {
	m := domain.ScopeMap{Origin: domain.OriginModel, Repos: []string{"alpha"},
		Nodes: []domain.ScopeMapNode{node("kept", "", "", path("alpha", "kept"))}}
	existing := []domain.ExistingScope{
		{RepoID: "alpha", Scope: "kept", Paths: []string{"kept"}},
		{RepoID: "alpha", Scope: "forgotten", Paths: []string{"forgotten"}},
	}
	d := domain.DiffScopeMap(m, existing)
	if d.Unchanged != 1 {
		t.Fatalf("expected the kept node to count as unchanged, got %d", d.Unchanged)
	}
	if len(d.Added) != 0 || len(d.Reparented) != 0 || len(d.PathsChanged) != 0 {
		t.Fatalf("expected no change at all, got %+v", d)
	}
}
