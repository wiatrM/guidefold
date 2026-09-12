package ghapp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

// OpenPullRequest opens a pull request from head into base. When one already
// exists for that head branch it returns the existing pull request's URL
// instead of failing: a retried ascend.run (ADR-0036 point 2) must not open
// a second pull request for the branch it already pushed to.
func (c *Client) OpenPullRequest(ctx context.Context, installationID int64, fullName, head, base, title, body string) (string, error) {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return "", err
	}
	rawURL, err := c.apiURL("/repos/"+fullName+"/pulls", nil)
	if err != nil {
		return "", fmt.Errorf("ghapp: %w", err)
	}
	payload := map[string]any{"title": title, "head": head, "base": base, "body": body}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, payload)
	if err != nil {
		return "", err
	}
	if result.status == http.StatusCreated {
		var out struct {
			HTMLURL string `json:"html_url"`
		}
		if err := json.Unmarshal(result.body, &out); err != nil {
			return "", fmt.Errorf("ghapp: pull request response is unreadable: %w", err)
		}
		if out.HTMLURL == "" {
			return "", fmt.Errorf("ghapp: pull request response carried no html_url")
		}
		return out.HTMLURL, nil
	}
	if result.status == http.StatusUnprocessableEntity && looksLikeAlreadyExists(result.body) {
		return c.existingPullRequestURL(ctx, token, fullName, head, base)
	}
	return "", classifyWriteError(result.status, result.body)
}

// looksLikeAlreadyExists recognises GitHub's 422 for "a pull request already
// exists for owner:head". GitHub puts the top-level message as the generic
// "Validation Failed" and the actual reason inside errors[].message, so both
// are checked; the check is on a substring rather than the exact sentence so
// a minor wording change does not turn "already open" into a hard failure.
func looksLikeAlreadyExists(body []byte) bool {
	if strings.Contains(strings.ToLower(githubMessage(body)), "already exists") {
		return true
	}
	var parsed struct {
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}
	if json.Unmarshal(body, &parsed) != nil {
		return false
	}
	for _, e := range parsed.Errors {
		if strings.Contains(strings.ToLower(e.Message), "already exists") {
			return true
		}
	}
	return false
}

// existingPullRequestURL looks up the open pull request for head (used only
// after GitHub's own 422 said one already exists), because the create
// response that 422 came with does not carry the existing PR's URL itself.
func (c *Client) existingPullRequestURL(ctx context.Context, token, fullName, head, base string) (string, error) {
	owner := fullName
	if i := strings.Index(fullName, "/"); i >= 0 {
		owner = fullName[:i]
	}
	query := url.Values{"head": {owner + ":" + head}, "state": {"open"}}
	if base != "" {
		query.Set("base", base)
	}
	rawURL, err := c.apiURL("/repos/"+fullName+"/pulls", query)
	if err != nil {
		return "", fmt.Errorf("ghapp: %w", err)
	}
	var list []struct {
		HTMLURL string `json:"html_url"`
	}
	if err := c.getJSON(ctx, token, rawURL, &list); err != nil {
		return "", err
	}
	if len(list) == 0 || list[0].HTMLURL == "" {
		return "", fmt.Errorf("ghapp: GitHub reported an existing pull request for %s but none was found", head)
	}
	return list[0].HTMLURL, nil
}
