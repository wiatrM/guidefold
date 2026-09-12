package ghapp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
)

// ChangedFile is one entry of a pull request's file list: the path, and the
// unified diff GitHub calls the patch. The patch is absent for a file GitHub
// considers too large to diff, which is a normal state and not an error.
type ChangedFile struct {
	Path  string
	Patch string
}

// maxChangedFilePages bounds the walk. A pull request with more than five
// thousand changed files is not one anybody reviews, and an unbounded loop over
// somebody else's repository is a way to spend an afternoon inside one job.
const maxChangedFilePages = 50

// ListPullRequestFiles returns the files a pull request changes, following
// GitHub's pagination to the end.
//
// It lives here rather than in the caller because this package is the only one
// that holds an installation token, and the rule that the token never leaves it
// only survives if nobody else needs to mint one. A caller that re-implemented
// the JWT exchange to reach one more endpoint would have quietly moved the
// secret into a second package.
func (c *Client) ListPullRequestFiles(ctx context.Context, installationID int64, fullName string, prNumber int) ([]ChangedFile, error) {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	next, err := c.apiURL("/repos/"+fullName+"/pulls/"+strconv.Itoa(prNumber)+"/files",
		url.Values{"per_page": {"100"}})
	if err != nil {
		return nil, err
	}
	files := []ChangedFile{}
	for page := 0; next != "" && page < maxChangedFilePages; page++ {
		var body []struct {
			Filename string `json:"filename"`
			Patch    string `json:"patch"`
		}
		link, err := c.getJSONPage(ctx, token, next, &body)
		if err != nil {
			return nil, err
		}
		for _, f := range body {
			files = append(files, ChangedFile{Path: f.Filename, Patch: f.Patch})
		}
		next = link
	}
	return files, nil
}

// getJSONPage is getJSON plus the Link header, which pagination needs and a
// plain decode throws away.
func (c *Client) getJSONPage(ctx context.Context, token, rawURL string, out any) (nextURL string, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	resp, err := c.http.Do(req)
	if err != nil {
		return "", fmt.Errorf("ghapp: request to GitHub failed: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	switch {
	case resp.StatusCode == http.StatusNotFound:
		return "", ErrInstallationNotFound
	case resp.StatusCode == http.StatusForbidden:
		return "", ErrPermissionRefused
	case resp.StatusCode != http.StatusOK:
		return "", fmt.Errorf("ghapp: GitHub answered %d", resp.StatusCode)
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return "", fmt.Errorf("ghapp: GitHub answered unreadable JSON: %w", err)
	}
	return parseNextLink(resp.Header.Get("Link")), nil
}
