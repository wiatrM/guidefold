package live

import (
	"context"
	"errors"

	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

// secretsCredentialSource adapts *secrets.Service to CredentialSource. It is
// the one place this package is allowed to know how a preferred credential
// is actually stored and opened; handleCreate only ever sees the interface.
type secretsCredentialSource struct{ secrets *secrets.Service }

// NewSecretsCredentialSource wires the concrete secrets service as this
// package's CredentialSource, the way the composition root wires every other
// module's dependency (see main.go and internal/pivottest).
//
// secrets.Service.OpenPreferred also hands back the credential's plaintext
// key, opened so the worker can call the model with it; this adapter reads
// only the provider and model it returns and discards the key immediately —
// it is never assigned to a variable this package logs, stores or returns,
// consistent with this package never opening the organisation's model key.
func NewSecretsCredentialSource(s *secrets.Service) CredentialSource {
	return secretsCredentialSource{secrets: s}
}

func (a secretsCredentialSource) PreferredProvider(ctx context.Context, orgID string) (provider, model string, err error) {
	provider, model, _, e := a.secrets.OpenPreferred(ctx, orgID)
	switch {
	case errors.Is(e, secrets.ErrNoCredential):
		return "", "", ErrNoPreferredCredential
	case errors.Is(e, secrets.ErrNoKeyring):
		return "", "", ErrCredentialStoreUnavailable
	case e != nil:
		return "", "", e
	}
	return provider, model, nil
}
