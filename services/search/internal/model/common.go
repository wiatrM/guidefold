package model

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

// providerErrorBody is the one JSON error shape all three providers publish
// closely enough to share a decoder: {"error":{"type","code","message"}}.
// Anthropic also sends this shape as an in-stream "error" event rather than
// (or in addition to) a non-200 status, which is why classification below
// takes the parsed fields rather than only an HTTP status.
type providerErrorBody struct {
	Error struct {
		Type    string `json:"type"`
		Code    any    `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func parseProviderError(body []byte) providerErrorBody {
	var parsed providerErrorBody
	_ = json.Unmarshal(body, &parsed)
	return parsed
}

// quotaMarkers and modelMarkers are the words this package keys the
// quota-vs-rate 429 split and the "this 400 actually means unknown model"
// question on. Neither API-CONTRACT §8 nor either provider's documentation
// names an exact machine-readable field for either distinction at the time
// this package was written, so this list is a judgment call, checked
// against real provider error text in this package's own tests — a caller
// that finds a provider using different wording is finding this list
// incomplete, not wrong in kind.
var quotaMarkers = []string{"insufficient_quota", "quota", "credit balance", "billing", "exceeded your current"}
var modelMarkers = []string{"does not exist", "not found", "unknown model", "invalid model", "unknown_model"}

func containsAny(haystack string, markers []string) bool {
	for _, m := range markers {
		if strings.Contains(haystack, m) {
			return true
		}
	}
	return false
}

// classifyFailure turns one failed call into a named outcome or a wrapped
// error. status is 0 for an in-stream error event that carried no HTTP
// status of its own (Anthropic's "error" SSE event on an otherwise-200
// response) — every branch below that inspects status only for a positive
// value keeps that path reachable for both callers.
func classifyFailure(status int, body []byte) error {
	pe := parseProviderError(body)
	text := strings.ToLower(pe.Error.Type + " " + pe.Error.Message + " " + fmt.Sprint(pe.Error.Code))

	switch status {
	case http.StatusPaymentRequired:
		return ErrQuotaExhausted
	case http.StatusUnauthorized:
		return ErrUnauthorized
	}
	if status == http.StatusTooManyRequests || strings.Contains(pe.Error.Type, "rate_limit") {
		if containsAny(text, quotaMarkers) {
			return ErrQuotaExhausted
		}
		return ErrRateLimited
	}
	if status == http.StatusNotFound || pe.Error.Type == "not_found_error" ||
		(strings.Contains(text, "model") && containsAny(text, modelMarkers)) {
		return ErrModelNotAvailable
	}
	if pe.Error.Type == "authentication_error" || pe.Error.Type == "permission_error" {
		return ErrUnauthorized
	}
	if containsAny(text, quotaMarkers) {
		return ErrQuotaExhausted
	}
	msg := pe.Error.Message
	if msg == "" {
		msg = "no message"
	}
	// The provider's own message is safe to include: it is text the
	// provider chose to send back about a request that never carried the
	// key anywhere but an Authorization/x-api-key header, never in the body
	// this message was parsed from.
	if status > 0 {
		return fmt.Errorf("model: provider answered %d: %s", status, msg)
	}
	return fmt.Errorf("model: provider reported an error: %s", msg)
}

// estimateTokensFromChars is the ~4-characters-per-token rule of thumb this
// package uses whenever a provider's own response carried no usage, or to
// check a prompt against MaxInputTokens before any request leaves this
// package (no provider accepts a parameter for that ceiling, so it has to
// be judged locally). It is never presented as a measurement: every Usage
// this produces carries Estimated: true.
func estimateTokensFromChars(n int) int {
	if n <= 0 {
		return 0
	}
	tokens := n / 4
	if tokens < 1 {
		tokens = 1
	}
	return tokens
}

// checkInputCeiling estimates the size of System plus every message and
// refuses the call before it leaves this package when Request.MaxInputTokens
// is set and would be exceeded.
func checkInputCeiling(req Request) error {
	if req.MaxInputTokens <= 0 {
		return nil
	}
	chars := len(req.System)
	for _, m := range req.Messages {
		chars += len(m.Content)
	}
	if estimated := estimateTokensFromChars(chars); estimated > req.MaxInputTokens {
		return fmt.Errorf("model: prompt estimated at %d tokens exceeds the %d-token input ceiling",
			estimated, req.MaxInputTokens)
	}
	return nil
}
