package domain

import (
	"encoding/json"
	"path"
	"sort"
	"strings"
)

// InventoryFormat is what tools/worker/build_tree.py writes next to the
// snapshot: one row per parsed SKILL.md plus the files it could not parse.
const InventoryFormat = "guidefold-import-inventory-v1"

// InventorySkill is one parsed SKILL.md, exactly as the trusted Python builder
// reports it. Frontmatter parsing is the CLI's own, so the importer never has a
// second implementation that could drift from the ranker's.
type InventorySkill struct {
	Path             string          `json:"path"`
	URN              string          `json:"urn"`
	Name             string          `json:"name"`
	Scope            string          `json:"scope"`
	Owner            *string         `json:"owner"`
	Layer            *string         `json:"layer"`
	Status           *string         `json:"status"`
	Kind             *string         `json:"kind"`
	Generated        bool            `json:"generated"`
	Description      string          `json:"description"`
	Requires         []string        `json:"requires"`
	Refines          []string        `json:"refines"`
	Replaces         []string        `json:"replaces"`
	References       []string        `json:"references"`
	Triggers         []string        `json:"triggers"`
	NegativeTriggers []string        `json:"negative_triggers"`
	SHA256           string          `json:"sha256"`
	Size             int64           `json:"size"`
	Frontmatter      json.RawMessage `json:"frontmatter"`
}

// InventoryError is one SKILL.md the builder could not parse. One broken file
// never fails the import: it fails on its own and the rest are accepted (U2.1).
type InventoryError struct {
	Path  string `json:"path"`
	Error string `json:"error"`
}

// Inventory is the whole file.
type Inventory struct {
	Format   string           `json:"format"`
	RepoID   string           `json:"repo_id"`
	Revision string           `json:"revision"`
	Skills   []InventorySkill `json:"skills"`
	Errors   []InventoryError `json:"errors"`
	// GeneratedSkipped names the SKILL.md files the builder left out because
	// their frontmatter says `generated: true`. The snapshot has no card for
	// them (Index.build excludes generated skills), so a row in Skills would put
	// a skill in gfm.skills that SEARCH can never return. Named rather than
	// silent: finding one in an imported tree means a generated file was
	// committed, which ADR-0012 says should not happen.
	GeneratedSkipped []string `json:"generated_skipped"`
}

// OwnerOrEmpty, LayerOrEmpty and StatusOrEmpty read the optional frontmatter
// fields without inventing a value: an absent owner stays absent.
func (s *InventorySkill) OwnerOrEmpty() string  { return deref(s.Owner) }
func (s *InventorySkill) LayerOrEmpty() string  { return deref(s.Layer) }
func (s *InventorySkill) StatusOrEmpty() string { return deref(s.Status) }

func deref(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// Directory is the skill package's directory, the prefix its resources share.
func (s *InventorySkill) Directory() string {
	if i := strings.LastIndex(s.Path, "/"); i >= 0 {
		return s.Path[:i]
	}
	return ""
}

// Node is one scope of the built snapshot: the guidefold.yaml mapping the
// builder resolved, not a guess from directory depth.
type Node struct {
	Owner    *string  `json:"owner"`
	Paths    []string `json:"paths"`
	Subteams []string `json:"subteams"`
}

// Snapshot is the envelope tools/worker/build_tree.py writes. The importer
// reads only the scope map from it; building and publishing the serving
// snapshot belongs to the publication module.
type Snapshot struct {
	SHA256   string `json:"sha256"`
	Snapshot struct {
		Format   string          `json:"format"`
		RepoID   string          `json:"repo_id"`
		Revision string          `json:"revision"`
		CLISHA   string          `json:"cli_sha256"`
		Nodes    map[string]Node `json:"nodes"`
		Source   string          `json:"source"`
	} `json:"snapshot"`
}

// ScopeOf maps a repository path to the most specific scope that claims it.
// The node paths are guidefold.yaml globs; the longest literal prefix wins,
// which is the same "deepest node first" rule the CLI applies. An unmatched
// path has no scope rather than a guessed one.
func ScopeOf(nodes map[string]Node, filePath string) string {
	best, bestLen := "", -1
	for name, node := range nodes {
		for _, glob := range node.Paths {
			prefix := literalPrefix(glob)
			if prefix == "" {
				// "**" claims the whole repository; it only wins when nothing
				// more specific does.
				if bestLen < 0 {
					best, bestLen = name, 0
				}
				continue
			}
			if !strings.HasPrefix(filePath, prefix) {
				continue
			}
			if len(prefix) > bestLen || (len(prefix) == bestLen && name > best) {
				best, bestLen = name, len(prefix)
			}
		}
	}
	return best
}

func literalPrefix(glob string) string {
	if i := strings.IndexAny(glob, "*?["); i >= 0 {
		glob = glob[:i]
	}
	return glob
}

// ParentScope is the dotted parent of a scope, or "" for a root node.
func ParentScope(scope string) string {
	if i := strings.LastIndex(scope, "."); i > 0 {
		return scope[:i]
	}
	return ""
}

// Resource is one file of a skill package (U1.7): path, hash, size, type and
// whether the frontmatter declares it required.
type Resource struct {
	Path      string
	SHA256    string
	Size      int64
	Type      string
	Required  bool
	Available bool
}

// ResourcesFor lists the package files of one skill: every manifest file under
// the skill's directory except the SKILL.md itself, plus any path the
// frontmatter's references/scripts name inside that directory. A declared file
// that the scan did not carry is listed as required and unavailable rather than
// dropped, because a missing required resource has to block publication instead
// of disappearing (U1.7, U5.5).
func ResourcesFor(skill *InventorySkill, declared []string, files []File) []Resource {
	dir := skill.Directory()
	prefix := dir + "/"
	// What the scan actually carried inside this package, and which of the
	// package's own directories it carried anything from.
	carried := map[string]bool{}
	// Only directories *below* the package root: a bare name like `WORKSPACE`
	// is as likely to be a repository file as a package file, so it counts only
	// when the scan actually carried it.
	carriedDir := map[string]bool{}
	for _, f := range files {
		if !strings.HasPrefix(f.Path, prefix) {
			continue
		}
		carried[f.Path] = true
		for d := path.Dir(f.Path); strings.HasPrefix(d, prefix); d = path.Dir(d) {
			carriedDir[d] = true
		}
	}
	required := map[string]bool{}
	for _, ref := range declared {
		ref = strings.TrimSpace(ref)
		if ref == "" {
			continue
		}
		if i := strings.IndexByte(ref, '#'); i >= 0 { // "pool.go#maxConns" names a symbol
			ref = ref[:i]
		}
		resolved := ref
		if !strings.HasPrefix(ref, prefix) {
			// A reference is normally written relative to the skill directory;
			// a repository-relative one that points elsewhere is a document,
			// not a package resource, and is skipped here.
			resolved = path.Join(dir, ref)
			if !strings.HasPrefix(resolved, prefix) {
				continue
			}
		}
		// A declared path only counts as a *package* resource when it is one:
		// either the scan carried it, or it sits in a directory of the package
		// the scan did carry. `metadata.references` is also used to point at
		// repository files a reader should open — `libs/db/pool.go`, `WORKSPACE`
		// — and joining those under the package would invent a path that exists
		// nowhere and then block publication on its absence (U1.7).
		if !carried[resolved] && !carriedDir[path.Dir(resolved)] {
			continue
		}
		required[resolved] = true
	}
	byPath := map[string]Resource{}
	for _, f := range files {
		if !strings.HasPrefix(f.Path, prefix) || f.Path == skill.Path {
			continue
		}
		byPath[f.Path] = Resource{Path: f.Path, SHA256: f.SHA256, Size: f.Size,
			Type: resourceType(f.Path), Required: required[f.Path], Available: true}
	}
	for p := range required {
		if _, ok := byPath[p]; !ok {
			byPath[p] = Resource{Path: p, Type: resourceType(p), Required: true, Available: false}
		}
	}
	out := make([]Resource, 0, len(byPath))
	for _, r := range byPath {
		out = append(out, r)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out
}

// resourceType names the package role of a file: the well-known directory it
// sits in, else its extension. It is a label for the reader, not a policy.
func resourceType(p string) string {
	for _, dir := range []string{"references", "scripts", "assets"} {
		if strings.Contains(p, "/"+dir+"/") {
			return dir
		}
	}
	if ext := path.Ext(p); ext != "" {
		return strings.TrimPrefix(ext, ".")
	}
	return "file"
}
