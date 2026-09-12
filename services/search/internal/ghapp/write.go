package ghapp

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// maxWriteResponseBytes bounds how much of a write response this package
// will read into memory. GitHub's own write responses (a comment, a blob
// SHA, a commit) are small; this is defence against an httptest double or a
// misbehaving proxy answering with something unbounded, not a real GitHub
// response shape.
const maxWriteResponseBytes = 1 << 20

// writeResult is a write call's outcome before this package decides what it
// means: some callers treat 201 as success and 422 as "already exists, try
// something else", others treat 200 as success and everything else as
// failure. Deciding that once, in one struct, keeps that judgment out of the
// HTTP plumbing.
type writeResult struct {
	status int
	body   []byte
}

// doWrite issues one authenticated GitHub write (POST or PATCH) and returns
// its status and body without judging either — every caller in this package
// interprets those differently for its own endpoint.
func (c *Client) doWrite(ctx context.Context, token, method, rawURL string, payload any) (writeResult, error) {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return writeResult{}, err
	}
	req, err := http.NewRequestWithContext(ctx, method, rawURL, bytes.NewReader(encoded))
	if err != nil {
		return writeResult{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	resp, err := c.http.Do(req)
	if err != nil {
		return writeResult{}, fmt.Errorf("ghapp: request to GitHub failed: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, maxWriteResponseBytes))
	if err != nil {
		return writeResult{}, fmt.Errorf("ghapp: GitHub response is unreadable: %w", err)
	}
	return writeResult{status: resp.StatusCode, body: raw}, nil
}

// classifyWriteError turns an unexpected status into an error. 403 is
// singled out as ErrPermissionRefused — the organisation's fix for that is
// "re-approve the App's permissions", never a retry — everything else stays
// a plain wrapped failure with GitHub's own message, which is safe to
// include because it is GitHub's text, never anything this package holds
// secret.
func classifyWriteError(status int, body []byte) error {
	if status == http.StatusForbidden {
		return fmt.Errorf("%w: %s", ErrPermissionRefused, githubMessage(body))
	}
	return fmt.Errorf("ghapp: GitHub answered %d: %s", status, githubMessage(body))
}

func githubMessage(body []byte) string {
	var parsed struct {
		Message string `json:"message"`
	}
	if json.Unmarshal(body, &parsed) == nil && parsed.Message != "" {
		return parsed.Message
	}
	return "no message"
}
