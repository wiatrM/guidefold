package generator

import "sort"

// The knowledge layer of the pyramid, inferred.
//
// The layer is the Wiedza axis of PRODUCT-PIVOT §2: how abstract an instruction
// is. It is a different question from the Źródło axis (which file, which commit)
// and from the Zakres axis (which scope, which owner), and it never follows from
// directory depth — a skill three directories down is not thereby atomic
// (domain-glossary, UX §2).
//
// det-1 may only ever *infer* it. Every layer it emits is a `knowledge_layer`
// field with `origin: inferred` and a source reference, so a reviewer sees the
// claim and the bytes it was read from, and may overrule it on approve — at
// which point the field's origin becomes `human` (API-CONTRACT §4.4).

// LayerInput is what the rule table below reads. It is the parsed shape of one
// candidate, not the candidate itself, so the rules stay testable without a
// document, a database or a generator.
type LayerInput struct {
	// Steps is the number of ordered steps the candidate carries.
	Steps int
	// Rules is the number of list entries that state a rule or a constraint
	// rather than a step: entries under "when to use", "when not to use" and any
	// other non-procedural heading.
	Rules int
	// SourceScopes is how many distinct scopes the candidate was built from. Two
	// or more means it is a shared element lifted above its sources.
	SourceScopes int
}

// Layer rule ids. They are recorded in the abstention/provenance detail so the
// reason a layer was chosen is readable without re-deriving it.
const (
	LayerRuleConsolidated = "consolidated_from_2_or_more_scopes"
	LayerRuleOrderedSteps = "ordered_steps"
	LayerRuleSingleStep   = "single_step"
	LayerRuleRulesOnly    = "rules_or_constraints_without_steps"
	LayerRuleReference    = "single_reference"
)

// InferLayer applies the det-1 rule table, in order. The first rule that matches
// wins, which is what makes the outcome explainable: there is exactly one reason
// for every answer.
//
//	| # | condition                                   | layer    |
//	|---|---------------------------------------------|----------|
//	| 1 | built from 2 or more distinct scopes         | abstract |
//	| 2 | 2 or more ordered steps                      | task     |
//	| 3 | exactly one ordered step                     | atomic   |
//	| 4 | no steps, 2 or more rules or constraints     | abstract |
//	| 5 | anything else (a single reference)           | atomic   |
//
// Rule 1 before rule 2 is the load-bearing order: a shared element consolidated
// out of two scopes still *has* steps, and calling it a task would put it on the
// same rung as the procedures it was lifted out of.
func InferLayer(in LayerInput) (layer, rule string) {
	switch {
	case in.SourceScopes >= 2:
		return LayerAbstract, LayerRuleConsolidated
	case in.Steps >= 2:
		return LayerTask, LayerRuleOrderedSteps
	case in.Steps == 1:
		return LayerAtomic, LayerRuleSingleStep
	case in.Rules >= 2:
		return LayerAbstract, LayerRuleRulesOnly
	}
	return LayerAtomic, LayerRuleReference
}

// KnownLayer reports whether a value is one of the three inferred layers or the
// explicit "not classified yet". Anything else is a typo or a source layer that
// wandered into the wrong field.
func KnownLayer(v string) bool {
	switch v {
	case LayerAtomic, LayerTask, LayerAbstract, LayerUnclassified:
		return true
	}
	return false
}

// LayerInputOf reads one parsed body into the rule table's inputs.
func LayerInputOf(sections []Section, sourceScopes int) LayerInput {
	in := LayerInput{SourceScopes: sourceScopes}
	for _, s := range sections {
		switch RoleOf(s.Heading) {
		case RoleSteps:
			in.Steps += len(Items(s))
		case RoleVerification:
			// Verification is neither a step of the procedure nor a rule about
			// when it applies; counting it either way would move the layer.
		default:
			in.Rules += len(Items(s))
		}
	}
	return in
}

// distinctScopes counts the scopes a set of sources spans, ignoring blanks.
func distinctScopes(scopes []string) int {
	seen := map[string]bool{}
	for _, s := range scopes {
		if s != "" {
			seen[s] = true
		}
	}
	return len(seen)
}

// sortedUnique is the deterministic rendering of a set of identifiers.
func sortedUnique(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, v := range values {
		if v == "" || seen[v] {
			continue
		}
		seen[v] = true
		out = append(out, v)
	}
	sort.Strings(out)
	return out
}
