package secrets

import (
	"context"
	"errors"
	"net/http"
	"regexp"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// The closed domain of model providers (§4.8). A key belongs to one provider,
// so an organisation can hold several at once: OpenRouter reaches many models
// through one account, while Anthropic and OpenAI are the direct routes an
// organisation that already has an account with them will want to use. The
// table's CHECK, this list and the OpenAPI enum change together.
const (
	ProviderOpenRouter = "openrouter"
	ProviderAnthropic  = "anthropic"
	ProviderOpenAI     = "openai"
)

// Providers lists the domain in the order the console shows it.
var Providers = []string{ProviderOpenRouter, ProviderAnthropic, ProviderOpenAI}

// modelShape mirrors internal/live's modelShape exactly (§4.8): providers use
// slashes, dots, colons and dashes, never whitespace. There is deliberately no
// closed list of models here either, for the same reason live.go gives — the
// catalog belongs to the provider and changes weekly.
var modelShape = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,119}$`)

func knownProvider(p string) bool {
	for _, known := range Providers {
		if p == known {
			return true
		}
	}
	return false
}

// Verifier asks the provider whether a key works. It is a port so a test can
// run the whole write path without a network, and so a provider outage is one
// named failure rather than a stack trace.
type Verifier interface {
	Verify(ctx context.Context, provider, apiKey string) error
}

// ErrRejected is what a Verifier returns for a key the provider does not
// accept. Anything else is treated as "we could not tell", which is not the
// same answer and must not be reported as an invalid key.
var ErrRejected = errors.New("secrets: the provider rejected this key")

// Credential is the metadata half of a stored key: everything the API is
// willing to say about it.
type Credential struct {
	Provider  string  `json:"provider"`
	Name      string  `json:"name"`
	Last4     string  `json:"last4"`
	Model     string  `json:"model"`
	Preferred bool    `json:"preferred"`
	CreatedAt any     `json:"created_at"`
	CreatedBy *string `json:"created_by"`
}

// Service owns gfm.org_credentials and the three routes over it.
type Service struct {
	pool     *pgxpool.Pool
	keyring  *Keyring
	verifier Verifier
}

// New builds the service. A nil keyring is a valid state: the routes then
// answer `secret_encryption_unavailable` instead of storing a key in the clear.
func New(pool *pgxpool.Pool, keyring *Keyring, verifier Verifier) *Service {
	return &Service{pool: pool, keyring: keyring, verifier: verifier}
}

// Register mounts the credential routes. Reading the metadata is a member's
// right; writing and deleting are the owner's, with CSRF, like every other
// management mutation.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/credentials", s.handleList)
	r.Handle(http.MethodPut, "/api/v1/orgs/{org}/credentials/{provider}", s.handlePut)
	r.Handle(http.MethodPatch, "/api/v1/orgs/{org}/credentials/{provider}", s.handlePatch)
	r.Handle(http.MethodDelete, "/api/v1/orgs/{org}/credentials/{provider}", s.handleDelete)
}

// OpenFor returns the plaintext key of one organisation, or ErrNoCredential
// when it has none. It is the only read path that produces a plaintext, and the
// worker is its only caller.
func (s *Service) OpenFor(ctx context.Context, orgID, provider string) (string, error) {
	return OpenFor(ctx, s.pool, s.keyring, orgID, provider)
}

// OpenPreferred resolves the organisation's preferred credential (§4.8, §5.5a)
// and returns the provider and model stored beside it together with the
// opened key. It is OpenFor's sibling for work that takes whichever provider
// the organisation chose rather than one it names, and it returns
// ErrNoCredential the same way OpenFor does when the organisation has none —
// there is no third state where a preferred row exists but does not resolve.
// The plaintext key it returns must stay in memory only: never logged, never
// put on a job payload, checkpoint, result or error string.
func (s *Service) OpenPreferred(ctx context.Context, orgID string) (provider, model, key string, err error) {
	return OpenPreferred(ctx, s.pool, s.keyring, orgID)
}

// ErrNoCredential says this organisation has not stored a key for the provider.
var ErrNoCredential = errors.New("secrets: no credential for this organisation")

// OpenFor is the package-level form, so the worker can use it without holding
// the HTTP service.
func OpenFor(ctx context.Context, pool *pgxpool.Pool, keyring *Keyring, orgID, provider string) (string, error) {
	if keyring == nil {
		return "", ErrNoKeyring
	}
	var keyID string
	var nonce, ciphertext []byte
	e := pool.QueryRow(ctx, `SELECT key_id,nonce,ciphertext FROM gfm.org_credentials
 WHERE org_id=$1::uuid AND provider=$2`, orgID, provider).Scan(&keyID, &nonce, &ciphertext)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", ErrNoCredential
	}
	if e != nil {
		return "", e
	}
	return keyring.Open(orgID, provider, keyID, nonce, ciphertext)
}

// OpenPreferred is the package-level form, so the worker can use it without
// holding the HTTP service.
func OpenPreferred(ctx context.Context, pool *pgxpool.Pool, keyring *Keyring, orgID string) (provider, model, key string, err error) {
	if keyring == nil {
		return "", "", "", ErrNoKeyring
	}
	var keyID string
	var nonce, ciphertext []byte
	e := pool.QueryRow(ctx, `SELECT provider,model,key_id,nonce,ciphertext FROM gfm.org_credentials
 WHERE org_id=$1::uuid AND preferred`, orgID).Scan(&provider, &model, &keyID, &nonce, &ciphertext)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", "", "", ErrNoCredential
	}
	if e != nil {
		return "", "", "", e
	}
	key, e = keyring.Open(orgID, provider, keyID, nonce, ciphertext)
	if e != nil {
		return "", "", "", e
	}
	return provider, model, key, nil
}

func (s *Service) handleList(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleAny)
	if e != nil {
		return e
	}
	rows, e := s.pool.Query(c.Ctx(), `SELECT provider,name,last4,model,preferred,created_at,created_by::text
 FROM gfm.org_credentials WHERE org_id=$1::uuid ORDER BY provider`, org.ID)
	if e != nil {
		return mgmt.Internal(e)
	}
	defer rows.Close()
	items := []Credential{}
	for rows.Next() {
		var item Credential
		if e := rows.Scan(&item.Provider, &item.Name, &item.Last4, &item.Model, &item.Preferred,
			&item.CreatedAt, &item.CreatedBy); e != nil {
			return mgmt.Internal(e)
		}
		items = append(items, item)
	}
	if e := rows.Err(); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{"schema_version": mgmt.SchemaVersion, "items": items})
}

type setCredential struct {
	APIKey    string `json:"api_key"`
	Name      string `json:"name"`
	Model     string `json:"model"`
	Preferred bool   `json:"preferred"`
}

func (s *Service) handlePut(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	provider := strings.TrimSpace(c.Param("provider"))
	if !knownProvider(provider) {
		return mgmt.Invalid("invalid_provider", "That model provider is not supported.")
	}
	if s.keyring == nil {
		return mgmt.Fail(http.StatusServiceUnavailable, "secret_encryption_unavailable",
			"This deployment has no secret master key, so a credential cannot be stored.")
	}
	var body setCredential
	if e := c.Decode(&body); e != nil {
		return e
	}
	key := strings.TrimSpace(body.APIKey)
	if len(key) < 8 {
		return mgmt.Invalid("invalid_body", "An API key is required.")
	}
	name := strings.TrimSpace(body.Name)
	if len(name) > 120 {
		return mgmt.Invalid("invalid_body", "The name may not exceed 120 characters.")
	}
	// Shape only, never a closed list (§4.8): the model catalog belongs to the
	// provider and changes weekly. An empty model means the provider's default
	// and is stored as ''. Checked before the verifier's network round trip and
	// before sealing, so a bad model costs nothing and stores nothing.
	model := strings.TrimSpace(body.Model)
	if model != "" && !modelShape.MatchString(model) {
		return mgmt.Invalid("invalid_model", "A model identifier has no spaces and is at most 120 characters.")
	}
	// Verify before sealing. Accepting a key the provider will refuse moves the
	// failure into a background job the owner is not watching (ADR-0045 §5).
	if s.verifier != nil {
		switch e := s.verifier.Verify(c.Ctx(), provider, key); {
		case errors.Is(e, ErrRejected):
			return mgmt.Invalid("credential_invalid", "The provider rejected this key.")
		case e != nil:
			return mgmt.Fail(http.StatusBadGateway, "provider_unavailable",
				"The model provider could not be reached to check this key.")
		}
	}
	keyID, nonce, ciphertext, e := s.keyring.Seal(org.ID, provider, key)
	if e != nil {
		return mgmt.Internal(e)
	}
	tx, e := c.Tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	last4 := Last4(key)
	// Exactly one credential per organisation is preferred, whenever it has at
	// least one (§4.8, §5.5a). storing the first row for an organisation makes
	// it preferred implicitly; asking for preferred:true clears every other row
	// of this organisation first, inside this same transaction, so the unique
	// partial index (org_id) WHERE preferred never sees two true rows at once.
	if body.Preferred {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.org_credentials SET preferred=false
 WHERE org_id=$1::uuid AND provider<>$2 AND preferred`, org.ID, provider); e != nil {
			return mgmt.Internal(e)
		}
	}
	if _, e := tx.Exec(c.Ctx(), `INSERT INTO gfm.org_credentials
 (org_id,provider,credential_id,key_id,nonce,ciphertext,last4,name,model,preferred,created_by)
 VALUES($1::uuid,$2,gen_random_uuid(),$3,$4,$5,$6,$7,$8,
   $9::bool OR NOT EXISTS(SELECT 1 FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider<>$2 AND preferred),
   $10::uuid)
 ON CONFLICT (org_id,provider) DO UPDATE SET credential_id=excluded.credential_id,
 key_id=excluded.key_id,nonce=excluded.nonce,ciphertext=excluded.ciphertext,
 last4=excluded.last4,name=excluded.name,model=excluded.model,
 preferred=excluded.preferred,created_by=excluded.created_by,created_at=now()`,
		org.ID, provider, keyID, nonce, ciphertext, last4, name, model, body.Preferred,
		c.Principal.UserID); e != nil {
		return mgmt.Internal(e)
	}
	// The audit row carries last4 and nothing more, here and everywhere else.
	if e := c.Audit(c.Ctx(), tx, org.ID, "credential.set", "credential:"+provider, last4); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	var out Credential
	if e := s.pool.QueryRow(c.Ctx(), `SELECT provider,name,last4,model,preferred,created_at,created_by::text
 FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider=$2`, org.ID, provider).
		Scan(&out.Provider, &out.Name, &out.Last4, &out.Model, &out.Preferred, &out.CreatedAt, &out.CreatedBy); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, out)
}

// patchCredential's fields are pointers so the handler can tell "not sent"
// from "sent as the zero value": an omitted model must not clobber a stored
// one, and preferred:false is a real instruction, not the absence of one.
type patchCredential struct {
	Model     *string `json:"model"`
	Preferred *bool   `json:"preferred"`
}

// handlePatch changes the model, or moves the preferred mark, without the key
// (§4.8). It exists because a form that asks for a secret to flip a checkbox
// teaches people to paste keys into forms — the key cannot be shown back, so
// re-entering it to "confirm" a change proves nothing anyway. api_key is
// deliberately not in patchCredential: replacing a key stays PUT, which
// verifies it against the provider first.
func (s *Service) handlePatch(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	provider := strings.TrimSpace(c.Param("provider"))
	if !knownProvider(provider) {
		return mgmt.Invalid("invalid_provider", "That model provider is not supported.")
	}
	var body patchCredential
	if e := c.Decode(&body); e != nil {
		return e
	}
	if body.Model == nil && body.Preferred == nil {
		return mgmt.Invalid("invalid_body", "At least one of model or preferred is required.")
	}
	haveModel := body.Model != nil
	var model string
	if haveModel {
		model = strings.TrimSpace(*body.Model)
		// Shape only, same check as PUT (§4.8). An explicit empty string is
		// valid here too: it means the provider's default.
		if model != "" && !modelShape.MatchString(model) {
			return mgmt.Invalid("invalid_model", "A model identifier has no spaces and is at most 120 characters.")
		}
	}
	tx, e := c.Tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	// Lock the row for the rest of this transaction: the preferred check right
	// below has to see a value that cannot change out from under it before the
	// UPDATE that acts on it runs.
	var currentlyPreferred bool
	var last4 string
	e = tx.QueryRow(c.Ctx(), `SELECT preferred,last4 FROM gfm.org_credentials
 WHERE org_id=$1::uuid AND provider=$2 FOR UPDATE`, org.ID, provider).Scan(&currentlyPreferred, &last4)
	if errors.Is(e, pgx.ErrNoRows) {
		return mgmt.NotFound("credential_not_found", "This organisation has no key for that provider.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	havePreferred := body.Preferred != nil
	var wantPreferred bool
	if havePreferred {
		wantPreferred = *body.Preferred
	}
	// The only way to legitimately reach zero preferred rows is deleting the
	// last credential (handleDelete promotes when one remains). preferred:false
	// on the row that is currently the organisation's only preferred one would
	// get there another way, so it is refused instead — the invariant this
	// whole module keeps is why a run with no fields is ever possible.
	if havePreferred && !wantPreferred && currentlyPreferred {
		return mgmt.Invalid("invalid_body",
			"This is the organisation's only preferred credential; clearing it would leave none preferred.")
	}
	if havePreferred && wantPreferred {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.org_credentials SET preferred=false
 WHERE org_id=$1::uuid AND provider<>$2 AND preferred`, org.ID, provider); e != nil {
			return mgmt.Internal(e)
		}
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.org_credentials SET
 model = CASE WHEN $3 THEN $4 ELSE model END,
 preferred = CASE WHEN $5 THEN $6 ELSE preferred END
 WHERE org_id=$1::uuid AND provider=$2`,
		org.ID, provider, haveModel, model, havePreferred, wantPreferred); e != nil {
		return mgmt.Internal(e)
	}
	// Same audit shape as PUT: last4 and nothing more. Changing the model or
	// the preferred mark is still a change to the row an owner controls.
	if e := c.Audit(c.Ctx(), tx, org.ID, "credential.set", "credential:"+provider, last4); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	var out Credential
	if e := s.pool.QueryRow(c.Ctx(), `SELECT provider,name,last4,model,preferred,created_at,created_by::text
 FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider=$2`, org.ID, provider).
		Scan(&out.Provider, &out.Name, &out.Last4, &out.Model, &out.Preferred, &out.CreatedAt, &out.CreatedBy); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, out)
}

func (s *Service) handleDelete(c *mgmt.Context) error {
	org, e := c.Authorize("org", mgmt.RoleOwner)
	if e != nil {
		return e
	}
	provider := strings.TrimSpace(c.Param("provider"))
	if !knownProvider(provider) {
		return mgmt.NotFound("credential_not_found", "This organisation has no key for that provider.")
	}
	tx, e := c.Tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	var last4 string
	var wasPreferred bool
	e = tx.QueryRow(c.Ctx(), `DELETE FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider=$2
 RETURNING last4,preferred`, org.ID, provider).Scan(&last4, &wasPreferred)
	if errors.Is(e, pgx.ErrNoRows) {
		return mgmt.NotFound("credential_not_found", "This organisation has no key for that provider.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	// Deleting the preferred credential promotes another one deterministically
	// (oldest created_at, then provider) if any remain, so an organisation with
	// credentials never ends up with none of them preferred (§4.8). Deleting a
	// non-preferred row leaves the mark exactly where it was. If nothing remains,
	// the subquery returns no provider and this UPDATE touches no row.
	if wasPreferred {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.org_credentials SET preferred=true
 WHERE org_id=$1::uuid AND provider=(SELECT provider FROM gfm.org_credentials
   WHERE org_id=$1::uuid ORDER BY created_at ASC, provider ASC LIMIT 1)`, org.ID); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := c.Audit(c.Ctx(), tx, org.ID, "credential.delete", "credential:"+provider, last4); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.NoContent()
}
