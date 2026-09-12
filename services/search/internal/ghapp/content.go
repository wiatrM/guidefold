package ghapp

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
)

// MaxFileBytes is the read ceiling ReadFile enforces. 256 KiB is generous for
// a SKILL.md or an AGENTS.md — both are meant to be read by a human — while
// still bounding what one live.repo job can be made to pull into memory by a
// repository that put something else at a matching path.
const MaxFileBytes = 256 * 1024

// ListSkillFiles returns the repository paths, at ref, that a live run or
// ascent reads: AGENTS.md at the root and every **/.agents/skills/**/SKILL.md.
// It uses the git trees API with recursive=1 — one call regardless of
// repository depth — rather than walking directories one contents-API call
// at a time.
func (c *Client) ListSkillFiles(ctx context.Context, installationID int64, fullName, ref string) ([]string, error) {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	rawURL, err := c.treesURL(fullName, ref)
	if err != nil {
		return nil, fmt.Errorf("ghapp: %w", err)
	}
	var body struct {
		Tree []struct {
			Path string `json:"path"`
			Type string `json:"type"`
		} `json:"tree"`
		Truncated bool `json:"truncated"`
	}
	if err := c.getJSON(ctx, token, rawURL, &body); err != nil {
		return nil, err
	}
	if body.Truncated {
		// A truncated tree that we filtered anyway could look like a complete
		// list of every skill in the repository while missing every one past
		// the point GitHub stopped. ADR-0046 point 3 treats that as a failure
		// worth naming, not a smaller-than-expected success.
		return nil, ErrTreeTruncated
	}
	files := make([]string, 0, len(body.Tree))
	for _, entry := range body.Tree {
		if entry.Type == "blob" && isSkillFile(entry.Path) {
			files = append(files, entry.Path)
		}
	}
	sort.Strings(files) // deterministic order: two runs over the same tree agree
	return files, nil
}

// ReadFile returns the decoded bytes of one file at ref, through the
// contents API. It refuses anything over MaxFileBytes outright rather than
// returning a prefix: a caller that parses a truncated SKILL.md as if it
// were the whole file would extract knowledge the repository does not
// actually contain.
func (c *Client) ReadFile(ctx context.Context, installationID int64, fullName, ref, path string) ([]byte, error) {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	rawURL, err := c.contentsURL(fullName, path, ref)
	if err != nil {
		return nil, fmt.Errorf("ghapp: %w", err)
	}
	var body struct {
		Content  string `json:"content"`
		Encoding string `json:"encoding"`
		Size     int    `json:"size"`
		Type     string `json:"type"`
	}
	if err := c.getJSON(ctx, token, rawURL, &body); err != nil {
		return nil, err
	}
	if body.Type != "" && body.Type != "file" {
		return nil, fmt.Errorf("ghapp: %s is a %s, not a file", path, body.Type)
	}
	if body.Size > MaxFileBytes {
		// Checked against the size GitHub already reported, before touching
		// the (already-fetched) content field, so an oversize file never gets
		// as far as a base64 decode.
		return nil, ErrFileTooLarge
	}
	if body.Encoding != "base64" {
		return nil, fmt.Errorf("ghapp: %s came back with unsupported encoding %q", path, body.Encoding)
	}
	decoded, err := base64.StdEncoding.DecodeString(strings.ReplaceAll(body.Content, "\n", ""))
	if err != nil {
		return nil, fmt.Errorf("ghapp: %s content is not valid base64: %w", path, err)
	}
	if len(decoded) > MaxFileBytes {
		// Defence in depth: the decoded length is checked again in case
		// GitHub's reported size ever disagreed with what it actually sent.
		return nil, ErrFileTooLarge
	}
	return decoded, nil
}

// isSkillFile matches "AGENTS.md" at the root and
// "**/.agents/skills/**/SKILL.md" — a skill file always lives one or more
// directories below skills/, named after the skill, never directly as
// ".agents/skills/SKILL.md".
func isSkillFile(path string) bool {
	if path == "AGENTS.md" {
		return true
	}
	segments := strings.Split(path, "/")
	for i := 0; i+1 < len(segments); i++ {
		if segments[i] != ".agents" || segments[i+1] != "skills" {
			continue
		}
		rest := segments[i+2:]
		if len(rest) >= 2 && rest[len(rest)-1] == "SKILL.md" {
			return true
		}
	}
	return false
}

// getJSON is the one HTTP round trip both content operations make: an
// installation-token-authenticated GET, decoded as JSON. Every non-200 or
// undecodable answer is wrapped with context and returned as-is — this
// package names only the four errors in errors.go as ones worth branching
// on; everything else here is just "GitHub did not answer the way this call
// needed".
func (c *Client) getJSON(ctx context.Context, token, rawURL string, out any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("ghapp: request to GitHub failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ghapp: GitHub answered %d", resp.StatusCode)
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("ghapp: GitHub answered unreadable JSON: %w", err)
	}
	return nil
}

// treesURL and contentsURL build the request URL by setting url.URL.Path (the
// decoded form) and letting String() escape it, so a fullName, ref or path
// containing characters that need percent-encoding is handled correctly
// without this package hand-rolling escaping rules for GitHub's API.
func (c *Client) treesURL(fullName, ref string) (string, error) {
	return c.apiURL("/repos/"+fullName+"/git/trees/"+ref, url.Values{"recursive": {"1"}})
}

func (c *Client) contentsURL(fullName, path, ref string) (string, error) {
	q := url.Values{}
	if ref != "" {
		q.Set("ref", ref)
	}
	return c.apiURL("/repos/"+fullName+"/contents/"+path, q)
}

func (c *Client) apiURL(pathSuffix string, query url.Values) (string, error) {
	base, err := url.Parse(c.baseURL)
	if err != nil {
		return "", fmt.Errorf("invalid GitHub API base URL: %w", err)
	}
	resolved := *base
	resolved.Path = strings.TrimSuffix(base.Path, "/") + pathSuffix
	if query != nil {
		resolved.RawQuery = query.Encode()
	}
	return resolved.String(), nil
}
