package model

import "errors"

// These are the errors a caller is expected to branch on — internal/agentrun
// turns ErrQuotaExhausted into the run's own model_quota_exhausted and
// refuses to retry it (ADR-0036 point 4a: a retry against an exhausted
// account produces charges on someone else's bill and no output).
// Everything else this package returns is wrapped with fmt.Errorf and
// carries no promise about its text, the same rule internal/ghapp's
// errors.go states for its own package.
var (
	// ErrQuotaExhausted means the provider will not serve this key another
	// token: HTTP 402, or a 429 whose body marks the refusal as quota
	// rather than rate (API-CONTRACT §8). Retrying it spends nothing new on
	// the model — the account has none left — and produces no output.
	ErrQuotaExhausted = errors.New("model: the provider account has no quota left")

	// ErrRateLimited is an ordinary 429: the account has quota, but this
	// request arrived too fast. Unlike ErrQuotaExhausted, a caller may
	// retry this one after a backoff.
	ErrRateLimited = errors.New("model: the provider rate-limited this request")

	// ErrModelNotAvailable means the provider does not know Request.Model —
	// a typo, a retired model, or one this account cannot reach. Retrying
	// the same request changes nothing.
	ErrModelNotAvailable = errors.New("model: the provider does not know this model")

	// ErrUnauthorized means the provider rejected the key itself, not the
	// request. The organisation's stored credential (ADR-0045) is bad and
	// needs replacing; retrying with the same key cannot succeed.
	ErrUnauthorized = errors.New("model: the provider rejected this key")
)
