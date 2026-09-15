package generator

import (
	"context"
	"fmt"

	"github.com/wiatrM/guidefold/services/search/internal/review/domain"
)

var _ ScopeMapper = (*remote)(nil)

// ProposeScopeMap asks the provider for the organisation's structure.
//
// It reuses `call` -- the same one request, one timeout, one cost accounting
// the candidate path uses -- rather than opening a second way to reach a
// provider. What differs is only the prompt and the decoding, which is exactly
// what a second question should differ in.
//
// The budget is one call by contract (API-CONTRACT §8), so there is no retry
// loop here: a provider that answers with something other than the documented
// object has not been asked a question a second attempt would answer better,
// and the job reports the failure instead of spending again.
func (r *remote) ProposeScopeMap(ctx context.Context, req ScopeMapRequest) (domain.ScopeMap, Cost, error) {
	key, e := r.resolveKey(Request{APIKey: req.APIKey})
	if e != nil {
		return domain.ScopeMap{}, Cost{}, e
	}
	raw, cost, e := r.call(ctx, key, ScopeMapPrompt(req), 0)
	if e != nil {
		return domain.ScopeMap{}, cost, e
	}
	m, e := DecodeScopeMap(raw)
	if e != nil {
		return domain.ScopeMap{}, cost, fmt.Errorf("%s: %w", r.provider, e)
	}
	m.Model = r.model
	for _, repo := range req.Repos {
		m.Repos = append(m.Repos, repo.RepoID)
	}
	return m, cost, nil
}
