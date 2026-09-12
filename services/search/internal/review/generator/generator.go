// Package generator is the review module's outbound port for turning source
// text into skill candidates.
//
// It is a port, not a client: the domain asks for "candidates for this group"
// and gets candidates with provenance, and the four implementations behind it —
// none, deterministic, openai, anthropic — differ only in where the text comes
// from. That is what lets the tests, the offline demo and a real deployment run
// the *same* review pipeline (API-CONTRACT §8, "Generator").
//
// Nothing here touches the database, HTTP handlers or the job queue. A
// generator never decides whether a candidate is accepted; it only produces one
// with enough evidence for a person to decide.
package generator

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"sort"
	"strings"
)

// Kinds of generation. One job kind runs all three; `payload.kind` picks
// (API-CONTRACT §8, tech-lead decision 9).
const (
	KindExtraction    = "extraction"
	KindEnrichment    = "enrichment"
	KindConsolidation = "consolidation"
)

// Origins a field value can have (API-CONTRACT §7, gfm.proposal_fields).
const (
	OriginSource   = "source"
	OriginParsed   = "parsed"
	OriginInferred = "inferred"
	OriginHuman    = "human"
)

// Knowledge layers — the Wiedza axis of the pyramid (PRODUCT-PIVOT §2).
//
// This axis is *not* the source layer (`org`/`platform`/`team`) and does not
// follow from directory depth: a layer says how abstract an instruction is, not
// who owns it or where it sits (domain-glossary). A generator may only ever
// infer it; an owner may overrule the inference on approve.
const (
	LayerAtomic       = "atomic"
	LayerTask         = "task"
	LayerAbstract     = "abstract"
	LayerUnclassified = "unclassified"
)

// FieldKnowledgeLayer is the field name the inferred layer is recorded under,
// in `gfm.proposal_fields` and in the candidate's frontmatter metadata. It is
// deliberately not `layer`: that key already carries the source axis, and
// collapsing the two is the mistake the glossary exists to prevent.
const FieldKnowledgeLayer = "knowledge_layer"

// ErrNotConfigured is what `GUIDEFOLD_GENERATOR=none` returns. The job ends
// `skipped` with `llm_not_configured` and the import stays `ready`: importing
// the skills a repository already has must not depend on a model (U2.7).
var ErrNotConfigured = errors.New("llm_not_configured")

// ErrUncertainCost marks a provider call that timed out after the request was
// sent. The charge is unknown, not zero, so it is recorded as `usd_uncertain`
// rather than guessed (U2.3).
var ErrUncertainCost = errors.New("generator_timeout_cost_uncertain")

// ErrCredentialMissing is what a remote generator returns when a request
// carries no organisation key and the deployment configured no fallback file
// either. The job ends `skipped` with `model_credential_missing` (ADR-0045):
// running the deployment's own key on the organisation's behalf is exactly
// the cross-tenant charge BYOK exists to prevent, so this is a stop, not a
// fallback.
var ErrCredentialMissing = errors.New("model_credential_missing")

// Document is one repository document offered to extraction.
type Document struct {
	Path   string
	SHA256 string
	Commit string
	Scope  string
	Owner  string
	Body   string
}

// Skill is one existing catalog skill offered to enrichment or consolidation.
type Skill struct {
	SkillID     string
	RevisionID  string
	Path        string
	SHA256      string
	Name        string
	Description string
	Scope       string
	Owner       string
	Body        string
}

// Limits bound one group's work. They come from the plan and the job's `limits`
// column, and the generator must respect them rather than trusting the caller
// to stop reading (API-CONTRACT §8).
type Limits struct {
	MaxProposals  int
	MaxNeighbours int
	MaxTokens     int
	MaxCalls      int
	MaxUSD        float64
}

// Request is one generation group: one scope's documents or skills.
type Request struct {
	Kind      string
	OrgID     string
	RepoID    string
	Scope     string
	Owner     string
	GroupID   string
	Documents []Document
	Skills    []Skill
	Limits    Limits
	// ScopeDirs maps a scope name to the real on-disk directory guidefold.yaml
	// declared for it (gfm.scopes, the longest literal prefix of the node's own
	// `paths`), keyed by every scope a candidate in this request might land in.
	// A scope missing here (nil map, zero-value caller, or a scope with no
	// stored prefix) falls back to candidatePath's dotted-name guess -- correct
	// only when a node's own directory happens to mirror its dotted name, which
	// is not guaranteed (2026-09-08 ACT-01 finding: `atlas.graph` sits at
	// `platforms/atlas/graph/**` in the Meridian fixture, not `atlas/graph/`).
	ScopeDirs map[string]string
	// APIKey travels on the request for exactly one call and is never assigned
	// to a field that outlives it -- a job payload, a checkpoint, a result, a
	// log line or an error string (ADR-0045). It names the organisation's own
	// stored credential, opened by internal/secrets.OpenFor just before this
	// request is built; empty means the caller found none, and a remote
	// generator falls back to its own deployment key file. The provider and
	// model stay out of Request: both are already fixed per deployment
	// (GUIDEFOLD_GENERATOR, GUIDEFOLD_GENERATOR_MODEL) and are part of Recipe,
	// which is itself part of the proposal cache key -- letting a request pick
	// its own model would let two requests with the same key generate under
	// different recipes, exactly the drift the cache key exists to prevent.
	APIKey string
}

// SourceRef points at the exact bytes a field came from.
type SourceRef struct {
	Path     string `json:"path"`
	SHA256   string `json:"sha256"`
	LineFrom int    `json:"line_from"`
	LineTo   int    `json:"line_to"`
}

// Field is one candidate field with its provenance. Either it names the source
// bytes it came from, or it says out loud that a person has to confirm it
// (PRODUCT-PIVOT U2: "każdy wygenerowany krok ma konkretny fragment źródła …
// albo »wymaga potwierdzenia«").
type Field struct {
	Field             string     `json:"field"`
	Origin            string     `json:"origin"`
	Value             string     `json:"-"`
	Ref               *SourceRef `json:"source_ref"`
	NeedsConfirmation bool       `json:"needs_confirmation"`
}

// Relation is one candidate edge. `derived_from` is what a consolidation owes
// its sources; `requires`/`refines` are authored structure.
//
// An edge normally leaves the candidate, so `From` is empty and the store fills
// in the candidate's own placeholder identity. A consolidation also needs the
// opposite direction — each *source* skill `refines` the shared element that was
// lifted out of it — and that is what `From` carries: the existing skill the
// edge starts at, with the candidate as its target. Without it the pyramid would
// only ever be readable downwards, and a card could never say "there is a child
// of this abstraction for your scope" (P08).
type Relation struct {
	Type string `json:"type"`
	To   string `json:"to"`
	From string `json:"from,omitempty"`
}

// Source is one input the candidate was built from, as the ProposalDetail DTO
// carries it (API-CONTRACT §5.4).
type Source struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Commit string `json:"commit,omitempty"`
	Lines  []int  `json:"lines,omitempty"`
}

// Candidate is one proposed skill package.
type Candidate struct {
	Name          string
	Slug          string
	Scope         string
	Owner         string
	Path          string
	Body          string
	Frontmatter   map[string]any
	TargetSkillID string
	Fields        []Field
	Relations     []Relation
	Sources       []Source
	// Identity distinguishes two candidates of the same group inside the cache
	// key, so a re-run collides with the row a person already decided on.
	Identity string
}

// Abstention is a group the generator deliberately produced nothing for. It is
// a result, not a failure: "correctly declining to consolidate" is measured
// separately from accuracy (PRODUCT-PIVOT U2 AC5).
type Abstention struct {
	Reason string   `json:"reason"`
	Skills []string `json:"skills"`
	Detail string   `json:"detail,omitempty"`
}

// Output is one group's result.
type Output struct {
	Candidates  []Candidate
	Abstentions []Abstention
}

// Cost is the JobCost DTO. `usd_uncertain` exists because a call that timed out
// after the request left may still be billed; unknown is not zero (U2.3).
type Cost struct {
	Calls        int     `json:"calls"`
	TokensIn     int     `json:"tokens_in"`
	TokensOut    int     `json:"tokens_out"`
	USDCertain   float64 `json:"usd_certain"`
	USDUncertain float64 `json:"usd_uncertain"`
}

// Add accumulates one call's cost into a running total.
func (c *Cost) Add(other Cost) {
	c.Calls += other.Calls
	c.TokensIn += other.TokensIn
	c.TokensOut += other.TokensOut
	c.USDCertain += other.USDCertain
	c.USDUncertain += other.USDUncertain
}

// Generator turns one group of inputs into candidates.
type Generator interface {
	Generate(ctx context.Context, req Request) (Output, Cost, error)
}

// Recipe identifies what produced a candidate. It is part of the cache key, so
// changing a prompt or a model revision produces new candidates rather than
// silently reusing old ones (API-CONTRACT §8).
type Recipe struct {
	Generator string `json:"generator"`
	Version   string `json:"version"`
	Model     string `json:"model,omitempty"`
}

// Names of the configured generators. NameOpenRouter matches
// internal/secrets.ProviderOpenRouter -- the two lists must name providers
// identically, since ForOrganisation dispatches on exactly the string
// OpenPreferred reads back out of gfm.org_credentials.
const (
	NameNone          = "none"
	NameDeterministic = "deterministic"
	NameOpenAI        = "openai"
	NameAnthropic     = "anthropic"
	NameOpenRouter    = "openrouter"
)

// Select builds the configured generator. `GUIDEFOLD_GENERATOR` is operator
// configuration and never a request field: which model a deployment pays for is
// not something a caller may choose.
func Select(env func(string) string) (Generator, Recipe, error) {
	if env == nil {
		env = os.Getenv
	}
	name := strings.TrimSpace(env("GUIDEFOLD_GENERATOR"))
	if name == "" {
		name = NameNone
	}
	switch name {
	case NameNone:
		return notConfigured{}, Recipe{Generator: NameNone, Version: "none"}, nil
	case NameDeterministic:
		g := &Deterministic{}
		return g, g.Recipe(), nil
	case NameOpenAI, NameAnthropic, NameOpenRouter:
		g, e := newRemote(name, env)
		if e != nil {
			return nil, Recipe{}, e
		}
		return g, g.Recipe(), nil
	}
	return nil, Recipe{}, fmt.Errorf("unknown_generator %q", name)
}

type notConfigured struct{}

func (notConfigured) Generate(context.Context, Request) (Output, Cost, error) {
	return Output{}, Cost{}, ErrNotConfigured
}

// CacheKey is sha256(org, sorted input digests, recipe version, model revision,
// candidate identity). Two runs over the same bytes with the same recipe
// produce the same key, so a rejected proposal is never regenerated
// (API-CONTRACT §8).
func CacheKey(orgID, kind string, inputs []string, recipe Recipe, identity string) string {
	sorted := append([]string{}, inputs...)
	sort.Strings(sorted)
	h := sha256.New()
	for _, part := range append([]string{orgID, kind}, sorted...) {
		h.Write([]byte(part))
		h.Write([]byte{0})
	}
	for _, part := range []string{recipe.Version, recipe.Model, identity} {
		h.Write([]byte(part))
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}

// InputDigests lists the digests of everything a request reads, which is the
// dedupe basis for the job and for every candidate it produces.
func InputDigests(req Request) []string {
	out := make([]string, 0, len(req.Documents)+len(req.Skills))
	for _, d := range req.Documents {
		out = append(out, d.SHA256)
	}
	for _, s := range req.Skills {
		out = append(out, s.SHA256)
	}
	sort.Strings(out)
	return out
}
