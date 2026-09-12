# ADR-0045: Organisation-supplied model credentials, encrypted at rest

**Status:** Proposed · 2026-09-12 · numbered 0045 after 0043 and 0044 were taken the same day by the ADR reconciliation and the shadcn console · owner instruction the same day: the live agent runs "z kluczami
podanymi przez organizację", and, asked where the key should live, the owner chose encrypted
storage over a key that is never persisted.
**Governs:** `gfm.org_credentials`, `{org_base}/credentials/*`, the secret-box port used by the API
and the worker, and every future feature that needs a provider credential belonging to a customer
rather than to the deployment.
**Depends on:** [ADR-0038](ADR-0038-subscription-byok-and-metered-ai.md) §2 (BYOK is the default
commercial route), [ADR-0033](ADR-0033-api-contract-first-and-mvp-storage.md) (contract before code).
**Used by:** [ADR-0046](ADR-0046-live-agent-on-demand-across-connected-repositories.md).

## Context

Verified in this repository on 2026-09-12: `gfm` stores no recoverable secret. Sessions, personal
tokens, CI tokens and invitations are kept as `token_sha256` only, which is a one-way hash — the
service can check a secret it is shown but can never produce one. The model key the Go generator
uses today comes from a file path in the deployment (`*_FILE`), so it belongs to whoever runs the
service, not to a customer organisation.

The live agent needs a third thing: a credential that one organisation supplies once, that the
worker can *use* later without a human present. A hash cannot do that, and a deployment-wide file
cannot be per-organisation. So this is the first reversible secret in the product, and the first
place where a database dump would be worth stealing.

Rozbieżność: ADR-0038 §2 makes BYOK the route where "the customer pays their model provider
directly"; it does not say where the key is kept, because the CI route kept it in the customer's
own secret store and Guidefold never held it.
Decyzja w tej pracy: Guidefold holds it, encrypted, per organisation.
Dokument zastępowany: none. §2's commercial conclusion is unchanged — Guidefold still adds no AI
charge on this route.
Konsekwencje: a new key-management responsibility, a new operational failure mode (lost master
key), and a new class of audit event.
Do decyzji właściciela: none for this scope.

## Decision

1. **One table, ciphertext only, one row per provider.** `gfm.org_credentials` holds `org_id`,
   `provider`, `credential_id`, `key_id`, `nonce`, `ciphertext`, `last4`, `name`, `created_by`
   and `created_at`. The primary key is `(org_id, provider)`: one live credential per provider
   per organisation, replaced in place, several providers side by side. No column ever holds the
   plaintext, and no index is built over anything derived from it.

   The domain is `openrouter`, `anthropic` and `openai` (owner instruction, 2026-09-12: keys are
   per provider and the product supports several models). OpenRouter reaches many models through
   one account; the two direct routes exist because an organisation that already has an account
   with Anthropic or OpenAI should not have to open a third one to use its own models. Adding a
   provider means changing the table's CHECK, the Go list and the OpenAPI enum together — a
   provider accepted by the API but rejected by the column would be a 500 in place of a 400.

2. **AES-256-GCM with a deployment master key, and the organisation bound into the ciphertext.**
   The key material comes from `GUIDEFOLD_SECRET_KEY_FILE`, a JSON object of `key_id → 32 random
   bytes, base64`, with one id marked active. Sealing uses the active key, a fresh 12-byte nonce,
   and `org_id || provider || key_id` as additional authenticated data. A ciphertext copied into
   another organisation's row therefore fails to open rather than decrypting into someone else's
   run. `key_id` is stored per row, so rotation means adding a new active key and re-sealing rows
   in the background; old keys stay in the file until no row references them.

3. **The plaintext leaves the database in exactly one direction.** The worker opens the box in
   memory, for the duration of one job, and passes it to the provider over TLS. It is never
   written to a log, a job payload, a checkpoint, a job `result`, an error message or an export.
   The API never returns it: `GET` answers with `provider`, `name`, `last4`, `created_at`,
   `created_by` and nothing else.

4. **Owners only, CSRF, audited.** `PUT {org_base}/credentials/{provider}` and
   `DELETE {org_base}/credentials/{provider}` require the owner role and the CSRF header, like
   every other mutating management call. Setting, replacing, deleting and *using* a credential
   each write a `gfm.audit` row (`credential.set`, `credential.delete`, `credential.used` with the
   run id). The audit row carries `last4`, never more.

5. **Validation happens against the provider, not against a regex.** On `PUT`, the API makes one
   cheap authenticated call to the provider (for OpenRouter, `GET /api/v1/key`) and refuses a
   credential the provider rejects, with `credential_invalid`. Accepting a key that cannot work
   would move the failure to a background job the owner is not watching.

6. **No master key, no feature.** When `GUIDEFOLD_SECRET_KEY_FILE` is absent or unreadable, `PUT`
   answers `503 secret_encryption_unavailable` and every job that needs a credential terminates
   `skipped` with the same code. Storing a key in the clear "for now" is not an option this ADR
   leaves open.

7. **BYOK, so no metering.** The customer's provider bills the customer. Guidefold adds no AI
   charge and therefore does not need the budget reservation, concurrency-safe spend limit and
   reconciliation that ADR-0038 §5 requires before *paid managed* execution. §5 is not waived; it
   does not apply to this route. What does apply is a per-run cost ceiling, so a runaway loop
   cannot spend the customer's money without bound — that ceiling lives in ADR-0046.

## Consequences

- Losing every master key makes every stored credential unrecoverable. That is the intended
  failure mode: owners re-enter their key. It must be stated in the deployment docs, and the key
  file must be backed up separately from the database, or the two are compromised together.
- A database dump alone no longer yields working provider keys, but a dump plus the key file does.
  Ship them on different trust boundaries.
- Rotation needs a background re-seal job before a retired key can be deleted from the file. Until
  that exists, keys accumulate in the file; that is safe but must not be mistaken for rotation
  having happened.
- This ADR is Proposed until the table, the secret-box port, the four endpoints, the provider
  validation call and the audit rows exist, and a test proves that a ciphertext sealed for one
  organisation fails to open for another.

## References

- [API-CONTRACT](../API-CONTRACT.md) §2 (roles and CSRF), §4.1, §5.1, §7 — the contract entries for
  this decision land there in the same change as the code.
- [ADR-0038](ADR-0038-subscription-byok-and-metered-ai.md) §2, §5.
- [OpenRouter key introspection](https://openrouter.ai/docs/api-reference/limits), used for the
  validation call in point 5; verify the endpoint before relying on it.
