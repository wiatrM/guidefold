package generator

import (
	"regexp"
	"strings"
)

// Markdown reading for the deterministic recipe. It is deliberately small: the
// point is not to render Markdown but to find the four things a runbook has to
// carry — what it is for, when it does and does not apply, its ordered steps
// and how to verify them — and to remember which *lines* each of them came from
// so a person can check the claim against the file.

// Line is one source line with its 1-based number.
type Line struct {
	N    int
	Text string
}

// Section is one heading and the lines under it, up to the next heading of the
// same or a shallower level.
type Section struct {
	Heading  string
	Level    int
	LineFrom int
	LineTo   int
	Lines    []Line
}

var (
	headingRE = regexp.MustCompile(`^(#{1,6})\s+(.*\S)\s*$`)
	orderedRE = regexp.MustCompile(`^\s{0,3}(\d+)[.)]\s+(.*\S)\s*$`)
	bulletRE  = regexp.MustCompile(`^\s{0,3}[-*+]\s+(.*\S)\s*$`)
	fenceRE   = regexp.MustCompile("^\\s{0,3}(```|~~~)")
	codeRE    = regexp.MustCompile("`([^`]+)`")
	versionRE = regexp.MustCompile(`(?i)\b(v?\d+\.\d+(?:\.\d+)?|\d+\.x)\b`)
)

// Split reads a document into its heading sections plus a preamble section
// (heading "", level 0) holding everything before the first heading. Fenced
// code blocks are transparent to heading detection: a `#` inside a shell block
// is a comment, not a section.
func Split(body string) []Section {
	raw := strings.Split(strings.ReplaceAll(body, "\r\n", "\n"), "\n")
	out := []Section{{Level: 0, LineFrom: 1, LineTo: 1}}
	fenced := false
	for i, text := range raw {
		n := i + 1
		if fenceRE.MatchString(text) {
			fenced = !fenced
		}
		if m := headingRE.FindStringSubmatch(text); m != nil && !fenced {
			out = append(out, Section{Heading: m[2], Level: len(m[1]), LineFrom: n, LineTo: n})
			continue
		}
		last := &out[len(out)-1]
		last.Lines = append(last.Lines, Line{N: n, Text: text})
		last.LineTo = n
	}
	// A document that opens with a heading leaves an empty preamble; keeping it
	// would make "the first paragraph" empty for every well-formed file.
	if len(out) > 1 && strings.TrimSpace(joinText(out[0].Lines)) == "" {
		out = out[1:]
	}
	return out
}

func joinText(lines []Line) string {
	parts := make([]string, 0, len(lines))
	for _, l := range lines {
		parts = append(parts, l.Text)
	}
	return strings.Join(parts, "\n")
}

// Paragraph is the first non-empty run of lines in a section.
func Paragraph(s Section) (string, int, int) {
	from, to := 0, 0
	var parts []string
	for _, l := range s.Lines {
		text := strings.TrimSpace(l.Text)
		if text == "" {
			if len(parts) > 0 {
				break
			}
			continue
		}
		if headingRE.MatchString(l.Text) {
			break
		}
		if from == 0 {
			from = l.N
		}
		to = l.N
		parts = append(parts, text)
	}
	return strings.Join(parts, " "), from, to
}

// Item is one list entry with the lines it occupies.
type Item struct {
	Text     string
	LineFrom int
	LineTo   int
	Ordered  bool
}

// Items reads the list entries of a section. A continuation line indented under
// an entry belongs to that entry, so a step's source range covers all of it.
func Items(s Section) []Item {
	out := []Item{}
	fenced := false
	for _, l := range s.Lines {
		if fenceRE.MatchString(l.Text) {
			fenced = !fenced
			if len(out) > 0 {
				out[len(out)-1].LineTo = l.N
			}
			continue
		}
		if fenced {
			if len(out) > 0 {
				out[len(out)-1].LineTo = l.N
			}
			continue
		}
		if m := orderedRE.FindStringSubmatch(l.Text); m != nil {
			out = append(out, Item{Text: m[2], LineFrom: l.N, LineTo: l.N, Ordered: true})
			continue
		}
		if m := bulletRE.FindStringSubmatch(l.Text); m != nil {
			out = append(out, Item{Text: m[1], LineFrom: l.N, LineTo: l.N})
			continue
		}
		text := strings.TrimSpace(l.Text)
		if text == "" || len(out) == 0 {
			continue
		}
		if strings.HasPrefix(l.Text, "  ") || strings.HasPrefix(l.Text, "\t") {
			out[len(out)-1].Text += " " + text
			out[len(out)-1].LineTo = l.N
		}
	}
	return out
}

// Role names what a heading is for. Matching is on the heading text only: a
// document that does not say "when not to use" does not get one inferred from
// its prose, it gets a field that needs confirmation.
type Role string

// The five roles the extraction recipe recognises.
const (
	RolePurpose      Role = "purpose"
	RoleWhenToUse    Role = "when_to_use"
	RoleWhenNotToUse Role = "when_not_to_use"
	RoleSteps        Role = "steps"
	RoleVerification Role = "verification"
	RoleOther        Role = ""
)

var roleWords = []struct {
	role  Role
	words []string
}{
	// Order matters: "when not to use" must be tested before "when to use".
	{RoleWhenNotToUse, []string{"when not", "do not use", "don't use", "not applicable",
		"out of scope", "kiedy nie"}},
	{RoleWhenToUse, []string{"when to use", "use when", "applies to", "applicability",
		"kiedy uzyc", "kiedy używać"}},
	{RoleVerification, []string{"verify", "verification", "validate", "validation",
		"check that", "acceptance", "weryfikacja"}},
	{RoleSteps, []string{"steps", "procedure", "runbook", "how to", "instructions",
		"playbook", "kroki", "procedura"}},
	{RolePurpose, []string{"purpose", "overview", "summary", "what it does", "about",
		"context", "cel"}},
}

// RoleOf classifies one heading.
func RoleOf(heading string) Role {
	h := strings.ToLower(strings.TrimSpace(heading))
	for _, entry := range roleWords {
		for _, w := range entry.words {
			if strings.Contains(h, w) {
				return entry.role
			}
		}
	}
	return RoleOther
}

// Slug turns a name into an identifier a skill directory can carry.
func Slug(s string) string {
	var b strings.Builder
	dash := false
	for _, r := range strings.ToLower(s) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
			dash = false
		default:
			if !dash && b.Len() > 0 {
				b.WriteByte('-')
				dash = true
			}
		}
	}
	out := strings.Trim(b.String(), "-")
	if len(out) > 60 {
		out = strings.Trim(out[:60], "-")
	}
	return out
}

// Normalise reduces a step to the tokens two runbooks have to agree on for the
// step to count as shared. It keeps word order, drops punctuation and case, and
// keeps version-like tokens intact, because "upgrade to 2.1" and "upgrade to
// 3.0" are different instructions that must not consolidate.
func Normalise(text string) []string {
	fields := strings.FieldsFunc(strings.ToLower(text), func(r rune) bool {
		return !(r >= 'a' && r <= 'z' || r >= '0' && r <= '9' || r == '.' || r == '_')
	})
	out := make([]string, 0, len(fields))
	for _, f := range fields {
		f = strings.Trim(f, ".")
		if f == "" || stopwords[f] {
			continue
		}
		out = append(out, f)
	}
	return out
}

// Versions lists the version-like tokens of a step. A shared step whose
// versions differ is not shared (PRODUCT-PIVOT U2 AC5).
func Versions(text string) []string {
	out := []string{}
	for _, m := range versionRE.FindAllString(strings.ToLower(text), -1) {
		out = append(out, strings.TrimPrefix(m, "v"))
	}
	return out
}

// conditionWords open a clause that makes a step conditional. Two steps that
// read alike but hold under different conditions are not the same step.
var conditionWords = map[string]bool{"if": true, "unless": true, "when": true,
	"only": true, "except": true, "otherwise": true, "provided": true, "gdy": true}

// Conditions lists the condition clauses of a step, lower-cased and trimmed.
func Conditions(text string) []string {
	out := []string{}
	lower := strings.ToLower(text)
	words := strings.Fields(lower)
	for i, w := range words {
		w = strings.Trim(w, ",.;:()")
		if !conditionWords[w] {
			continue
		}
		end := len(words)
		for j := i + 1; j < len(words); j++ {
			if strings.HasSuffix(words[j], ",") || strings.HasSuffix(words[j], ";") {
				end = j + 1
				break
			}
		}
		clause := strings.Join(words[i:end], " ")
		out = append(out, strings.Trim(clause, ",.;: "))
	}
	return out
}

// negations open a step that forbids what another step requires.
var negations = []string{"do not ", "don't ", "never ", "must not ", "avoid ", "nie "}

// Contradicts reports whether two steps say the opposite thing: same tokens
// once the negation is removed, but only one of them negated.
func Contradicts(a, b string) bool {
	na, stripA := stripNegation(a)
	nb, stripB := stripNegation(b)
	if na == nb {
		return false
	}
	return equalTokens(Normalise(stripA), Normalise(stripB))
}

func stripNegation(s string) (bool, string) {
	lower := strings.ToLower(strings.TrimSpace(s))
	for _, n := range negations {
		if strings.HasPrefix(lower, n) {
			return true, lower[len(n):]
		}
		if i := strings.Index(lower, " "+n); i >= 0 {
			return true, lower[:i+1] + lower[i+1+len(n):]
		}
	}
	return false, lower
}

func equalTokens(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// Code lists the inline code spans of a text, which is where a runbook names
// the technologies it actually touches.
func Code(text string) []string {
	out := []string{}
	for _, m := range codeRE.FindAllStringSubmatch(text, -1) {
		if v := strings.TrimSpace(m[1]); v != "" {
			out = append(out, v)
		}
	}
	return out
}

// stopwords are dropped from term frequency and step normalisation. The list is
// small on purpose: an aggressive one would make two different steps look alike.
var stopwords = map[string]bool{
	"a": true, "an": true, "and": true, "are": true, "as": true, "at": true, "be": true,
	"by": true, "for": true, "from": true, "has": true, "have": true, "in": true,
	"into": true, "is": true, "it": true, "its": true, "of": true, "on": true, "or": true,
	"that": true, "the": true, "their": true, "then": true, "there": true, "these": true,
	"this": true, "to": true, "was": true, "were": true, "will": true, "with": true,
	"you": true, "your": true, "we": true, "our": true, "can": true, "should": true,
	"must": true, "each": true, "any": true, "all": true, "not": true, "no": true,
}
