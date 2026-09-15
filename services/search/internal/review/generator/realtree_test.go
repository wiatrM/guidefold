package generator

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// Real-tree harness for the deterministic consolidation rules.
//
// It is skipped unless GUIDEFOLD_REAL_TREE names a checkout, because a test
// that reads a working tree is a measurement, not a regression: the numbers it
// prints belong in a report next to the command that produced them
// (eval-evidence-rules), and CI must not fail because somebody edited a
// SKILL.md. Every rule it exercises has its own planted-tree test next to it.
//
//	GUIDEFOLD_REAL_TREE=$PWD go test ./internal/review/generator -run RealTree -v
//
// The harness reproduces the plan's input exactly: `.agents/skills/*/SKILL.md`
// of one repository become one `_root` group, ordered by skill id as
// `skillsByScope` orders it (`ORDER BY s.scope,s.skill_id`, and skill_id is the
// URN text, so the order is alphabetical by skill name), and cut to
// max_neighbours.
func realTreeSkills(t *testing.T, root string) []Skill {
	t.Helper()
	dirs, e := filepath.Glob(filepath.Join(root, ".agents", "skills", "*", "SKILL.md"))
	if e != nil {
		t.Fatalf("glob: %v", e)
	}
	out := []Skill{}
	for _, p := range dirs {
		raw, e := os.ReadFile(p)
		if e != nil {
			t.Fatalf("read %s: %v", p, e)
		}
		name := filepath.Base(filepath.Dir(p))
		sum := sha256.Sum256(raw)
		rel, _ := filepath.Rel(root, p)
		out = append(out, Skill{
			SkillID: "urn:skill:cloudfloo:_root:" + name,
			Path:    rel, SHA256: hex.EncodeToString(sum[:]),
			Name: name, Description: name, Scope: "_root",
			Body: string(raw),
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].SkillID < out[j].SkillID })
	return out
}

func TestRealTreeConsolidation(t *testing.T) {
	root := os.Getenv("GUIDEFOLD_REAL_TREE")
	if root == "" {
		t.Skip("set GUIDEFOLD_REAL_TREE=<checkout> to measure a real repository tree")
	}
	all := realTreeSkills(t, root)
	t.Logf("skills under .agents/skills: %d", len(all))

	procedures := 0
	for _, s := range all {
		n := 0
		for _, sec := range Split(s.Body) {
			if RoleOf(sec.Heading) == RoleSteps {
				n += len(Items(sec))
			}
		}
		if n >= minSharedSteps {
			procedures++
		}
	}
	t.Logf("skills with >=%d parsed steps: %d", minSharedSteps, procedures)

	limits := Limits{MaxProposals: 5, MaxNeighbours: 10}
	ids := make([]string, len(all))
	for i := range all {
		ids[i] = all[i].SkillID
	}
	order := NeighbourOrder(ids)
	if len(order) > limits.MaxNeighbours {
		order = order[:limits.MaxNeighbours]
	}
	group := []Skill{}
	for _, i := range order {
		group = append(group, all[i])
	}
	sort.Slice(group, func(a, b int) bool { return group[a].SkillID < group[b].SkillID })
	names := []string{}
	for _, s := range group {
		names = append(names, strings.TrimPrefix(s.SkillID, "urn:skill:cloudfloo:_root:"))
	}
	t.Logf("group presented to consolidation (%d of %d): %s", len(group), len(all), strings.Join(names, ", "))

	d := &Deterministic{}
	out := d.consolidate(Request{Kind: KindConsolidation, Scope: "_root", Owner: "",
		Skills: group, Limits: limits})
	t.Logf("candidates: %d  abstentions: %d", len(out.Candidates), len(out.Abstentions))
	for _, a := range out.Abstentions {
		t.Logf("  abstention %s %v: %s", a.Reason, a.Skills, a.Detail)
	}
	for _, c := range out.Candidates {
		t.Logf("  candidate %q scope=%s path=%s sources=%d identity=%s",
			c.Name, c.Scope, c.Path, len(c.Sources), c.Identity)
		for _, s := range c.Sources {
			t.Logf("    source %s %s", s.Path, s.SHA256[:12])
		}
		for _, r := range c.Relations {
			t.Logf("    relation %s to=%s from=%s", r.Type, r.To, r.From)
		}
		t.Logf("---- body ----\n%s---- end ----", c.Body)
	}
	fmt.Fprintln(os.Stderr)
}
