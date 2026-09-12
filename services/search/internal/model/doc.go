// Package model is a small streaming chat client over the three providers an
// organisation may hold a key for (ADR-0045): openrouter, anthropic, openai.
//
// It is a port, not a client library: a caller asks for "stream this
// conversation" and gets text deltas as they arrive plus a usage figure at
// the end, and the three implementations behind it differ only in endpoint,
// auth header and request/response shape — never in what a caller can rely
// on. That symmetry is what lets internal/agentrun call whichever provider
// the organisation configured without a provider-specific branch of its own.
//
// The organisation's own key (ADR-0045 point 3) is the caller's to hold and
// pass on Request.APIKey for the duration of one call; this package never
// logs it, never stores it, and never lets it reach a returned value or an
// error string — every error this package produces is checked for exactly
// that in its own tests.
//
// A caller that needs to branch on why a call failed has four named outcomes
// to match against with errors.Is: ErrQuotaExhausted, ErrRateLimited,
// ErrModelNotAvailable, ErrUnauthorized. Everything else is wrapped and
// carries no promise about its text — a caller that needs another branch is
// a caller this package is missing a named error for, the same rule
// internal/ghapp's errors.go states for its own package.
package model
