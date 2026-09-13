package schema

// Catalog (gf) and management (gfm) DDL. The catalog statements are the ones
// that used to live next to the code that queries them; they are unchanged
// except that everything depending on the pgvector `vector` type moved into
// vectorSQL so a plain PostgreSQL server can run the same migration.

const extensionsSQL = `
DO $$ BEGIN
 CREATE EXTENSION IF NOT EXISTS pg_search;
EXCEPTION WHEN OTHERS THEN
 RAISE NOTICE 'pg_search unavailable, router engine only: %', SQLERRM;
END $$;
DO $$ BEGIN
 CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
 RAISE NOTICE 'vector unavailable, dense retrieval disabled: %', SQLERRM;
END $$;
`

const catalogSQL = `
CREATE SCHEMA IF NOT EXISTS gf;
CREATE TABLE IF NOT EXISTS gf.schema_version (version integer PRIMARY KEY);
INSERT INTO gf.schema_version VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.snapshots (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 revision text NOT NULL, cli_sha text NOT NULL, nodes jsonb NOT NULL, weights jsonb NOT NULL,
 published_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.skills (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 urn text NOT NULL, skill_revision text NOT NULL, node text NOT NULL,
 status text NOT NULL, metadata json NOT NULL, body bytea NOT NULL, search_text text NOT NULL,
 UNIQUE(tenant,repo,snapshot_id,urn),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
-- v2 preserves arbitrary UTF-8 skill bodies (including NUL) as bytes. JSON, unlike
-- JSONB, also retains escaped NUL in metadata. The search projection maps NUL to space.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='gf.skills'::regclass AND attname='body' AND atttypid='text'::regtype) THEN
  ALTER TABLE gf.skills ALTER COLUMN body TYPE bytea USING convert_to(body,'UTF8');
 END IF;
 IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='gf.skills'::regclass AND attname='metadata' AND atttypid='jsonb'::regtype) THEN
  ALTER TABLE gf.skills ALTER COLUMN metadata TYPE json USING metadata::json;
 END IF;
END $$;
INSERT INTO gf.schema_version VALUES (2) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.heads (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 PRIMARY KEY(tenant,repo),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
-- v4: BM25 document frequencies belong to one immutable tenant/repo/snapshot.
-- A global index makes another catalog or old snapshot change this one's scores.
DROP INDEX IF EXISTS gf.skills_search;
INSERT INTO gf.schema_version VALUES (4) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.router_indexes (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 index_sha text NOT NULL, n_docs integer NOT NULL, n_terms integer NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.router_terms (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 term text NOT NULL, postings bytea NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id,term),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.router_indexes(tenant,repo,snapshot_id)
);
INSERT INTO gf.schema_version VALUES (5) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.events (
 tenant_id text NOT NULL, event_id bytea NOT NULL,
 event_type text NOT NULL, schema_version text NOT NULL,
 occurred_at text NOT NULL, received_at text NOT NULL,
 search_id text, load_id text, payload bytea NOT NULL,
 PRIMARY KEY(tenant_id,event_id)
);
CREATE INDEX IF NOT EXISTS events_tenant_type ON gf.events(tenant_id,event_type);
CREATE INDEX IF NOT EXISTS events_occurred ON gf.events(occurred_at);
CREATE INDEX IF NOT EXISTS events_search ON gf.events(tenant_id,search_id);
CREATE INDEX IF NOT EXISTS events_load ON gf.events(tenant_id,load_id);
INSERT INTO gf.schema_version VALUES (7) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.search_shadow (
 tenant_id text NOT NULL, search_id text NOT NULL, repo text NOT NULL,
 snapshot_id text NOT NULL, encoder_id text NOT NULL, status text NOT NULL,
 sparse_ranked bytea NOT NULL, hybrid_ranked bytea NOT NULL,
 selected bytea NOT NULL, hybrid_selected bytea NOT NULL,
 timings jsonb NOT NULL, error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,search_id)
);
CREATE INDEX IF NOT EXISTS search_shadow_created ON gf.search_shadow(created_at);
INSERT INTO gf.schema_version VALUES (8) ON CONFLICT DO NOTHING;
`

// Everything that needs pgvector. Skipped on the plain PostgreSQL profile; the
// router engine never reads these relations.
const vectorSQL = `
ALTER TABLE gf.skills ADD COLUMN IF NOT EXISTS embedding vector(1024);
CREATE TABLE IF NOT EXISTS gf.embedding_sets (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 encoder_id text NOT NULL, manifest jsonb NOT NULL, bundle_sha text NOT NULL,
 n_vectors integer NOT NULL CHECK(n_vectors>0),
 PRIMARY KEY(tenant,repo,snapshot_id,encoder_id),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.embeddings (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 encoder_id text NOT NULL, urn text NOT NULL, skill_revision text NOT NULL,
 embedding vector(1024) NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id,encoder_id,urn),
 FOREIGN KEY(tenant,repo,snapshot_id,encoder_id) REFERENCES gf.embedding_sets(tenant,repo,snapshot_id,encoder_id),
 FOREIGN KEY(tenant,repo,snapshot_id,urn) REFERENCES gf.skills(tenant,repo,snapshot_id,urn)
);
INSERT INTO gf.schema_version VALUES (6) ON CONFLICT DO NOTHING;
`

// Management schema. Every row carries org_id and every composite key starts
// with it, so a query that forgets the tenant predicate cannot join across
// organisations by construction.
const managementSQL = `
CREATE SCHEMA IF NOT EXISTS gfm;
CREATE TABLE IF NOT EXISTS gfm.users (
 user_id uuid PRIMARY KEY,
 email text NOT NULL,
 name text NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS users_email ON gfm.users(lower(email));
CREATE TABLE IF NOT EXISTS gfm.identities (
 provider text NOT NULL,
 subject text NOT NULL,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(provider,subject)
);
CREATE INDEX IF NOT EXISTS identities_user ON gfm.identities(user_id);
CREATE TABLE IF NOT EXISTS gfm.orgs (
 org_id uuid PRIMARY KEY,
 slug text NOT NULL UNIQUE,
 name text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS gfm.memberships (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 role text NOT NULL CHECK(role IN ('owner','member')),
 joined_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,user_id)
);
CREATE INDEX IF NOT EXISTS memberships_user ON gfm.memberships(user_id);
CREATE TABLE IF NOT EXISTS gfm.teams (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 team_id uuid NOT NULL,
 name text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,team_id),
 UNIQUE(team_id),
 UNIQUE(org_id,name)
);
CREATE INDEX IF NOT EXISTS teams_org ON gfm.teams(org_id);
CREATE TABLE IF NOT EXISTS gfm.team_members (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 team_id uuid NOT NULL,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 PRIMARY KEY(org_id,team_id,user_id),
 FOREIGN KEY(org_id,team_id) REFERENCES gfm.teams(org_id,team_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS team_members_user ON gfm.team_members(user_id);
-- gfm.github_installations mirrors one GitHub App installation and is keyed
-- by installation_id alone: GitHub assigns that id globally, and the row must
-- be able to exist before any organisation has linked it — an "installation"
-- webhook event can arrive before the OAuth-during-install callback finishes
-- (ADR-0034). Which organisation an installation belongs to is decided only
-- by gfm.github_installation_links below, never guessed from account/org login.
CREATE TABLE IF NOT EXISTS gfm.github_installations (
 installation_id bigint PRIMARY KEY,
 account text NOT NULL,
 repositories jsonb NOT NULL DEFAULT '[]',
 suspended_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
-- Upgrades the earlier org-keyed shape, where org_id was part of the primary
-- key and was written by the webhook itself from a login-equals-slug guess —
-- a match that only ever worked when a Guidefold organisation's slug happened
-- to equal the GitHub account's login, never for an App installed by an
-- unrelated account (the point of a public App). One installation belongs to
-- at most one Guidefold organisation, decided by the explicit link, so org_id
-- has no home on this table any more.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='gfm' AND table_name='github_installations' AND column_name='org_id') THEN
  DROP INDEX IF EXISTS gfm.github_installations_org;
  ALTER TABLE gfm.github_installations DROP CONSTRAINT IF EXISTS github_installations_pkey;
  ALTER TABLE gfm.github_installations DROP CONSTRAINT IF EXISTS github_installations_installation_id_key;
  ALTER TABLE gfm.github_installations DROP COLUMN org_id;
  ALTER TABLE gfm.github_installations ADD PRIMARY KEY (installation_id);
 END IF;
END $$;
-- The explicit link ADR-0034 always meant to require: proven by GitHub's own
-- OAuth-during-install user-authorization flow (the API-CONTRACT §4.7 start
-- and callback routes), never asserted from a query string. installation_id
-- references the mirror above so a link cannot outlive its installation row.
CREATE TABLE IF NOT EXISTS gfm.github_installation_links (
 installation_id bigint PRIMARY KEY REFERENCES gfm.github_installations(installation_id) ON DELETE CASCADE,
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 linked_by uuid REFERENCES gfm.users(user_id),
 linked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS github_installation_links_org ON gfm.github_installation_links(org_id);
CREATE TABLE IF NOT EXISTS gfm.github_deliveries (
 delivery_id text PRIMARY KEY,
 payload_sha256 text NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS github_deliveries_received ON gfm.github_deliveries(received_at);
-- The first reversible secret in the product (ADR-0045). Every other credential
-- here is a sha256 the server can check but never reproduce; this one has to be
-- usable by a background job with nobody present, so it is sealed rather than
-- hashed. The organisation is authenticated into the ciphertext, so a row moved
-- between organisations fails to open instead of decrypting into someone else's
-- run, and key_id lets a retired master key stay readable until its rows are
-- re-sealed.
CREATE TABLE IF NOT EXISTS gfm.org_credentials (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 provider text NOT NULL CHECK(provider IN ('openrouter','anthropic','openai')),
 credential_id uuid NOT NULL UNIQUE,
 key_id text NOT NULL,
 nonce bytea NOT NULL,
 ciphertext bytea NOT NULL,
 last4 text NOT NULL,
 name text NOT NULL DEFAULT '',
 model text NOT NULL DEFAULT '',
 preferred boolean NOT NULL DEFAULT false,
 created_by uuid REFERENCES gfm.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,provider)
);
-- Which provider and model background work uses is an organisation setting, not a
-- field on every run: the owner presses one button and the answer to "with what"
-- was decided once, here.
ALTER TABLE gfm.org_credentials ADD COLUMN IF NOT EXISTS model text NOT NULL DEFAULT '';
ALTER TABLE gfm.org_credentials ADD COLUMN IF NOT EXISTS preferred boolean NOT NULL DEFAULT false;
CREATE UNIQUE INDEX IF NOT EXISTS org_credentials_preferred ON gfm.org_credentials(org_id)
 WHERE preferred;
CREATE TABLE IF NOT EXISTS gfm.live_runs (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 run_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'queued'
   CHECK(state IN ('queued','running','succeeded','partial','failed','cancelled')),
-- prompt is unused: a run takes no instruction (ADR-0046 §8, amended). The column
-- stays because dropping a NOT NULL column under a deployment that syncs itself is
-- the one irreversible step in that change; it goes once nothing reads it.
 prompt text NOT NULL DEFAULT '',
 provider text NOT NULL CHECK(provider IN ('openrouter','anthropic','openai')),
 model text NOT NULL,
 limits jsonb NOT NULL DEFAULT '{}',
 cost jsonb NOT NULL DEFAULT '{}',
 summary jsonb NOT NULL DEFAULT '{}',
 error text,
 created_by uuid REFERENCES gfm.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz,
 finished_at timestamptz,
 PRIMARY KEY(org_id,run_id)
);
-- One active run per organisation (ADR-0046 §6), enforced here rather than by a
-- check in the handler: two concurrent sweeps of the same repositories would
-- double the spend for the same answer.
CREATE UNIQUE INDEX IF NOT EXISTS live_runs_one_active ON gfm.live_runs(org_id)
 WHERE state IN ('queued','running');
CREATE INDEX IF NOT EXISTS live_runs_recent ON gfm.live_runs(org_id,created_at DESC);
ALTER TABLE gfm.live_runs ADD COLUMN IF NOT EXISTS summary jsonb NOT NULL DEFAULT '{}';
ALTER TABLE gfm.live_runs ALTER COLUMN prompt SET DEFAULT '';
CREATE TABLE IF NOT EXISTS gfm.live_run_targets (
 org_id uuid NOT NULL,
 run_id uuid NOT NULL,
 repo_id text NOT NULL,
 state text NOT NULL DEFAULT 'queued'
   CHECK(state IN ('queued','running','done','failed','skipped')),
 job_id uuid,
 phase text NOT NULL DEFAULT 'fetch' CHECK(phase IN ('fetch','parse','propose','done')),
 skills integer NOT NULL DEFAULT 0,
 proposals integer NOT NULL DEFAULT 0,
 findings integer NOT NULL DEFAULT 0, -- unused; see the note on gfm.live_runs.prompt

 error text,
 started_at timestamptz,
 finished_at timestamptz,
 PRIMARY KEY(org_id,run_id,repo_id),
 FOREIGN KEY(org_id,run_id) REFERENCES gfm.live_runs(org_id,run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS live_run_targets_state ON gfm.live_run_targets(org_id,run_id,state);
ALTER TABLE gfm.live_run_targets ADD COLUMN IF NOT EXISTS phase text NOT NULL DEFAULT 'fetch';
ALTER TABLE gfm.live_run_targets ADD COLUMN IF NOT EXISTS skills integer NOT NULL DEFAULT 0;
ALTER TABLE gfm.live_run_targets ADD COLUMN IF NOT EXISTS proposals integer NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS gfm.live_run_events (
 org_id uuid NOT NULL,
 run_id uuid NOT NULL,
 seq bigint NOT NULL,
 at timestamptz NOT NULL DEFAULT now(),
 repo_id text,
 type text NOT NULL CHECK(type IN ('run.started','repo.started','repo.fetched','repo.parsed','repo.proposed','repo.finished','run.finished','error')),
 payload jsonb NOT NULL DEFAULT '{}',
 PRIMARY KEY(org_id,run_id,seq),
 FOREIGN KEY(org_id,run_id) REFERENCES gfm.live_runs(org_id,run_id) ON DELETE CASCADE
);
-- The event domain changed with ADR-0046's amendment: progress through the import
-- and proposal pipeline replaced a raw model transcript. A CHECK cannot be widened
-- in place, so it is dropped and rewritten.
ALTER TABLE gfm.live_run_events DROP CONSTRAINT IF EXISTS live_run_events_type_check;
ALTER TABLE gfm.live_run_events ADD CONSTRAINT live_run_events_type_check
 CHECK(type IN ('run.started','repo.started','repo.fetched','repo.parsed','repo.proposed','repo.finished','run.finished','error'));
CREATE TABLE IF NOT EXISTS gfm.repos (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 repo_id text NOT NULL,
 name text NOT NULL DEFAULT '',
 git_host_url text NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,repo_id)
);
-- github_installation_id marks a repository as reconciled from a linked
-- GitHub App installation (API-CONTRACT §4.7/§8) rather than registered by
-- hand or the CLI. NULL means "not installation-managed", which is also
-- what a repository reverts to when GitHub reports it removed from the
-- installation (detached, never deleted — gfm.imports, gfm.skills,
-- gfm.proposals and gfm.publications all cascade off gfm.repos, so deleting
-- the row would destroy an organisation's catalogue and review history over
-- a repository visibility change on GitHub's side).
ALTER TABLE gfm.repos ADD COLUMN IF NOT EXISTS github_installation_id bigint;
CREATE INDEX IF NOT EXISTS repos_github_installation ON gfm.repos(org_id,github_installation_id) WHERE github_installation_id IS NOT NULL;
-- Optional repository policy. An empty ACL keeps the existing organization
-- membership behavior; once an owner adds one entry, non-owners need an
-- explicit row for every management and delivery operation.
CREATE TABLE IF NOT EXISTS gfm.repo_members (
 org_id uuid NOT NULL,
 repo_id text NOT NULL,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 access text NOT NULL CHECK(access IN ('read','write')),
 created_by uuid REFERENCES gfm.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,repo_id,user_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS repo_members_user ON gfm.repo_members(user_id);
CREATE TABLE IF NOT EXISTS gfm.repo_acl_policies (
 org_id uuid NOT NULL,
 repo_id text NOT NULL,
 enabled boolean NOT NULL DEFAULT true,
 created_by uuid REFERENCES gfm.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,repo_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS gfm.repo_reviewers (
 org_id uuid NOT NULL,
 repo_id text NOT NULL,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 assigned_by uuid REFERENCES gfm.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,repo_id,user_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS repo_reviewers_user ON gfm.repo_reviewers(user_id);
CREATE TABLE IF NOT EXISTS gfm.invitations (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 invitation_id uuid NOT NULL,
 token_sha256 text NOT NULL UNIQUE,
 email text NOT NULL,
 role text NOT NULL CHECK(role IN ('owner','member')),
 created_by uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 accepted_by uuid,
 accepted_at timestamptz,
 revoked_at timestamptz,
 PRIMARY KEY(org_id,invitation_id)
);
CREATE TABLE IF NOT EXISTS gfm.sessions (
 id_sha256 text PRIMARY KEY,
 user_id uuid NOT NULL REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 csrf_token text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 last_seen_at timestamptz
);
CREATE INDEX IF NOT EXISTS sessions_user ON gfm.sessions(user_id);
CREATE TABLE IF NOT EXISTS gfm.tokens (
 token_id uuid PRIMARY KEY,
 token_sha256 text NOT NULL UNIQUE,
 kind text NOT NULL CHECK(kind IN ('personal','installation','ci')),
 user_id uuid REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 org_id uuid REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 repo_id text,
 scopes text[] NOT NULL DEFAULT '{}',
 name text NOT NULL DEFAULT '',
 harness text,
 adapter_version text,
 capabilities jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz,
 revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS tokens_org ON gfm.tokens(org_id);
CREATE TABLE IF NOT EXISTS gfm.device_codes (
 device_code_sha256 text PRIMARY KEY,
 user_code text NOT NULL UNIQUE,
 state text NOT NULL CHECK(state IN ('pending','approved','denied','expired')),
 user_id uuid REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 last_poll_at timestamptz
);
-- OAuth/link handoff state. Not a session: it only survives one round trip and
-- carries the current user id when the flow links an identity to that user.
CREATE TABLE IF NOT EXISTS gfm.auth_states (
 state_sha256 text PRIMARY KEY,
 kind text NOT NULL CHECK(kind IN ('login','link')),
 provider text NOT NULL,
 user_id uuid REFERENCES gfm.users(user_id) ON DELETE CASCADE,
 return_to text NOT NULL DEFAULT '/',
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL
);
-- 'github_install' (API-CONTRACT §4.7) reuses this same one-round-trip,
-- single-use table rather than a second state mechanism: org_id ties the
-- round trip to the organisation that started it, the way user_id already
-- ties a 'link' round trip to a person. NULL for 'login'/'link'.
ALTER TABLE gfm.auth_states ADD COLUMN IF NOT EXISTS org_id uuid REFERENCES gfm.orgs(org_id) ON DELETE CASCADE;
ALTER TABLE gfm.auth_states DROP CONSTRAINT IF EXISTS auth_states_kind_check;
ALTER TABLE gfm.auth_states ADD CONSTRAINT auth_states_kind_check CHECK(kind IN ('login','link','github_install'));
CREATE TABLE IF NOT EXISTS gfm.audit (
 org_id uuid NOT NULL,
 audit_id bigint GENERATED ALWAYS AS IDENTITY,
 at timestamptz NOT NULL DEFAULT now(),
 actor text NOT NULL,
 action text NOT NULL,
 entity text NOT NULL,
 revision text,
 request_id text NOT NULL DEFAULT '',
 PRIMARY KEY(org_id,audit_id)
);
CREATE INDEX IF NOT EXISTS audit_org_at ON gfm.audit(org_id,at DESC,audit_id DESC);
CREATE TABLE IF NOT EXISTS gfm.idempotency (
 org_id uuid NOT NULL,
 principal_id text NOT NULL,
 key text NOT NULL,
 payload_sha256 text NOT NULL,
 status integer NOT NULL DEFAULT 0,
 body bytea NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,principal_id,key)
);
CREATE TABLE IF NOT EXISTS gfm.jobs (
 org_id uuid NOT NULL,
 job_id uuid NOT NULL,
 repo_id text,
 import_id uuid,
 kind text NOT NULL,
 state text NOT NULL DEFAULT 'queued'
  CHECK(state IN ('queued','leased','done','failed','skipped','cancelled')),
 payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 input_digest text,
 recipe_version text,
 idempotency_key text,
 attempts integer NOT NULL DEFAULT 0,
 max_attempts integer NOT NULL DEFAULT 3,
 lease_until timestamptz,
 worker_id text,
 generation integer NOT NULL DEFAULT 0,
 checkpoint jsonb,
 limits jsonb,
 cost jsonb,
 result jsonb,
 error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz,
 finished_at timestamptz,
 PRIMARY KEY(org_id,job_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_job_id ON gfm.jobs(job_id);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency ON gfm.jobs(org_id,idempotency_key)
 WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS jobs_runnable ON gfm.jobs(kind,state,created_at);
INSERT INTO gf.schema_version VALUES (9) ON CONFLICT DO NOTHING;
`

// Privileges. gf.* stays read-only for the API (plus the two append-only
// ledgers); gfm.* is the API's own read/write surface. The role keeps
// default_transaction_read_only, so every management write opens an explicit
// read-write transaction — the same rule the telemetry ingest already follows.
const grantsSQL = `
GRANT USAGE ON SCHEMA gf TO guidefold_api;
GRANT SELECT ON ALL TABLES IN SCHEMA gf TO guidefold_api;
GRANT INSERT ON gf.events,gf.search_shadow,gf.training_examples TO guidefold_api;
GRANT USAGE ON SCHEMA gfm TO guidefold_api;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA gfm TO guidefold_api;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA gfm TO guidefold_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA gfm GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO guidefold_api;
ALTER ROLE guidefold_api SET default_transaction_read_only=on;
DO $$ BEGIN
 EXECUTE format('GRANT CONNECT ON DATABASE %I TO guidefold_api', current_database());
END $$;
`
