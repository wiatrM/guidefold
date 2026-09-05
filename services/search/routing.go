package main

import (
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"

	"golang.org/x/text/unicode/norm"
)

const scale int64 = 1 << 20
const backend = "router_bm25f_v1"

type pathRule struct {
	node, pattern string
	re            *regexp.Regexp
	specificity   int
}
type Catalog struct {
	ID, Repo, Revision, PolicySHA, ScopeSHA string
	RouterIndexSHA                          string
	Nodes                                   M
	Weights                                 M
	Cards                                   map[string]M
	Revisions                               map[string]string
	Order                                   []string
	Negatives                               map[string][][]string
	Rules                                   []pathRule
}

func tokens(s string) []string {
	var b strings.Builder
	for _, r := range norm.NFKD.String(s) {
		if norm.NFKD.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		if r >= 'A' && r <= 'Z' {
			r += 'a' - 'A'
		}
		if r >= 'a' && r <= 'z' || r >= '0' && r <= '9' {
			b.WriteRune(r)
		} else {
			b.WriteByte(' ')
		}
	}
	return strings.Fields(b.String())
}
func globRegex(pattern string) (*regexp.Regexp, error) {
	// fnmatch-style glob: * and ? also match directory separators.
	var b strings.Builder
	b.WriteString("(?s)^")
	chars := []rune(pattern)
	for i := 0; i < len(chars); i++ {
		switch chars[i] {
		case '*':
			b.WriteString(".*")
		case '?':
			b.WriteByte('.')
		case '[':
			end := i + 1
			if end < len(chars) && (chars[end] == '!' || chars[end] == '^') {
				end++
			}
			if end < len(chars) && chars[end] == ']' {
				end++
			}
			for end < len(chars) && chars[end] != ']' {
				end++
			}
			if end == len(chars) {
				b.WriteString(`\[`)
				continue
			}
			raw := string(chars[i+1 : end])
			if strings.HasPrefix(raw, "!") {
				raw = "^" + raw[1:]
			} else if strings.HasPrefix(raw, "^") {
				raw = `\` + raw
			}
			b.WriteByte('[')
			b.WriteString(strings.ReplaceAll(raw, `\`, `\\`))
			b.WriteByte(']')
			i = end
		default:
			b.WriteString(regexp.QuoteMeta(string(chars[i])))
		}
	}
	b.WriteByte('$')
	return regexp.Compile(b.String())
}
func (c *Catalog) prepare() error {
	c.Order = keys(c.Cards)
	c.Negatives = map[string][][]string{}
	for u, card := range c.Cards {
		for _, phrase := range stringList(card["negative_triggers"]) {
			ts := tokens(phrase)
			if len(ts) > 0 {
				c.Negatives[u] = append(c.Negatives[u], ts)
			}
		}
	}
	for _, node := range keys(c.Nodes) {
		for _, p := range stringList(obj(c.Nodes[node])["paths"]) {
			re, e := globRegex(p)
			if e != nil {
				return e
			}
			c.Rules = append(c.Rules, pathRule{node, p, re, utf8.RuneCountInString(p)})
		}
	}
	c.ScopeSHA = hash(pythonJSON(c.Nodes, true))
	return nil
}
func (c *Catalog) mapPath(path string) (string, error) {
	if path == "." {
		return "_root", nil
	}
	best := -1
	wins := map[string]bool{}
	for _, r := range c.Rules {
		if r.re.MatchString(path) || r.re.MatchString(path+"/") {
			if r.specificity > best {
				best = r.specificity
				wins = map[string]bool{r.node: true}
			} else if r.specificity == best {
				wins[r.node] = true
			}
		}
	}
	if len(wins) == 0 {
		return "", fail(422, "unmapped_workspace_path")
	}
	if len(wins) > 1 {
		return "", fail(422, "ambiguous_workspace_path")
	}
	node := keys(wins)[0]
	if node == "_root" {
		only := true
		for _, p := range stringList(obj(c.Nodes[node])["paths"]) {
			if p != "*" && p != "**" {
				only = false
			}
		}
		if only {
			return "", fail(422, "unmapped_workspace_path")
		}
	}
	return node, nil
}
func (c *Catalog) resolve(p M) ([]string, M, error) {
	scopes := []string{text(p, "node", "_root")}
	source := "node"
	warnings := []string{}
	work := obj(p["workspace"])
	if work != nil {
		if str(work["repo_id"]) != c.Repo {
			return nil, nil, fail(409, "repository_mismatch")
		}
		if rev, ok := work["revision"]; ok {
			if str(rev) != c.Revision {
				return nil, nil, fail(409, "repository_revision_mismatch")
			}
		} else {
			warnings = append(warnings, "repository_revision_not_supplied")
		}
		targets := arr(work["target_paths"])
		trusted := []any{}
		for _, t := range targets {
			s := str(obj(t)["source"])
			if s == "edited" || s == "user_explicit" {
				trusted = append(trusted, t)
			}
		}
		if len(trusted) > 0 {
			targets = trusted
		}
		paths := []string{str(work["cwd"])}
		source = "cwd"
		if len(targets) > 0 {
			paths = []string{}
			source = "target_paths"
			for _, t := range targets {
				paths = append(paths, str(obj(t)["path"]))
			}
			if len(trusted) == 0 {
				warnings = append(warnings, "scope_from_inferred_paths")
			}
		}
		unique := map[string]bool{}
		for _, path := range paths {
			node, e := c.mapPath(path)
			if e != nil {
				return nil, nil, e
			}
			unique[node] = true
		}
		scopes = keys(unique)
		if len(scopes) > 4 {
			return nil, nil, fail(422, "too_many_resolved_scopes")
		}
	}
	for _, s := range scopes {
		if _, ok := c.Nodes[s]; !ok {
			return nil, nil, fail(400, "invalid_node")
		}
	}
	unused := []M{}
	for _, k := range []string{"intent", "stack", "constraints", "capabilities"} {
		if _, ok := p[k]; ok {
			unused = append(unused, M{"field": k, "reason": "ranking_signal_not_admitted"})
		}
	}
	owners := M{}
	for _, s := range scopes {
		owners[s] = obj(c.Nodes[s])["owner"]
	}
	used := []string{"node"}
	if work != nil {
		used = []string{"workspace"}
	}
	ctx := M{"resolved_scopes": scopes, "scope_source": source, "scope_owners": owners, "repository": M{"repo_id": c.Repo, "revision": c.Revision}, "scope_map_revision": c.ScopeSHA, "used_fields": used, "unused_fields": unused, "warnings": warnings, "scope_is_authorization": false}
	return scopes, ctx, nil
}
func appendContext(c M, key, value string) { c[key] = append(c[key].([]string), value) }
func (c *Catalog) allowed(node, query string) (map[string]bool, int) {
	qt := map[string]bool{}
	for _, t := range tokens(query) {
		qt[t] = true
	}
	kept := map[string]bool{}
	drops := 0
	for _, u := range c.Order {
		card := c.Cards[u]
		cn := str(card["node"])
		visible := node == "_root" || cn == "_root" || cn == node || strings.HasPrefix(cn, node+".") || strings.HasPrefix(node, cn+".")
		if str(card["status"]) == "deprecated" || !visible {
			drops++
			continue
		}
		negative := false
		for _, phrase := range c.Negatives[u] {
			all := true
			for _, t := range phrase {
				if !qt[t] {
					all = false
					break
				}
			}
			if all {
				negative = true
				break
			}
		}
		if negative {
			drops++
		} else {
			kept[u] = true
		}
	}
	return kept, drops
}
func depth(node string) int {
	if node == "_root" {
		return 0
	}
	return strings.Count(node, ".") + 1
}
func hops(skill, caller string) int {
	if skill == caller {
		return 0
	}
	if skill == "_root" {
		return depth(caller)
	}
	if strings.HasPrefix(caller, skill+".") {
		return depth(caller) - depth(skill)
	}
	if strings.HasPrefix(skill, caller+".") {
		return depth(skill) - depth(caller)
	}
	return depth(skill)
}
func (c *Catalog) weight(key string, def int64) int64 { return integer(c.Weights, key, def) }
func (c *Catalog) requires(u string) []string {
	out := []string{}
	for _, r := range stringList(c.Cards[u]["requires"]) {
		if _, ok := c.Cards[r]; ok {
			out = append(out, r)
		}
	}
	return out
}
func (c *Catalog) closure(u string) []string {
	seen := map[string]bool{u: true}
	front := []string{u}
	out := []string{}
	for d := 0; d < 2; d++ {
		next := []string{}
		for _, x := range front {
			for _, r := range c.requires(x) {
				if !seen[r] {
					seen[r] = true
					out = append(out, r)
					next = append(next, r)
				}
			}
		}
		front = next
	}
	return out
}

type Candidate struct {
	URN                 string
	BM25Rank, DenseRank int
	Score               int64
}

func (c *Catalog) score(candidates []Candidate, node string) []Candidate {
	seeds := map[string]int64{}
	for _, x := range candidates {
		s := int64(0)
		if x.BM25Rank > 0 {
			s += scale / (60 + int64(x.BM25Rank))
		}
		if x.DenseRank > 0 {
			s += scale / (60 + int64(x.DenseRank))
		}
		s += c.weight("w_scope", 200) / int64(1+hops(str(c.Cards[x.URN]["node"]), node))
		seeds[x.URN] = s
	}
	sum := int64(0)
	for _, s := range seeds {
		if s > 0 {
			sum += s
		}
	}
	p := map[string]int64{}
	mass := map[string]int64{}
	if sum > 0 {
		for _, u := range c.Order {
			s := seeds[u]
			if s < 0 {
				s = 0
			}
			p[u] = s * scale / sum
			mass[u] = p[u]
		}
		if text(c.Weights, "ppr_mode", "closure") == "closure" {
			for _, u := range c.Order {
				if p[u] <= 0 {
					continue
				}
				front := []string{u}
				seen := map[string]bool{u: true}
				num, den := int64(1), int64(1)
				for d := 0; d < 2; d++ {
					num *= c.weight("closure_decay_num", 1)
					den *= c.weight("closure_decay_den", 2)
					next := []string{}
					for _, x := range front {
						for _, r := range c.requires(x) {
							if !seen[r] {
								seen[r] = true
								next = append(next, r)
								mass[r] += p[u] * num / den
							}
						}
					}
					front = next
				}
			}
		} else {
			type edge struct {
				u string
				w int64
			}
			edges := map[string][]edge{}
			outweight := map[string]int64{}
			add := func(u, v string, w int64) {
				if _, ok := c.Cards[v]; ok && w > 0 {
					edges[u] = append(edges[u], edge{v, w})
					outweight[u] += w
				}
			}
			for _, u := range c.Order {
				card := c.Cards[u]
				for _, kind := range []string{"requires", "refines"} {
					for _, v := range stringList(card[kind]) {
						add(u, v, c.weight("edge."+kind, 0))
					}
				}
				if str(card["status"]) == "deprecated" {
					replacement := str(card["replaced_by"])
					if _, ok := c.Cards[replacement]; ok {
						add(replacement, u, c.weight("edge.replaces", 40))
					}
				}
			}
			for i := 0; i < 20; i++ {
				next := map[string]int64{}
				for _, u := range c.Order {
					next[u] = 15 * p[u] / 100
				}
				for _, u := range c.Order {
					if mass[u] == 0 || outweight[u] == 0 {
						continue
					}
					for _, e := range edges[u] {
						next[e.u] += 85 * mass[u] * e.w / (100 * outweight[u])
					}
				}
				mass = next
			}
		}
	}
	out := append([]Candidate{}, candidates...)
	for i := range out {
		u := out[i].URN
		out[i].Score = seeds[u] + c.weight("w_ppr", 250)*mass[u]/scale
	}
	sortCandidates(out)
	return out
}
func sortCandidates(out []Candidate) {
	sort.Slice(out, func(i, j int) bool {
		if out[i].Score != out[j].Score {
			return out[i].Score > out[j].Score
		}
		return out[i].URN < out[j].URN
	})
}
func (c *Catalog) selectCards(scored []Candidate, k int, admissible map[string]bool) []string {
	if len(scored) == 0 || k == 0 {
		return []string{}
	}
	threshold := c.weight("abstain_threshold", 1200)
	signal := scored[0].Score
	if text(c.Weights, "abstain_mode", "magnitude") == "margin" {
		threshold = c.weight("abstain_margin_threshold", 1200)
		signal = 1 << 30
		if len(scored) > 1 {
			signal = scored[0].Score - scored[1].Score
		}
	}
	if signal < threshold {
		return []string{}
	}
	chosen := []string{}
	seen := map[string]bool{}
	scores := map[string]int64{}
	for _, s := range scored {
		scores[s.URN] = s.Score
	}
	for _, s := range scored {
		if len(chosen) >= k {
			break
		}
		if seen[s.URN] || !admissible[s.URN] {
			continue
		}
		chosen = append(chosen, s.URN)
		seen[s.URN] = true
		for _, r := range c.closure(s.URN) {
			if len(chosen) >= k {
				break
			}
			if !seen[r] && admissible[r] {
				seen[r] = true
				chosen = append(chosen, r)
			}
		}
	}
	sort.Slice(chosen, func(i, j int) bool {
		a, b := chosen[i], chosen[j]
		da, db := depth(str(c.Cards[a]["node"])), depth(str(c.Cards[b]["node"]))
		if da != db {
			return da < db
		}
		if scores[a] != scores[b] {
			return scores[a] > scores[b]
		}
		return a < b
	})
	return chosen
}
func (c *Catalog) card(u string, eligible map[string][]string, contextual bool) M {
	card := c.Cards[u]
	out := M{"skill_id": u, "urn": u, "revision": c.Revisions[u], "name": card["name"], "description": card["description"]}
	if contextual {
		out["eligible_scopes"] = eligible[u]
		if eligible[u] == nil {
			out["eligible_scopes"] = []string{}
		}
	}
	return out
}
