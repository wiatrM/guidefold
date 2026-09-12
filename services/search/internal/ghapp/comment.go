package ghapp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

// StickyCommentMarker opens every comment this package writes with
// UpsertStickyComment. It is exported so the worker that composes the
// comment body and this package's own tests agree on the exact bytes that
// identify "ours" among a pull request's other comments — a mismatch here
// would either duplicate the comment on every push or silently adopt
// somebody else's.
const StickyCommentMarker = "<!-- guidefold:pr-report -->"

// commentsPerPage is GitHub's own maximum for this endpoint; asking for it
// explicitly keeps the number of pages this operation might have to follow
// as small as GitHub allows.
const commentsPerPage = "100"

// UpsertStickyComment writes one comment per pull request: found by
// StickyCommentMarker at the top of its body, PATCHed when found, POSTed
// when not. ADR-0036 point 1a's coverage-bot report is rewritten on every
// push rather than accumulating a new comment each time, so finding the
// existing one is not optional — this operation pages through the full
// issue-comments listing before concluding there isn't one, because
// stopping at page one and posting a second comment is exactly the
// duplication this operation exists to avoid.
func (c *Client) UpsertStickyComment(ctx context.Context, installationID int64, fullName string, prNumber int, body string) error {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return err
	}
	finalBody := StickyCommentMarker + "\n" + body
	existingID, found, err := c.findStickyComment(ctx, token, fullName, prNumber)
	if err != nil {
		return err
	}
	if found {
		rawURL, err := c.apiURL(fmt.Sprintf("/repos/%s/issues/comments/%d", fullName, existingID), nil)
		if err != nil {
			return fmt.Errorf("ghapp: %w", err)
		}
		result, err := c.doWrite(ctx, token, http.MethodPatch, rawURL, map[string]string{"body": finalBody})
		if err != nil {
			return err
		}
		if result.status != http.StatusOK {
			return classifyWriteError(result.status, result.body)
		}
		return nil
	}
	rawURL, err := c.apiURL(fmt.Sprintf("/repos/%s/issues/%d/comments", fullName, prNumber), nil)
	if err != nil {
		return fmt.Errorf("ghapp: %w", err)
	}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, map[string]string{"body": finalBody})
	if err != nil {
		return err
	}
	if result.status != http.StatusCreated {
		return classifyWriteError(result.status, result.body)
	}
	return nil
}

// findStickyComment lists a pull request's issue comments a page at a time,
// following the Link: rel="next" header GitHub sends, until it finds one
// whose body starts with StickyCommentMarker or runs out of pages.
func (c *Client) findStickyComment(ctx context.Context, token, fullName string, prNumber int) (int64, bool, error) {
	rawURL, err := c.apiURL(fmt.Sprintf("/repos/%s/issues/%d/comments", fullName, prNumber),
		url.Values{"per_page": {commentsPerPage}})
	if err != nil {
		return 0, false, fmt.Errorf("ghapp: %w", err)
	}
	for rawURL != "" {
		id, found, next, err := c.findStickyCommentOnPage(ctx, token, rawURL)
		if err != nil {
			return 0, false, err
		}
		if found {
			return id, true, nil
		}
		rawURL = next
	}
	return 0, false, nil
}

func (c *Client) findStickyCommentOnPage(ctx context.Context, token, rawURL string) (id int64, found bool, next string, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return 0, false, "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	resp, err := c.http.Do(req)
	if err != nil {
		return 0, false, "", fmt.Errorf("ghapp: request to GitHub failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 0, false, "", fmt.Errorf("ghapp: GitHub answered %d listing pull request comments", resp.StatusCode)
	}
	var comments []struct {
		ID   int64  `json:"id"`
		Body string `json:"body"`
	}
	if decodeErr := json.NewDecoder(resp.Body).Decode(&comments); decodeErr != nil {
		return 0, false, "", fmt.Errorf("ghapp: GitHub answered unreadable JSON listing pull request comments: %w", decodeErr)
	}
	next = parseNextLink(resp.Header.Get("Link"))
	for _, comment := range comments {
		if strings.HasPrefix(comment.Body, StickyCommentMarker) {
			return comment.ID, true, "", nil
		}
	}
	return 0, false, next, nil
}

// parseNextLink extracts the rel="next" URL from a GitHub Link header
// (RFC 8288 form: `<url>; rel="next", <url2>; rel="last"`), or "" when there
// is no next page.
func parseNextLink(header string) string {
	if header == "" {
		return ""
	}
	for _, part := range strings.Split(header, ",") {
		segments := strings.Split(strings.TrimSpace(part), ";")
		if len(segments) < 2 {
			continue
		}
		target := strings.TrimSpace(segments[0])
		target = strings.TrimPrefix(target, "<")
		target = strings.TrimSuffix(target, ">")
		for _, attr := range segments[1:] {
			if strings.TrimSpace(attr) == `rel="next"` {
				return target
			}
		}
	}
	return ""
}
