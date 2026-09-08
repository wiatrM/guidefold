package generator

import (
	"context"
	"fmt"
	"sort"
	"strings"
)

// Deterministic is recipe `det-1`: extraction, enrichment and consolidation
// with no network, no model and no randomness.
//
// It exists because the review pipeline has to be testable and demonstrable
// without paying a provider, and because a deterministic recipe makes the
// *shape* of the contract falsifiable: every field it emits carries a source
// reference or says it needs confirmation, and every consolidation it declines
// says why. A model can do better prose; it cannot be allowed to do less
// provenance.
type Deterministic struct{}

// RecipeVersion labels the deterministic recipe. Changing any rule below
// changes this string, because the cache key contains it and stale candidates
// must not be reused after the rules move.
const RecipeVersion = "det-1"

// Recipe describes this generator.
func (d *Deterministic) Recipe() Recipe {
	return Recipe{Generator: NameDeterministic, Version: RecipeVersion}
}

var _ Generator = (*Deterministic)(nil)

// Generate dispatches on the group's kind.
func (d *Deterministic) Generate(ctx context.Context, req Request) (Output, Cost, error) {
	if e := ctx.Err(); e != nil {
		return Output{}, Cost{}, e
	}
	switch req.Kind {
	case KindExtraction:
		return d.extract(req), Cost{}, nil
	case KindEnrichment:
		return d.enrich(req), Cost{}, nil
	case KindConsolidation:
		return d.consolidate(req), Cost{}, nil
	}
	return Output{}, Cost{}, fmt.Errorf("unknown generation kind %q", req.Kind)
}

// ---------------------------------------------------------------------------
// Extraction
// ---------------------------------------------------------------------------

// extract turns each document into at most one candidate skill.
//
// A document with no ordered procedure produces nothing. That is deliberate:
// the promise is "a runbook becomes a skill", and a page of prose with no steps
// is not a runbook. Producing an empty candidate for it would spend an owner's
// review time on a document that had nothing to extract.
func (d *Deterministic) extract(req Request) Output {
	out := Output{Candidates: []Candidate{}, Abstentions: []Abstention{}}
	limit := req.Limits.MaxProposals
	for _, doc := range req.Documents {
		if limit > 0 && len(out.Candidates) >= limit {
			break
		}
		c, ok := extractDocument(req, doc)
		if !ok {
			out.Abstentions = append(out.Abstentions, Abstention{
				Reason: "no_procedure_found", Skills: []string{doc.Path},
				Detail: "the document has no ordered steps to extract"})
			continue
		}
		out.Candidates = append(out.Candidates, c)
	}
	return out
}

func extractDocument(req Request, doc Document) (Candidate, bool) {
	sections := Split(doc.Body)
	byRole := map[Role][]Section{}
	title := ""
	for _, s := range sections {
		if title == "" && s.Level == 1 {
			title = s.Heading
		}
		byRole[RoleOf(s.Heading)] = append(byRole[RoleOf(s.Heading)], s)
	}
	steps := []Item{}
	for _, s := range byRole[RoleSteps] {
		steps = append(steps, Items(s)...)
	}
	if len(steps) == 0 {
		return Candidate{}, false
	}
	if title == "" {
		title = titleFromPath(doc.Path)
	}
	scope, owner := doc.Scope, doc.Owner
	if scope == "" {
		scope = req.Scope
	}
	if owner == "" {
		owner = req.Owner
	}

	ref := func(from, to int) *SourceRef {
		if from == 0 {
			return nil
		}
		return &SourceRef{Path: doc.Path, SHA256: doc.SHA256, LineFrom: from, LineTo: to}
	}
	fields := []Field{}
	// text() reads one role's first paragraph and records where it came from.
	// A role the document does not name is still emitted, as a field a person
	// has to confirm rather than as an invented sentence.
	text := func(name string, role Role) string {
		list := byRole[role]
		if len(list) == 0 {
			fields = append(fields, Field{Field: name, Origin: OriginInferred, NeedsConfirmation: true})
			return ""
		}
		value, from, to := Paragraph(list[0])
		if strings.TrimSpace(value) == "" {
			if items := Items(list[0]); len(items) > 0 {
				parts := make([]string, 0, len(items))
				for _, it := range items {
					parts = append(parts, it.Text)
				}
				value = strings.Join(parts, "; ")
				from, to = items[0].LineFrom, items[len(items)-1].LineTo
			}
		}
		if strings.TrimSpace(value) == "" {
			fields = append(fields, Field{Field: name, Origin: OriginInferred, NeedsConfirmation: true})
			return ""
		}
		fields = append(fields, Field{Field: name, Origin: OriginParsed, Value: value, Ref: ref(from, to)})
		return value
	}

	purpose := text("purpose", RolePurpose)
	if purpose == "" {
		// No purpose heading: the document's opening paragraph is the honest
		// fallback, and it is still parsed from named lines.
		if value, from, to := Paragraph(sections[0]); strings.TrimSpace(value) != "" {
			purpose = value
			fields[len(fields)-1] = Field{Field: "purpose", Origin: OriginParsed,
				Value: value, Ref: ref(from, to)}
		}
	}
	whenToUse := text("when_to_use", RoleWhenToUse)
	whenNotToUse := text("when_not_to_use", RoleWhenNotToUse)
	verification := text("verification", RoleVerification)

	lines := []string{}
	for i, step := range steps {
		name := fmt.Sprintf("steps[%d]", i)
		if step.LineFrom > 0 {
			fields = append(fields, Field{Field: name, Origin: OriginParsed, Value: step.Text,
				Ref: ref(step.LineFrom, step.LineTo)})
		} else {
			fields = append(fields, Field{Field: name, Origin: OriginInferred,
				Value: step.Text, NeedsConfirmation: true})
		}
		lines = append(lines, fmt.Sprintf("%d. %s", i+1, step.Text))
	}

	slug := Slug(title)
	if slug == "" {
		slug = Slug(titleFromPath(doc.Path))
	}
	summary := firstSentence(purpose)
	if summary == "" {
		summary = title
	}
	// The knowledge layer is inferred from the shape of the document, never from
	// where the file sits. It is emitted as a field a reviewer can reject on its
	// own, with the lines it was read from (P08).
	layer, _ := InferLayer(LayerInputOf(sections, 1))
	fields = append(fields, Field{Field: FieldKnowledgeLayer, Origin: OriginInferred,
		Value: layer, Ref: ref(sections[0].LineFrom, sections[len(sections)-1].LineTo)})
	frontmatter := map[string]any{
		"name":        slug,
		"description": "[" + scopeLabel(scope) + "] " + summary,
		"metadata": map[string]any{
			"scope": scope, "owner": nullEmpty(owner), "layer": "task",
			FieldKnowledgeLayer: layer,
		},
	}
	body := renderCandidate(title, frontmatter, []bodySection{
		{"Purpose", purpose},
		{"When to use", whenToUse},
		{"When not to use", whenNotToUse},
		{"Steps", strings.Join(lines, "\n")},
		{"Verification", verification},
	})
	return Candidate{
		Name: title, Slug: slug, Scope: scope, Owner: owner,
		Path:        candidatePath(scope, slug, req.ScopeDirs),
		Body:        body,
		Frontmatter: frontmatter,
		Fields:      fields,
		Relations:   []Relation{},
		Sources: []Source{{Path: doc.Path, SHA256: doc.SHA256, Commit: doc.Commit,
			Lines: []int{sections[0].LineFrom, sections[len(sections)-1].LineTo}}},
		Identity: "extraction:" + doc.Path,
	}, true
}

// ---------------------------------------------------------------------------
// Enrichment
// ---------------------------------------------------------------------------

// enrich adds the retrieval metadata an existing skill is missing: what it is
// about, what it touches, what a person would type to find it, and what should
// *not* find it. Everything it adds is `inferred` — none of it is a claim the
// source made — so a reviewer can reject one field without losing the rest
// (PRODUCT-PIVOT U2 AC3).
func (d *Deterministic) enrich(req Request) Output {
	out := Output{Candidates: []Candidate{}, Abstentions: []Abstention{}}
	limit := req.Limits.MaxProposals
	for i := range req.Skills {
		if limit > 0 && len(out.Candidates) >= limit {
			break
		}
		s := req.Skills[i]
		sections := Split(s.Body)
		summary, _, _ := Paragraph(sections[0])
		if summary == "" && len(sections) > 1 {
			summary, _, _ = Paragraph(sections[1])
		}
		topics, technologies := terms(s.Body)
		triggers := []string{}
		negative := []string{}
		queries := []string{}
		for _, sec := range sections {
			role := RoleOf(sec.Heading)
			if sec.Heading != "" && sec.Level >= 2 && role != RoleWhenNotToUse {
				triggers = appendUnique(triggers, strings.ToLower(sec.Heading))
			}
			if role == RoleWhenNotToUse {
				for _, it := range Items(sec) {
					negative = appendUnique(negative, strings.ToLower(firstSentence(it.Text)))
				}
				if len(Items(sec)) == 0 {
					if p, _, _ := Paragraph(sec); p != "" {
						negative = appendUnique(negative, strings.ToLower(firstSentence(p)))
					}
				}
			}
			if role == RoleSteps {
				for _, it := range Items(sec) {
					if q := query(it.Text); q != "" {
						queries = appendUnique(queries, q)
					}
				}
			}
		}
		if len(topics) == 0 && len(triggers) == 0 && len(queries) == 0 {
			out.Abstentions = append(out.Abstentions, Abstention{Reason: "nothing_to_enrich",
				Skills: []string{s.SkillID}, Detail: "the body carries no headings, steps or repeated terms"})
			continue
		}
		if n := req.Limits.MaxNeighbours; n > 0 {
			topics, technologies = limitList(topics, n), limitList(technologies, n)
			triggers, negative, queries = limitList(triggers, n), limitList(negative, n), limitList(queries, n)
		}
		fields := []Field{}
		add := func(name, value string) {
			if strings.TrimSpace(value) == "" {
				return
			}
			// Inferred, and pointing at the body it was inferred from: the
			// reference is the evidence, the origin is the honesty.
			fields = append(fields, Field{Field: name, Origin: OriginInferred, Value: value,
				Ref: &SourceRef{Path: s.Path, SHA256: s.SHA256, LineFrom: 1,
					LineTo: len(strings.Split(s.Body, "\n"))}})
		}
		add("summary", firstSentence(summary))
		add("topics", strings.Join(topics, ", "))
		add("technologies", strings.Join(technologies, ", "))
		add("triggers", strings.Join(triggers, ", "))
		add("negative_triggers", strings.Join(negative, ", "))
		add("example_queries", strings.Join(queries, ", "))
		if len(fields) == 0 {
			continue
		}
		// Where a skill sits on the knowledge axis is retrieval metadata like the
		// rest of enrichment: inferred from the body's own shape, pointing at that
		// body, and rejectable on its own (P08, PRODUCT-PIVOT §2).
		layer, _ := InferLayer(LayerInputOf(sections, 1))
		add(FieldKnowledgeLayer, layer)
		frontmatter := map[string]any{
			"name":        skillName(s),
			"description": s.Description,
			"metadata": map[string]any{
				"scope": s.Scope, "owner": nullEmpty(s.Owner),
				"summary": firstSentence(summary), "topics": topics,
				"technologies": technologies, "triggers": triggers,
				"negative_triggers": negative, "example_queries": queries,
				FieldKnowledgeLayer: layer,
			},
		}
		out.Candidates = append(out.Candidates, Candidate{
			Name: s.Name, Slug: Slug(skillName(s)), Scope: s.Scope, Owner: s.Owner,
			Path: s.Path, Body: reframe(s.Body, frontmatter), Frontmatter: frontmatter,
			TargetSkillID: s.SkillID, Fields: fields, Relations: []Relation{},
			Sources:  []Source{{Path: s.Path, SHA256: s.SHA256}},
			Identity: "enrichment:" + s.SkillID,
		})
	}
	return out
}

// ---------------------------------------------------------------------------
// Consolidation
// ---------------------------------------------------------------------------

// minSharedSteps is the shortest run of steps that may become a shared skill.
// Two matching steps are a coincidence; three in the same order are a procedure.
const minSharedSteps = 3

// procedure is one skill of a consolidation group, parsed once.
type procedure struct {
	skill Skill
	steps []Item
	keys  []string
}

// consolidate looks for ordered runs of steps that two procedures in the group
// perform identically, and proposes each as a shared skill in the scope that
// contains both sources, with `derived_from` edges down to its sources and a
// proposed `refines` edge up from each source.
//
// The group is the unit of comparison and the group is bounded: the plan puts
// the skills of one parent scope and its direct children into one group of at
// most `max_neighbours` skills, so the comparison is quadratic in a small bound
// and never a pass over the catalog (API-CONTRACT §8). Inside that bound every
// pair is looked at, because a shared element that only shows up in the third
// and fifth runbook is exactly the one a person would never find by hand.
//
// It abstains loudly. Two runbooks that read alike but pin different versions,
// hold under different conditions, or contradict each other are *not* the same
// procedure, and merging them would put a wrong instruction in front of an
// agent (PRODUCT-PIVOT U2 AC5). Every declined pair is recorded with its reason
// rather than silently producing nothing, and a pair that only lost because its
// members are already in a shared element says that too.
func (d *Deterministic) consolidate(req Request) Output {
	out := Output{Candidates: []Candidate{}, Abstentions: []Abstention{}}
	skills := req.Skills
	if n := req.Limits.MaxNeighbours; n > 0 && len(skills) > n {
		// The bound is applied here as well as in the plan, because a generator
		// that trusts its caller to have stopped reading is not bounded at all.
		skills = skills[:n]
	}
	procs := []procedure{}
	for i := range skills {
		s := skills[i]
		steps := []Item{}
		for _, sec := range Split(s.Body) {
			if RoleOf(sec.Heading) == RoleSteps {
				steps = append(steps, Items(sec)...)
			}
		}
		if len(steps) < minSharedSteps {
			continue
		}
		keys := make([]string, len(steps))
		for j, st := range steps {
			keys[j] = strings.Join(Normalise(st.Text), " ")
		}
		procs = append(procs, procedure{skill: s, steps: steps, keys: keys})
	}
	if len(procs) < 2 {
		out.Abstentions = append(out.Abstentions, Abstention{Reason: "too_few_procedures",
			Skills: skillIDs(skills),
			Detail: "consolidation needs at least two skills with an ordered procedure"})
		return out
	}

	// Every pair with a long enough run, longest first so the strongest evidence
	// wins the sources it is built from. Ties break on the skill ids, so two runs
	// over the same group agree on which shared element they propose.
	pairs := []sharedRun{}
	for i := 0; i < len(procs); i++ {
		for j := i + 1; j < len(procs); j++ {
			run := longestRun(procs[i].keys, procs[j].keys)
			if run.length < minSharedSteps {
				continue
			}
			run.left, run.right = i, j
			pairs = append(pairs, run)
		}
	}
	if len(pairs) == 0 {
		out.Abstentions = append(out.Abstentions, Abstention{Reason: "no_shared_procedure",
			Skills: skillIDs(skills),
			Detail: fmt.Sprintf("no run of %d identical ordered steps appears in two procedures", minSharedSteps)})
		return out
	}
	sort.SliceStable(pairs, func(a, b int) bool {
		if pairs[a].length != pairs[b].length {
			return pairs[a].length > pairs[b].length
		}
		ia, ja := procs[pairs[a].left].skill.SkillID, procs[pairs[a].right].skill.SkillID
		ib, jb := procs[pairs[b].left].skill.SkillID, procs[pairs[b].right].skill.SkillID
		if ia != ib {
			return ia < ib
		}
		return ja < jb
	})

	limit := req.Limits.MaxProposals
	used := map[string]bool{}
	for _, run := range pairs {
		left, right := procs[run.left], procs[run.right]
		sourceIDs := sortedUnique([]string{left.skill.SkillID, right.skill.SkillID})
		if reason, detail := disagreeRun(left, right, run); reason != "" {
			out.Abstentions = append(out.Abstentions, Abstention{Reason: reason,
				Skills: sourceIDs, Detail: detail})
			continue
		}
		if used[left.skill.SkillID] || used[right.skill.SkillID] {
			// One shared element per source. A second one over the same skill
			// would carve the same procedure twice and leave the owner deciding
			// which of two overlapping abstractions is the real one.
			out.Abstentions = append(out.Abstentions, Abstention{Reason: "already_consolidated",
				Skills: sourceIDs,
				Detail: "one of these skills is already the source of a shared element in this run"})
			continue
		}
		if limit > 0 && len(out.Candidates) >= limit {
			out.Abstentions = append(out.Abstentions, Abstention{Reason: "max_proposals_reached",
				Skills: sourceIDs,
				Detail: fmt.Sprintf("the group's limit of %d proposals was already reached", limit)})
			continue
		}
		used[left.skill.SkillID], used[right.skill.SkillID] = true, true
		out.Candidates = append(out.Candidates, sharedElement(req, left, right, run, sourceIDs))
	}
	return out
}

// disagreeRun reports why two procedures with a matching run are not the same
// procedure, or "" when they are.
func disagreeRun(left, right procedure, run sharedRun) (string, string) {
	for k := 0; k < run.length; k++ {
		a, b := left.steps[run.leftAt+k].Text, right.steps[run.rightAt+k].Text
		if reason, detail := disagree(a, b); reason != "" {
			return reason, detail
		}
	}
	// A contradiction anywhere in the two procedures — not only inside the
	// matched run — means the two skills disagree about the same subject.
	for _, a := range left.steps {
		for _, b := range right.steps {
			if Contradicts(a.Text, b.Text) {
				return "contradictory_steps",
					fmt.Sprintf("%q contradicts %q", firstSentence(a.Text), firstSentence(b.Text))
			}
		}
	}
	return "", ""
}

// sharedElement builds the candidate for one agreeing pair.
//
// Two decisions are made here and enforced elsewhere. The scope is the deepest
// one that contains both sources, so a shared element between two sibling scopes
// lands on their parent rather than in one sibling's territory. When that raises
// the scope, the owner is the *target* scope's owner — the group's owner, which
// the plan read from `gfm.scopes` — because the person who has to live with a
// skill in `atlas` is the owner of `atlas`, not whoever happened to write the
// two runbooks. `validateConsolidation` refuses the approval if that owner is
// not the proposal's owner (API-CONTRACT §4.4, `scope_widening_not_approved`).
func sharedElement(req Request, left, right procedure, run sharedRun, sourceIDs []string) Candidate {
	scope := commonScope(left.skill.Scope, right.skill.Scope)
	raised := scope != left.skill.Scope || scope != right.skill.Scope
	owner := commonOwner(left.skill, right.skill)
	if raised {
		owner = req.Owner
	}
	title := "Shared: " + firstSentence(left.steps[run.leftAt].Text)
	slug := Slug(title)
	fields := []Field{}
	lines := []string{}
	for k := 0; k < run.length; k++ {
		step := left.steps[run.leftAt+k]
		fields = append(fields, Field{Field: fmt.Sprintf("steps[%d]", k), Origin: OriginParsed,
			Value: step.Text, Ref: &SourceRef{Path: left.skill.Path, SHA256: left.skill.SHA256,
				LineFrom: step.LineFrom, LineTo: step.LineTo}})
		lines = append(lines, fmt.Sprintf("%d. %s", k+1, step.Text))
	}
	purpose := fmt.Sprintf("The %d steps %s and %s perform identically.",
		run.length, left.skill.SkillID, right.skill.SkillID)
	fields = append(fields, Field{Field: "purpose", Origin: OriginInferred, Value: purpose,
		NeedsConfirmation: true})
	scopes := distinctScopes([]string{left.skill.Scope, right.skill.Scope})
	layer, _ := InferLayer(LayerInput{Steps: run.length, SourceScopes: scopes})
	fields = append(fields, Field{Field: FieldKnowledgeLayer, Origin: OriginInferred, Value: layer,
		Ref: &SourceRef{Path: left.skill.Path, SHA256: left.skill.SHA256,
			LineFrom: left.steps[run.leftAt].LineFrom,
			LineTo:   left.steps[run.leftAt+run.length-1].LineTo}})
	frontmatter := map[string]any{
		"name":        slug,
		"description": "[" + scopeLabel(scope) + "] " + firstSentence(title),
		"metadata": map[string]any{"scope": scope, "owner": nullEmpty(owner),
			"layer": "atomic", FieldKnowledgeLayer: layer},
	}
	body := renderCandidate(title, frontmatter, []bodySection{
		{"Purpose", purpose},
		{"Steps", strings.Join(lines, "\n")},
		{"Derived from", "- " + strings.Join(sourceIDs, "\n- ")},
	})
	// Down: what this element was derived from. Up: each source refines it. The
	// second direction is what makes the family readable from a card — a source
	// skill can say "there is an abstraction above me", and the abstraction can
	// list the children that specialise it (P08).
	relations := make([]Relation, 0, 2*len(sourceIDs))
	for _, id := range sourceIDs {
		relations = append(relations, Relation{Type: "derived_from", To: id})
	}
	for _, id := range sourceIDs {
		relations = append(relations, Relation{Type: "refines", From: id})
	}
	return Candidate{
		Name: title, Slug: slug, Scope: scope, Owner: owner,
		Path: candidatePath(scope, slug, req.ScopeDirs), Body: body, Frontmatter: frontmatter,
		Fields: fields, Relations: relations,
		Sources: []Source{
			{Path: left.skill.Path, SHA256: left.skill.SHA256},
			{Path: right.skill.Path, SHA256: right.skill.SHA256}},
		Identity: "consolidation:" + strings.Join(sourceIDs, "+"),
	}
}

type sharedRun struct {
	length, leftAt, rightAt, left, right int
}

// longestRun is the longest run of equal, consecutive, identically ordered
// entries in two step lists.
func longestRun(a, b []string) sharedRun {
	best := sharedRun{}
	table := make([][]int, len(a)+1)
	for i := range table {
		table[i] = make([]int, len(b)+1)
	}
	for i := 1; i <= len(a); i++ {
		for j := 1; j <= len(b); j++ {
			if a[i-1] == "" || a[i-1] != b[j-1] {
				continue
			}
			table[i][j] = table[i-1][j-1] + 1
			if table[i][j] > best.length {
				best = sharedRun{length: table[i][j], leftAt: i - table[i][j], rightAt: j - table[i][j]}
			}
		}
	}
	return best
}

// disagree reports why two textually matching steps are not the same step.
func disagree(a, b string) (string, string) {
	va, vb := Versions(a), Versions(b)
	if !equalTokens(va, vb) {
		return "version_mismatch", fmt.Sprintf("the same step pins %v in one procedure and %v in the other", va, vb)
	}
	ca, cb := Conditions(a), Conditions(b)
	if !equalTokens(ca, cb) {
		return "condition_mismatch", fmt.Sprintf("the same step holds under %v in one procedure and %v in the other", ca, cb)
	}
	if Contradicts(a, b) {
		return "contradictory_steps", fmt.Sprintf("%q contradicts %q", firstSentence(a), firstSentence(b))
	}
	return "", ""
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

type bodySection struct{ Heading, Text string }

// renderCandidate writes the SKILL.md a proposal carries. The frontmatter is
// emitted by hand rather than by a YAML library so the bytes are stable: the
// candidate's sha256 is part of its identity and of the export's digest.
func renderCandidate(title string, frontmatter map[string]any, sections []bodySection) string {
	var b strings.Builder
	b.WriteString("---\n")
	b.WriteString("name: " + yamlScalar(str(frontmatter["name"])) + "\n")
	b.WriteString("description: " + yamlScalar(str(frontmatter["description"])) + "\n")
	meta, _ := frontmatter["metadata"].(map[string]any)
	if len(meta) > 0 {
		b.WriteString("metadata:\n")
		for _, k := range sortedKeys(meta) {
			switch v := meta[k].(type) {
			case nil:
			case []string:
				if len(v) == 0 {
					continue
				}
				b.WriteString("  " + k + ":\n")
				for _, item := range v {
					b.WriteString("    - " + yamlScalar(item) + "\n")
				}
			default:
				b.WriteString("  " + k + ": " + yamlScalar(fmt.Sprint(v)) + "\n")
			}
		}
	}
	b.WriteString("---\n\n# " + title + "\n")
	for _, s := range sections {
		if strings.TrimSpace(s.Text) == "" {
			continue
		}
		b.WriteString("\n## " + s.Heading + "\n\n" + strings.TrimRight(s.Text, "\n") + "\n")
	}
	return b.String()
}

// reframe replaces an existing skill's frontmatter with the enriched one and
// keeps every byte of its body. Enrichment adds metadata; it never rewrites
// what a person authored.
func reframe(body string, frontmatter map[string]any) string {
	rest := body
	if strings.HasPrefix(body, "---\n") {
		if i := strings.Index(body[4:], "\n---"); i >= 0 {
			rest = strings.TrimPrefix(body[4+i+4:], "\n")
		}
	}
	head := renderCandidate("", frontmatter, nil)
	head = strings.TrimSuffix(head, "\n# \n")
	return head + "\n" + rest
}

func yamlScalar(s string) string {
	s = strings.ReplaceAll(s, "\n", " ")
	if s == "" {
		return `""`
	}
	if strings.ContainsAny(s, `:#"'{}[]&*?|<>=!%@`) || strings.HasPrefix(s, " ") {
		return `"` + strings.ReplaceAll(strings.ReplaceAll(s, `\`, `\\`), `"`, `\"`) + `"`
	}
	return s
}

func sortedKeys(m map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func str(v any) string { s, _ := v.(string); return s }

func nullEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// candidatePath places a candidate inside the scope it belongs to.
//
// `dirs[scope]` is the scope's real on-disk directory, resolved from
// guidefold.yaml's own declared node paths (gfm.scopes) by the caller that
// built the request -- the same "longest literal prefix" rule
// internal/importer/domain.ScopeOf uses in the other direction, just not
// reachable from here without a cross-module dependency this package does not
// otherwise need (module-boundaries-go: read another module's data through an
// explicit projection, not a shared query -- ScopeDirs IS that projection).
//
// When a scope is missing from `dirs` (nil map, a caller that has not wired
// gfm.scopes through yet, or a scope with no stored prefix), this falls back
// to the dotted-name guess: correct only when the node's own directory
// happens to mirror its dotted scope name, which guidefold.yaml does not
// guarantee -- confirmed wrong for the Meridian fixture's `atlas` node
// (declared at `platforms/atlas/**`, not `atlas/`) by the 2026-09-08 ACT-01
// acceptance run: a candidate placed by the guess landed at a path that
// resolved to a *different* scope on the next import, and the importer
// correctly (given that wrong input) archived the original identity as
// superseded.
func candidatePath(scope, slug string, dirs map[string]string) string {
	if dir, ok := dirs[scope]; ok && dir != "" {
		return strings.TrimSuffix(dir, "/") + "/.agents/skills/" + slug + "/SKILL.md"
	}
	dir := ".agents/skills"
	if scope != "" && scope != "_root" {
		dir = strings.ReplaceAll(scope, ".", "/") + "/.agents/skills"
	}
	return dir + "/" + slug + "/SKILL.md"
}

func scopeLabel(scope string) string {
	if scope == "" {
		return "_root"
	}
	return scope
}

func titleFromPath(p string) string {
	name := p
	if i := strings.LastIndex(p, "/"); i >= 0 {
		name = p[i+1:]
	}
	name = strings.TrimSuffix(name, ".md")
	words := strings.Fields(strings.ReplaceAll(strings.ReplaceAll(name, "-", " "), "_", " "))
	for i, w := range words {
		words[i] = strings.ToUpper(w[:1]) + w[1:]
	}
	return strings.Join(words, " ")
}

func firstSentence(s string) string {
	s = strings.TrimSpace(s)
	for i, r := range s {
		if r == '.' && (i+1 == len(s) || s[i+1] == ' ') {
			return s[:i]
		}
	}
	if len(s) > 180 {
		if i := strings.LastIndex(s[:180], " "); i > 0 {
			return s[:i]
		}
		return s[:180]
	}
	return s
}

func skillName(s Skill) string {
	if s.Name != "" {
		return s.Name
	}
	return Slug(s.SkillID)
}

// terms splits the body's vocabulary into technologies — the identifiers a
// runbook names in code spans — and topics, the words it repeats in prose.
func terms(body string) ([]string, []string) {
	tech := map[string]int{}
	for _, span := range Code(body) {
		for _, t := range Normalise(span) {
			if len(t) >= 2 {
				tech[t]++
			}
		}
	}
	counts := map[string]int{}
	for _, t := range Normalise(stripCode(body)) {
		if len(t) >= 4 && tech[t] == 0 {
			counts[t]++
		}
	}
	return top(counts, 2, 8), top(tech, 1, 8)
}

func stripCode(body string) string { return codeRE.ReplaceAllString(body, " ") }

// top returns the most frequent terms above a threshold, ties broken
// alphabetically so two runs over the same bytes agree.
func top(counts map[string]int, min, n int) []string {
	type entry struct {
		term string
		n    int
	}
	list := []entry{}
	for term, c := range counts {
		if c >= min {
			list = append(list, entry{term, c})
		}
	}
	sort.Slice(list, func(i, j int) bool {
		if list[i].n != list[j].n {
			return list[i].n > list[j].n
		}
		return list[i].term < list[j].term
	})
	out := []string{}
	for i := 0; i < len(list) && i < n; i++ {
		out = append(out, list[i].term)
	}
	return out
}

// query turns an imperative step into the question someone would type to find
// it. It is an inferred label, never a test of retrieval: a generated query
// that finds its own skill proves nothing (PRODUCT-PIVOT U2 AC3).
func query(step string) string {
	words := strings.Fields(strings.ToLower(stripCode(step)))
	if len(words) < 2 {
		return ""
	}
	verb := strings.Trim(words[0], ",.;:`")
	if verb == "" || stopwords[verb] || strings.HasSuffix(verb, "ing") {
		return ""
	}
	rest := []string{}
	for _, w := range words[1:] {
		w = strings.Trim(w, ",.;:`\"'()")
		if w == "" {
			continue
		}
		rest = append(rest, w)
		if len(rest) == 4 {
			break
		}
	}
	if len(rest) == 0 {
		return ""
	}
	return "how to " + verb + " " + strings.Join(rest, " ")
}

func appendUnique(list []string, v string) []string {
	v = strings.TrimSpace(v)
	if v == "" {
		return list
	}
	for _, x := range list {
		if x == v {
			return list
		}
	}
	return append(list, v)
}

func limitList(list []string, n int) []string {
	if n > 0 && len(list) > n {
		return list[:n]
	}
	return list
}

func skillIDs(list []Skill) []string {
	out := make([]string, 0, len(list))
	for _, s := range list {
		out = append(out, s.SkillID)
	}
	sort.Strings(out)
	return out
}

// commonScope is the deepest scope that contains both sources. Two skills of
// the same scope stay there; two of different scopes raise to their common
// ancestor, which is the case the decision endpoint guards.
func commonScope(a, b string) string {
	if a == b {
		return a
	}
	as, bs := strings.Split(a, "."), strings.Split(b, ".")
	out := []string{}
	for i := 0; i < len(as) && i < len(bs); i++ {
		if as[i] != bs[i] {
			break
		}
		out = append(out, as[i])
	}
	if len(out) == 0 {
		return "_root"
	}
	return strings.Join(out, ".")
}

func commonOwner(a, b Skill) string {
	if a.Owner == b.Owner {
		return a.Owner
	}
	return ""
}
