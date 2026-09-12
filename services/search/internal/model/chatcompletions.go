package model

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// chatCompletionsClient speaks OpenAI's /v1/chat/completions streaming
// shape. OpenRouter proxies many models through the identical wire format
// (same endpoint suffix, same SSE chunk shape, same Bearer auth) — the two
// providers differ in base URL and nothing about this type's own logic, so
// openai.go and openrouter.go each construct one rather than each
// reimplementing it. Anthropic's shape is different enough (auth header,
// body, SSE event names) that it gets its own type in anthropic.go instead
// of being forced into this one.
type chatCompletionsClient struct {
	provider string
	baseURL  string
	http     *http.Client
}

var _ Client = (*chatCompletionsClient)(nil)

func (c *chatCompletionsClient) Stream(ctx context.Context, req Request, onDelta DeltaFunc) (Usage, error) {
	if e := checkInputCeiling(req); e != nil {
		return Usage{}, e
	}
	messages := make([]map[string]string, 0, len(req.Messages)+1)
	if req.System != "" {
		messages = append(messages, map[string]string{"role": "system", "content": req.System})
	}
	for _, m := range req.Messages {
		messages = append(messages, map[string]string{"role": m.Role, "content": m.Content})
	}
	body := map[string]any{
		"model":    req.Model,
		"stream":   true,
		"messages": messages,
		// Requested explicitly: neither provider includes usage in a
		// streamed response by default, and a caller that asked for a
		// measured cost must not be quietly handed an estimate the
		// provider could have supplied.
		"stream_options": map[string]any{"include_usage": true},
	}
	if req.MaxOutputTokens > 0 {
		body["max_tokens"] = req.MaxOutputTokens
	}
	encoded, e := json.Marshal(body)
	if e != nil {
		return Usage{}, e
	}
	httpReq, e := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/chat/completions",
		bytes.NewReader(encoded))
	if e != nil {
		return Usage{}, e
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	httpReq.Header.Set("Accept", "text/event-stream")

	resp, e := c.http.Do(httpReq)
	if e != nil {
		return Usage{}, fmt.Errorf("model: %s request failed: %w", c.provider, e)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		return Usage{}, classifyFailure(resp.StatusCode, raw)
	}

	usage := Usage{Estimated: true}
	sawUsage := false
	outputChars := 0
	scanErr := scanSSE(resp.Body, func(ev sseEvent) bool {
		if ev.Data == "[DONE]" {
			return true
		}
		var chunk struct {
			Choices []struct {
				Delta struct {
					Content string `json:"content"`
				} `json:"delta"`
			} `json:"choices"`
			Usage *struct {
				PromptTokens     int `json:"prompt_tokens"`
				CompletionTokens int `json:"completion_tokens"`
			} `json:"usage"`
		}
		if json.Unmarshal([]byte(ev.Data), &chunk) != nil {
			// A chunk this package cannot parse is skipped rather than
			// aborting the stream: a provider that adds a field must not
			// turn every future call into a hard failure.
			return false
		}
		if chunk.Usage != nil {
			usage = Usage{TokensIn: chunk.Usage.PromptTokens, TokensOut: chunk.Usage.CompletionTokens}
			sawUsage = true
		}
		for _, choice := range chunk.Choices {
			if choice.Delta.Content != "" {
				outputChars += len(choice.Delta.Content)
				onDelta(choice.Delta.Content)
			}
		}
		return false
	})
	if scanErr != nil {
		return usage, fmt.Errorf("model: reading the %s response stream failed: %w", c.provider, scanErr)
	}
	if !sawUsage {
		usage = Usage{TokensIn: estimateTokensFromChars(promptChars(req)),
			TokensOut: estimateTokensFromChars(outputChars), Estimated: true}
	}
	return usage, nil
}

func promptChars(req Request) int {
	n := len(req.System)
	for _, m := range req.Messages {
		n += len(m.Content)
	}
	return n
}
