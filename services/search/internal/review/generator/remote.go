package generator

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

// The three HTTP providers. OpenRouter speaks the identical OpenAI-compatible
// wire protocol (same endpoint suffix, same request/response shape, same
// Bearer header) that request/readResponse already produce in their default,
// non-Anthropic branch, so it is this same type with a different endpoint and
// default model, not a second implementation. Anthropic's shape is different
// enough (auth header, body, SSE-free response) that it stays its own branch.
// Everything else — the prompt, the output schema, the retry rule, the cost
// accounting — is shared, because "which vendor" must not change what a
// proposal is allowed to claim.
//
// Three rules are not negotiable here.
//
// The key comes from a file (`OPENAI_API_KEY_FILE`, `ANTHROPIC_API_KEY_FILE`,
// `OPENROUTER_API_KEY_FILE`) or from one request's own Request.APIKey, is read
// per call, and is never logged, echoed or put in an error message
// (security-baseline).
//
// The output is validated against a JSON Schema before anything is believed. A
// model that answers with prose, with a missing `source_ref`, or with a step
// that carries neither a reference nor `needs_confirmation` is retried at most
// twice and then fails the group — a candidate without provenance is worse than
// no candidate (PRODUCT-PIVOT U2 AC2).
//
// A call that times out after the request left is charged to `usd_uncertain`.
// The provider may well bill it; pretending it was free would understate the
// cost of a run in exactly the report that is supposed to control it (U2.7).

// DefaultTimeout bounds one provider call.
const DefaultTimeout = 60 * time.Second

// maxJSONRetries is the "≤2 retry dla niepoprawnego JSON-a" of API-CONTRACT §8.
const maxJSONRetries = 2

// remote is the shared HTTP generator.
type remote struct {
	provider string
	model    string
	endpoint string
	keyFile  string
	client   *http.Client
	schema   *jsonschema.Schema
	// Pricing is USD per million tokens; zero means the deployment did not
	// configure it and the cost is reported as uncertain rather than as zero.
	inputUSDPerM, outputUSDPerM float64
}

var _ Generator = (*remote)(nil)

// baseRemote builds everything about a remote generator that is the same no
// matter which key ends up on a request: the endpoint, the timeout and the
// price list are deployment infrastructure (an operator still points
// OPENAI_BASE_URL at a private gateway, or prices a call, the same way
// whether the deployment's own key is used or an organisation's own is), read
// from env exactly once. modelOverride is deliberately a parameter rather
// than something this function reads from the environment itself: newRemote
// passes GUIDEFOLD_GENERATOR_MODEL (the deployment's own model), ForOrganisation
// passes the organisation's own stored model, and neither may leak into the
// other's remote -- an operator's deployment-wide model override must not
// silently apply to an organisation on a different provider (API-CONTRACT §8).
func baseRemote(provider, modelOverride string, env func(string) string) (*remote, error) {
	r := &remote{provider: provider, client: &http.Client{Timeout: DefaultTimeout}}
	switch provider {
	case NameOpenAI:
		r.model = firstNonEmpty(modelOverride, "gpt-4.1-mini")
		r.endpoint = firstNonEmpty(env("OPENAI_BASE_URL"), "https://api.openai.com") +
			"/v1/chat/completions"
	case NameAnthropic:
		r.model = firstNonEmpty(modelOverride, "claude-sonnet-4-5")
		r.endpoint = firstNonEmpty(env("ANTHROPIC_BASE_URL"), "https://api.anthropic.com") +
			"/v1/messages"
	case NameOpenRouter:
		r.model = firstNonEmpty(modelOverride, "openai/gpt-4o-mini")
		r.endpoint = firstNonEmpty(env("OPENROUTER_BASE_URL"), "https://openrouter.ai/api") +
			"/v1/chat/completions"
	default:
		return nil, fmt.Errorf("unknown_generator %q", provider)
	}
	if v := env("GUIDEFOLD_GENERATOR_TIMEOUT_SECONDS"); v != "" {
		n, e := strconv.Atoi(v)
		if e != nil || n < 1 || n > 600 {
			return nil, errors.New("invalid_generator_timeout")
		}
		r.client.Timeout = time.Duration(n) * time.Second
	}
	r.inputUSDPerM = envFloat(env, "GUIDEFOLD_GENERATOR_USD_PER_MTOK_IN")
	r.outputUSDPerM = envFloat(env, "GUIDEFOLD_GENERATOR_USD_PER_MTOK_OUT")
	schema, e := compileOutputSchema()
	if e != nil {
		return nil, e
	}
	r.schema = schema
	return r, nil
}

// newRemote builds the deployment's own configured generator (GUIDEFOLD_GENERATOR),
// with its own key file as the fallback a request's own key takes priority over.
func newRemote(provider string, env func(string) string) (*remote, error) {
	r, e := baseRemote(provider, env("GUIDEFOLD_GENERATOR_MODEL"), env)
	if e != nil {
		return nil, e
	}
	switch provider {
	case NameOpenAI:
		r.keyFile = env("OPENAI_API_KEY_FILE")
	case NameAnthropic:
		r.keyFile = env("ANTHROPIC_API_KEY_FILE")
	case NameOpenRouter:
		r.keyFile = env("OPENROUTER_API_KEY_FILE")
	}
	// No `*_API_KEY_FILE` is a valid deployment now (ADR-0045): a BYOK-only
	// installation may run this generator for organisations that each hold
	// their own key and none of the operator's. A request with neither an
	// organisation key nor this file ends the job `skipped` at Generate time,
	// which is where a caller can name it against the job instead of refusing
	// the whole worker at startup for a configuration that is only sometimes
	// wrong.
	r.keyFile = strings.TrimSpace(r.keyFile)
	return r, nil
}

// ForOrganisation builds a remote generator for one organisation's preferred
// provider and stored model (API-CONTRACT §8: "proposal.generate uruchomiony
// przez przebieg bierze klucz preferowanego dostawcy tej organizacji"). model
// empty means that provider's own default, exactly like an omitted `model` on
// PUT …/credentials/{provider} does. It carries no key file: this generator
// is bound to one organisation's own key for the lifetime of one job, and
// that key travels on Request.APIKey -- the same field and the same
// resolveKey priority a deployment-configured generator already uses -- so
// there is one key-carrying mechanism, not two. env is nil in production
// (os.Getenv); a test passes its own to point the endpoint at a fake server
// without touching the process environment.
func ForOrganisation(provider, model string, env func(string) string) (Generator, Recipe, error) {
	if env == nil {
		env = os.Getenv
	}
	r, e := baseRemote(provider, model, env)
	if e != nil {
		return nil, Recipe{}, e
	}
	return r, r.Recipe(), nil
}

// Recipe names the provider and the model revision. Both are part of the cache
// key, so switching models produces new candidates rather than reusing old ones.
func (r *remote) Recipe() Recipe {
	return Recipe{Generator: r.provider, Version: r.provider + "-1", Model: r.model}
}

// OutputSchema is the JSON Schema every provider answer must satisfy. It is the
// contract between "a model said something" and "a proposal exists".
const OutputSchema = `{
 "type": "object",
 "additionalProperties": false,
 "required": ["candidates"],
 "properties": {
  "candidates": {
   "type": "array",
   "maxItems": 20,
   "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["name", "purpose", "steps"],
    "properties": {
     "name": {"type": "string", "minLength": 1, "maxLength": 120},
     "purpose": {"type": "string", "minLength": 1, "maxLength": 2000},
     "when_to_use": {"type": "string", "maxLength": 2000},
     "when_not_to_use": {"type": "string", "maxLength": 2000},
     "verification": {"type": "string", "maxLength": 2000},
     "target_skill_id": {"type": "string", "maxLength": 300},
     "relations": {
      "type": "array", "maxItems": 20,
      "items": {
       "type": "object", "additionalProperties": false, "required": ["type", "to"],
       "properties": {
        "type": {"enum": ["derived_from", "requires", "refines", "similar", "conflicts_with"]},
        "to": {"type": "string", "minLength": 1}
       }
      }
     },
     "steps": {
      "type": "array", "minItems": 1, "maxItems": 50,
      "items": {
       "type": "object",
       "additionalProperties": false,
       "required": ["text"],
       "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 2000},
        "needs_confirmation": {"type": "boolean"},
        "source_ref": {
         "type": "object", "additionalProperties": false,
         "required": ["path", "sha256", "line_from", "line_to"],
         "properties": {
          "path": {"type": "string", "minLength": 1},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "line_from": {"type": "integer", "minimum": 1},
          "line_to": {"type": "integer", "minimum": 1}
         }
        }
       },
       "anyOf": [
        {"required": ["source_ref"]},
        {"properties": {"needs_confirmation": {"const": true}}, "required": ["needs_confirmation"]}
       ]
      }
     }
    }
   }
  },
  "abstentions": {
   "type": "array", "maxItems": 20,
   "items": {
    "type": "object", "additionalProperties": false, "required": ["reason"],
    "properties": {
     "reason": {"type": "string", "minLength": 1, "maxLength": 120},
     "detail": {"type": "string", "maxLength": 1000},
     "skills": {"type": "array", "items": {"type": "string"}}
    }
   }
  }
 }
}`

func compileOutputSchema() (*jsonschema.Schema, error) {
	doc, e := jsonschema.UnmarshalJSON(strings.NewReader(OutputSchema))
	if e != nil {
		return nil, e
	}
	c := jsonschema.NewCompiler()
	if e := c.AddResource("guidefold:generator-output", doc); e != nil {
		return nil, e
	}
	return c.Compile("guidefold:generator-output")
}

// modelOutput mirrors OutputSchema.
type modelOutput struct {
	Candidates []struct {
		Name          string     `json:"name"`
		Purpose       string     `json:"purpose"`
		WhenToUse     string     `json:"when_to_use"`
		WhenNotToUse  string     `json:"when_not_to_use"`
		Verification  string     `json:"verification"`
		TargetSkillID string     `json:"target_skill_id"`
		Relations     []Relation `json:"relations"`
		Steps         []struct {
			Text              string     `json:"text"`
			NeedsConfirmation bool       `json:"needs_confirmation"`
			SourceRef         *SourceRef `json:"source_ref"`
		} `json:"steps"`
	} `json:"candidates"`
	Abstentions []Abstention `json:"abstentions"`
}

// Generate asks the provider for one group's candidates.
//
// Limits.MaxCalls is the budget *left* for this group, not the job's original
// ceiling: the caller subtracts what earlier groups spent. It is counted here
// rather than only around the call, because one Generate makes up to
// maxJSONRetries+1 provider calls, and a ceiling only the caller enforces is a
// ceiling the owner can overshoot by that many calls per group (U2.7 promises
// the number shown in the plan is the number the worker enforces).
func (r *remote) Generate(ctx context.Context, req Request) (Output, Cost, error) {
	if req.Limits.MaxCalls < 0 {
		return Output{}, Cost{}, errors.New("generator_call_budget_exhausted")
	}
	key, e := r.resolveKey(req)
	if e != nil {
		return Output{}, Cost{}, e
	}
	prompt := Prompt(req)
	total := Cost{}
	var lastErr error
	for attempt := 0; attempt <= maxJSONRetries; attempt++ {
		if req.Limits.MaxCalls > 0 && total.Calls >= req.Limits.MaxCalls {
			if lastErr == nil {
				return Output{}, total, errors.New("generator_call_budget_exhausted")
			}
			return Output{}, total, fmt.Errorf("generator_call_budget_exhausted after %d call(s): %w",
				total.Calls, lastErr)
		}
		raw, cost, e := r.call(ctx, key, prompt, attempt)
		total.Add(cost)
		if e != nil {
			// A timeout is terminal: retrying a call that may already have been
			// billed multiplies an unknown charge.
			if errors.Is(e, ErrUncertainCost) {
				return Output{}, total, e
			}
			lastErr = e
			continue
		}
		out, e := r.decode(raw, req)
		if e == nil {
			return out, total, nil
		}
		lastErr = e
	}
	return Output{}, total, fmt.Errorf("generator_invalid_output after %d attempts: %w",
		maxJSONRetries+1, lastErr)
}

// resolveKey picks the request's own key over the deployment's file (ADR-0045:
// the organisation's key belongs to the organisation, so it is used whenever
// the caller supplied one) and falls back to the file only when the request
// carries none, which is how an organisation with no stored credential keeps
// working exactly as it did before this field existed. Neither exists (a
// BYOK-only deployment with no fallback file, for an organisation that never
// stored a key) ends the request with ErrCredentialMissing rather than
// silently running on nobody's key.
func (r *remote) resolveKey(req Request) (string, error) {
	if req.APIKey != "" {
		return req.APIKey, nil
	}
	if r.keyFile == "" {
		return "", ErrCredentialMissing
	}
	return readKey(r.keyFile)
}

// call performs one provider request. `raw` is the model's message text.
func (r *remote) call(ctx context.Context, key, prompt string, attempt int) (string, Cost, error) {
	instruction := prompt
	if attempt > 0 {
		instruction += "\n\nThe previous answer was not valid against the schema. " +
			"Answer with JSON only, matching the schema exactly."
	}
	body, header := r.request(instruction)
	encoded, e := json.Marshal(body)
	if e != nil {
		return "", Cost{}, e
	}
	call, cancel := context.WithTimeout(ctx, r.client.Timeout)
	defer cancel()
	httpReq, e := http.NewRequestWithContext(call, http.MethodPost, r.endpoint, bytes.NewReader(encoded))
	if e != nil {
		return "", Cost{}, e
	}
	httpReq.Header.Set("Content-Type", "application/json")
	for k, v := range header(key) {
		httpReq.Header.Set(k, v)
	}
	resp, e := r.client.Do(httpReq)
	if e != nil {
		if errors.Is(e, context.DeadlineExceeded) || errors.Is(call.Err(), context.DeadlineExceeded) {
			// The request left; the charge is unknown, not zero.
			return "", Cost{Calls: 1, USDUncertain: r.estimate(len(instruction)/4, 0)}, ErrUncertainCost
		}
		return "", Cost{Calls: 1}, fmt.Errorf("%s request failed: %w", r.provider, e)
	}
	defer resp.Body.Close()
	var payload map[string]any
	dec := json.NewDecoder(resp.Body)
	if e := dec.Decode(&payload); e != nil {
		return "", Cost{Calls: 1}, fmt.Errorf("%s answered with unreadable JSON", r.provider)
	}
	if resp.StatusCode != http.StatusOK {
		// The provider's own message is not echoed: it can carry the prompt back.
		return "", Cost{Calls: 1}, fmt.Errorf("%s answered %d", r.provider, resp.StatusCode)
	}
	text, in, out := r.readResponse(payload)
	cost := Cost{Calls: 1, TokensIn: in, TokensOut: out, USDCertain: r.estimate(in, out)}
	if r.inputUSDPerM == 0 && r.outputUSDPerM == 0 {
		// No configured price list: the call happened and cost something the
		// service cannot name. Uncertain, not zero.
		cost.USDCertain, cost.USDUncertain = 0, 0
	}
	if text == "" {
		return "", cost, fmt.Errorf("%s answered with no content", r.provider)
	}
	return text, cost, nil
}

func (r *remote) request(prompt string) (map[string]any, func(string) map[string]string) {
	if r.provider == NameAnthropic {
		return map[string]any{
				"model":      r.model,
				"max_tokens": 4096,
				"system":     systemPrompt,
				"messages":   []any{map[string]any{"role": "user", "content": prompt}},
			}, func(key string) map[string]string {
				return map[string]string{"x-api-key": key, "anthropic-version": "2023-06-01"}
			}
	}
	return map[string]any{
			"model":           r.model,
			"response_format": map[string]any{"type": "json_object"},
			"messages": []any{
				map[string]any{"role": "system", "content": systemPrompt},
				map[string]any{"role": "user", "content": prompt},
			},
		}, func(key string) map[string]string {
			return map[string]string{"Authorization": "Bearer " + key}
		}
}

func (r *remote) readResponse(payload map[string]any) (string, int, int) {
	in, out := 0, 0
	if usage, ok := payload["usage"].(map[string]any); ok {
		in = intOf(usage["prompt_tokens"]) + intOf(usage["input_tokens"])
		out = intOf(usage["completion_tokens"]) + intOf(usage["output_tokens"])
	}
	if r.provider == NameAnthropic {
		blocks, _ := payload["content"].([]any)
		var b strings.Builder
		for _, block := range blocks {
			m, _ := block.(map[string]any)
			if m != nil && m["type"] == "text" {
				b.WriteString(stringOf(m["text"]))
			}
		}
		return b.String(), in, out
	}
	choices, _ := payload["choices"].([]any)
	if len(choices) == 0 {
		return "", in, out
	}
	choice, _ := choices[0].(map[string]any)
	message, _ := choice["message"].(map[string]any)
	return stringOf(message["content"]), in, out
}

// decode validates the model's text against the schema and turns it into
// candidates. Everything a model produces is `inferred` unless it named the
// exact bytes it read; nothing it says makes a field `source`.
func (r *remote) decode(raw string, req Request) (Output, error) {
	text := strings.TrimSpace(raw)
	if i := strings.Index(text, "{"); i > 0 {
		text = text[i:]
	}
	if j := strings.LastIndex(text, "}"); j >= 0 && j+1 < len(text) {
		text = text[:j+1]
	}
	value, e := jsonschema.UnmarshalJSON(strings.NewReader(text))
	if e != nil {
		return Output{}, fmt.Errorf("answer is not JSON: %w", e)
	}
	if e := r.schema.Validate(value); e != nil {
		return Output{}, fmt.Errorf("answer does not match the output schema: %w", e)
	}
	var parsed modelOutput
	if e := json.Unmarshal([]byte(text), &parsed); e != nil {
		return Output{}, e
	}
	known := map[string]Document{}
	for _, d := range req.Documents {
		known[d.Path] = d
	}
	out := Output{Candidates: []Candidate{}, Abstentions: []Abstention{}}
	out.Abstentions = append(out.Abstentions, parsed.Abstentions...)
	for _, c := range parsed.Candidates {
		if req.Limits.MaxProposals > 0 && len(out.Candidates) >= req.Limits.MaxProposals {
			break
		}
		fields := []Field{{Field: "purpose", Origin: OriginInferred, Value: c.Purpose,
			NeedsConfirmation: true}}
		lines := []string{}
		for i, step := range c.Steps {
			f := Field{Field: fmt.Sprintf("steps[%d]", i), Origin: OriginInferred, Value: step.Text,
				NeedsConfirmation: true}
			// A reference is believed only when it points at a document this
			// request actually supplied, at that document's digest. Anything
			// else is a fabricated citation.
			if ref := step.SourceRef; ref != nil {
				if doc, ok := known[ref.Path]; ok && doc.SHA256 == ref.SHA256 {
					f.Origin, f.Ref, f.NeedsConfirmation = OriginParsed, ref, false
				}
			}
			fields = append(fields, f)
			lines = append(lines, fmt.Sprintf("%d. %s", i+1, step.Text))
		}
		for name, value := range map[string]string{"when_to_use": c.WhenToUse,
			"when_not_to_use": c.WhenNotToUse, "verification": c.Verification} {
			fields = append(fields, Field{Field: name, Origin: OriginInferred, Value: value,
				NeedsConfirmation: true})
		}
		sortFields(fields)
		slug := Slug(c.Name)
		frontmatter := map[string]any{
			"name":        slug,
			"description": "[" + scopeLabel(req.Scope) + "] " + firstSentence(c.Purpose),
			"metadata": map[string]any{"scope": req.Scope, "owner": nullEmpty(req.Owner),
				"layer": "task"},
		}
		body := renderCandidate(c.Name, frontmatter, []bodySection{
			{"Purpose", c.Purpose},
			{"When to use", c.WhenToUse},
			{"When not to use", c.WhenNotToUse},
			{"Steps", strings.Join(lines, "\n")},
			{"Verification", c.Verification},
		})
		sources := []Source{}
		for _, d := range req.Documents {
			sources = append(sources, Source{Path: d.Path, SHA256: d.SHA256, Commit: d.Commit})
		}
		for _, s := range req.Skills {
			sources = append(sources, Source{Path: s.Path, SHA256: s.SHA256})
		}
		relations := c.Relations
		if relations == nil {
			relations = []Relation{}
		}
		out.Candidates = append(out.Candidates, Candidate{
			Name: c.Name, Slug: slug, Scope: req.Scope, Owner: req.Owner,
			Path: candidatePath(req.Scope, slug, req.ScopeDirs), Body: body, Frontmatter: frontmatter,
			TargetSkillID: c.TargetSkillID, Fields: fields, Relations: relations,
			Sources: sources, Identity: req.Kind + ":" + slug,
		})
	}
	return out, nil
}

const systemPrompt = "You extract reusable engineering skills from repository documents. " +
	"Answer with JSON only, matching the supplied schema. Every step must either carry a " +
	"source_ref naming the exact document path, its sha256 and the line range you read it " +
	"from, or set needs_confirmation to true. Never invent a source_ref."

// Prompt renders one group as the user message. It is exported so a test can
// assert what leaves the process: the prompt carries repository text, and what
// it carries is a security decision, not a formatting detail.
func Prompt(req Request) string {
	var b strings.Builder
	fmt.Fprintf(&b, "Kind: %s\nScope: %s\n", req.Kind, scopeLabel(req.Scope))
	if req.Owner != "" {
		fmt.Fprintf(&b, "Owner: %s\n", req.Owner)
	}
	fmt.Fprintf(&b, "Produce at most %d candidates.\n", max(1, req.Limits.MaxProposals))
	b.WriteString("\nSchema:\n")
	b.WriteString(OutputSchema)
	for _, d := range req.Documents {
		fmt.Fprintf(&b, "\n\n=== document %s sha256=%s ===\n", d.Path, d.SHA256)
		b.WriteString(numbered(d.Body, req.Limits.MaxTokens))
	}
	for _, s := range req.Skills {
		fmt.Fprintf(&b, "\n\n=== skill %s path=%s sha256=%s ===\n", s.SkillID, s.Path, s.SHA256)
		b.WriteString(numbered(s.Body, req.Limits.MaxTokens))
	}
	return b.String()
}

// numbered prefixes each line with its number so a model can cite line ranges
// that the decoder can then check against the file it was given.
func numbered(body string, maxTokens int) string {
	lines := strings.Split(strings.ReplaceAll(body, "\r\n", "\n"), "\n")
	var b strings.Builder
	for i, l := range lines {
		if maxTokens > 0 && b.Len()/4 > maxTokens {
			fmt.Fprintf(&b, "… truncated at line %d of %d\n", i, len(lines))
			break
		}
		fmt.Fprintf(&b, "%d: %s\n", i+1, l)
	}
	return b.String()
}

func (r *remote) estimate(in, out int) float64 {
	return float64(in)*r.inputUSDPerM/1e6 + float64(out)*r.outputUSDPerM/1e6
}

// readKey reads the provider secret from its file on every call, so revoking it
// takes effect without a restart. The value never leaves this function except
// as a request header.
func readKey(path string) (string, error) {
	raw, e := os.ReadFile(path)
	if e != nil {
		// The path, not the contents: an error message is not a place for a key.
		return "", fmt.Errorf("generator key file is unreadable")
	}
	key := strings.TrimSpace(string(raw))
	if key == "" {
		return "", errors.New("generator key file is empty")
	}
	return key, nil
}

func sortFields(fields []Field) {
	// Stable, name-ordered provenance so two runs write the same rows.
	for i := 1; i < len(fields); i++ {
		for j := i; j > 0 && fields[j].Field < fields[j-1].Field; j-- {
			fields[j], fields[j-1] = fields[j-1], fields[j]
		}
	}
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if strings.TrimSpace(v) != "" {
			return strings.TrimSuffix(strings.TrimSpace(v), "/")
		}
	}
	return ""
}

func envFloat(env func(string) string, name string) float64 {
	v, e := strconv.ParseFloat(strings.TrimSpace(env(name)), 64)
	if e != nil || v < 0 {
		return 0
	}
	return v
}

func intOf(v any) int {
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case json.Number:
		i, _ := n.Int64()
		return int(i)
	}
	return 0
}

func stringOf(v any) string { s, _ := v.(string); return s }
