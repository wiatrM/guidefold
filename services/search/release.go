package main

import "context"

// Operator preflight. GPU shadow is checked here without making GPU availability
// a dependency of sparse serving readiness or starting background workers.
func verifyRelease(ctx context.Context, s *Store, shadow bool) error {
	c, err := s.catalog(ctx)
	if err != nil {
		return err
	}
	mode := env("GUIDEFOLD_RETRIEVAL_MODE", "sparse")
	if shadow {
		mode = "hybrid"
	}
	d, err := newDenseClientMode(mode)
	if err != nil {
		return err
	}
	result := M{"snapshot": c.ID, "repository": c.Repo, "tenant": s.Tenant,
		"policy_revision": c.PolicySHA, "router_index_revision": c.RouterIndexSHA,
		"pinned": s.SnapshotID != "", "encoder_id": nil}
	if d != nil {
		if err = d.ready(ctx); err != nil {
			return err
		}
		if err = d.verifyCatalog(ctx, s, c); err != nil {
			return err
		}
		result["encoder_id"] = d.ID
	}
	return printOperatorResult(result, nil)
}
