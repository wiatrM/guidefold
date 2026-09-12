package model

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// anthropicAPIVersion is pinned the same way internal/review/generator pins
// it for its own non-streaming Anthropic call: a version this package has
// tested against, changed deliberately rather than picked up silently by
// whatever "latest" would mean on a given day.
const anthropicAPIVersion = "2023-06-01"

// defaultAnthropicMaxTokens is sent when Request.MaxOutputTokens is unset.
// Anthropic's Messages API requires max_tokens on every call — unlike
// OpenAI and OpenRouter, there is no "provider's own default" to fall back
// to, so this package has to supply one.
const defaultAnthropicMaxTokens = 4096

// anthropicClient speaks Anthropic's Messages API streaming shape: an
// x-api-key header instead of Bearer, a required anthropic-version header,
// system as a top-level field instead of a message, and named SSE events
// (content_block_delta, message_start, message_delta, error) instead of
// chat-completions' single implicit chunk shape.
type anthropicClient struct {
	baseURL string
	http    *http.Client
}

var _ Client = (*anthropicClient)(nil)

// newAnthropicClient builds the Anthropic concern. Base URL is overridable
// through ANTHROPIC_BASE_URL, the same variable internal/review/generator
// reads for its own Anthropic call.
func newAnthropicClient(env func(string) string, httpClient *http.Client) Client {
	return &anthropicClient{
		baseURL: firstNonEmpty(env("ANTHROPIC_BASE_URL"), "https://api.anthropic.com"),
		http:    httpClient,
	}
}

func (c *anthropicClient) Stream(ctx context.Context, req Request, onDelta DeltaFunc) (Usage, error) {
	if e := checkInputCeiling(req); e != nil {
		return Usage{}, e
	}
	messages := make([]map[string]string, 0, len(req.Messages))
	for _, m := range req.Messages {
		messages = append(messages, map[string]string{"role": m.Role, "content": m.Content})
	}
	maxTokens := req.MaxOutputTokens
	if maxTokens <= 0 {
		maxTokens = defaultAnthropicMaxTokens
	}
	body := map[string]any{
		"model":      req.Model,
		"max_tokens": maxTokens,
		"stream":     true,
		"messages":   messages,
	}
	if req.System != "" {
		body["system"] = req.System
	}
	encoded, e := json.Marshal(body)
	if e != nil {
		return Usage{}, e
	}
	httpReq, e := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/messages",
		bytes.NewReader(encoded))
	if e != nil {
		return Usage{}, e
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("x-api-key", req.APIKey)
	httpReq.Header.Set("anthropic-version", anthropicAPIVersion)
	httpReq.Header.Set("Accept", "text/event-stream")

	resp, e := c.http.Do(httpReq)
	if e != nil {
		return Usage{}, fmt.Errorf("model: anthropic request failed: %w", e)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		return Usage{}, classifyFailure(resp.StatusCode, raw)
	}

	usage := Usage{Estimated: true}
	sawOutputUsage := false
	inputTokens := 0
	outputChars := 0
	var streamErr error
	scanErr := scanSSE(resp.Body, func(ev sseEvent) bool {
		switch ev.Event {
		case "error":
			// Anthropic reports a mid-stream failure as an "error" event on
			// an otherwise-200 response, not as a non-200 status — the only
			// place this port has to classify a failure without an HTTP
			// status to key on.
			streamErr = classifyFailure(0, []byte(ev.Data))
			return true
		case "message_start":
			var msg struct {
				Message struct {
					Usage struct {
						InputTokens int `json:"input_tokens"`
					} `json:"usage"`
				} `json:"message"`
			}
			if json.Unmarshal([]byte(ev.Data), &msg) == nil {
				inputTokens = msg.Message.Usage.InputTokens
			}
		case "content_block_delta":
			var delta struct {
				Delta struct {
					Type string `json:"type"`
					Text string `json:"text"`
				} `json:"delta"`
			}
			if json.Unmarshal([]byte(ev.Data), &delta) == nil && delta.Delta.Type == "text_delta" && delta.Delta.Text != "" {
				outputChars += len(delta.Delta.Text)
				onDelta(delta.Delta.Text)
			}
		case "message_delta":
			var md struct {
				Usage struct {
					OutputTokens int `json:"output_tokens"`
				} `json:"usage"`
			}
			if json.Unmarshal([]byte(ev.Data), &md) == nil {
				usage = Usage{TokensIn: inputTokens, TokensOut: md.Usage.OutputTokens}
				sawOutputUsage = true
			}
		}
		return false
	})
	if streamErr != nil {
		return Usage{}, streamErr
	}
	if scanErr != nil {
		return usage, fmt.Errorf("model: reading the anthropic response stream failed: %w", scanErr)
	}
	if !sawOutputUsage {
		in := inputTokens
		if in == 0 {
			in = estimateTokensFromChars(promptChars(req))
		}
		usage = Usage{TokensIn: in, TokensOut: estimateTokensFromChars(outputChars), Estimated: true}
	}
	return usage, nil
}
