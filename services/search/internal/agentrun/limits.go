package agentrun

import "encoding/json"

// Default ceilings for a Live Agent run. API-CONTRACT §8 names the three
// categories a run must enforce (max repositories, max input tokens per
// repository, max spend in USD) but — as of this change — no endpoint field
// lets an owner set the latter two per run: POST {org_base}/live/runs
// accepts only prompt/provider/model/repos, and gfm.live_runs.limits is
// written nowhere. These numbers are this package's own judgment call for
// what "a hard ceiling" defaults to until a request field exists; live.plan
// writes them into the run row it plans, so the console can show what was
// actually enforced rather than an empty '{}'.
const (
	DefaultMaxUSD            = 2.0
	DefaultMaxTokensPerRepo  = 50000
	DefaultMaxFiles          = 200
	DefaultMaxOutputTokens   = 2048
)

// Limits is what a live.repo job reads from its own `limits` column —
// mirroring internal/review's own Limits-on-the-job-row pattern rather than
// a per-call read of the run row, so a job resumed after a crash enforces
// the same ceiling it started with even if an operator changed the defaults
// meanwhile.
type Limits struct {
	MaxUSD          float64 `json:"max_usd"`
	MaxTokens       int     `json:"max_tokens"`
	MaxFiles        int     `json:"max_files"`
	MaxOutputTokens int     `json:"max_output_tokens"`
}

// DefaultLimits is what a run gets when nothing more specific overrides it.
func DefaultLimits() Limits {
	return Limits{MaxUSD: DefaultMaxUSD, MaxTokens: DefaultMaxTokensPerRepo,
		MaxFiles: DefaultMaxFiles, MaxOutputTokens: DefaultMaxOutputTokens}
}

func decodeLimits(raw json.RawMessage) Limits {
	limits := DefaultLimits()
	if len(raw) == 0 {
		return limits
	}
	var partial Limits
	if json.Unmarshal(raw, &partial) != nil {
		return limits
	}
	if partial.MaxUSD > 0 {
		limits.MaxUSD = partial.MaxUSD
	}
	if partial.MaxTokens > 0 {
		limits.MaxTokens = partial.MaxTokens
	}
	if partial.MaxFiles > 0 {
		limits.MaxFiles = partial.MaxFiles
	}
	if partial.MaxOutputTokens > 0 {
		limits.MaxOutputTokens = partial.MaxOutputTokens
	}
	return limits
}
