package ghapp

import (
	"context"
	"net/url"
)

// maxInstallationRepositoryPages bounds the walk, the same defensive ceiling
// ListPullRequestFiles applies to its own pagination.
const maxInstallationRepositoryPages = 50

// ListInstallationRepositories returns every repository the installation
// token can see (GET /installation/repositories), following pagination to
// the end. GitHub's own "installation" webhook payload can omit
// repositories for a large "All repositories" installation (its list is not
// guaranteed complete); this call is the authoritative source a worker
// reconciles gfm.repos from instead of trusting the webhook body
// (API-CONTRACT §4.7) — it runs here, in the worker, never in the webhook
// handler, which must not call GitHub at all.
func (c *Client) ListInstallationRepositories(ctx context.Context, installationID int64) ([]string, error) {
	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	next, err := c.apiURL("/installation/repositories", url.Values{"per_page": {"100"}})
	if err != nil {
		return nil, err
	}
	var fullNames []string
	for page := 0; next != "" && page < maxInstallationRepositoryPages; page++ {
		var body struct {
			Repositories []struct {
				FullName string `json:"full_name"`
			} `json:"repositories"`
		}
		link, err := c.getJSONPage(ctx, token, next, &body)
		if err != nil {
			return nil, err
		}
		for _, r := range body.Repositories {
			if r.FullName != "" {
				fullNames = append(fullNames, r.FullName)
			}
		}
		next = link
	}
	return fullNames, nil
}
