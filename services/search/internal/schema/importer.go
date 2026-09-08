package schema

// Import and Knowledge tables (API-CONTRACT §7). They are in their own file
// because they are the first tables written by the *worker* as well as the API:
// the import module enqueues, the parse job fills the catalog, and the drift
// rules append to the owner queue.
//
// Two invariants shape every statement here. Every row carries org_id and every
// composite key starts with it, so a query that forgets the tenant predicate
// cannot join across organisations by construction. And nothing is ever deleted
// on the drift path: a source file that disappears archives its skill and keeps
// every revision, because the decision belongs to the owner.
const importerSQL = `
CREATE TABLE IF NOT EXISTS gfm.blobs (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 sha256 text NOT NULL,
 size_bytes bigint NOT NULL,
 content bytea NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 last_referenced_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,sha256)
);
CREATE INDEX IF NOT EXISTS blobs_referenced ON gfm.blobs(org_id,last_referenced_at);

CREATE TABLE IF NOT EXISTS gfm.imports (
 org_id uuid NOT NULL,
 import_id uuid NOT NULL,
 repo_id text NOT NULL,
 state text NOT NULL DEFAULT 'created'
  CHECK(state IN ('created','uploading','queued','parsing','ready','partial','failed','cancelled')),
 manifest_digest text NOT NULL,
 commit text,
 complete boolean NOT NULL DEFAULT false,
 dirty boolean NOT NULL DEFAULT false,
 cli_version text NOT NULL DEFAULT '',
 scan_profile text NOT NULL DEFAULT 'default',
 manifest jsonb NOT NULL,
 publish boolean NOT NULL DEFAULT true,
 reused_import_id uuid,
 created_by uuid,
 error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 finalized_at timestamptz,
 PRIMARY KEY(org_id,import_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
-- One import per manifest digest, so re-sending the same tree reuses the import
-- instead of re-uploading it. A failed import does not hold the digest hostage.
CREATE UNIQUE INDEX IF NOT EXISTS imports_manifest ON gfm.imports(org_id,repo_id,manifest_digest)
 WHERE state<>'failed';
CREATE INDEX IF NOT EXISTS imports_recent ON gfm.imports(org_id,repo_id,created_at DESC);

CREATE TABLE IF NOT EXISTS gfm.import_files (
 org_id uuid NOT NULL,
 import_id uuid NOT NULL,
 path text NOT NULL,
 sha256 text NOT NULL,
 size_bytes bigint NOT NULL,
 kind text NOT NULL CHECK(kind IN ('skill','document','config','resource')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','omitted','failed')),
 reason text,
 skill_id text,
 mode text NOT NULL DEFAULT '100644',
 PRIMARY KEY(org_id,import_id,path),
 FOREIGN KEY(org_id,import_id) REFERENCES gfm.imports(org_id,import_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS import_files_status ON gfm.import_files(org_id,import_id,status);

CREATE TABLE IF NOT EXISTS gfm.skills (
 org_id uuid NOT NULL,
 skill_id text NOT NULL,
 repo_id text NOT NULL,
 name text NOT NULL,
 description text NOT NULL DEFAULT '',
 scope text NOT NULL,
 owner text,
 path text NOT NULL,
 source_layer text,
 knowledge_layer text NOT NULL DEFAULT 'unclassified',
 source_status text NOT NULL DEFAULT 'active',
 publication_status text NOT NULL DEFAULT 'draft'
  CHECK(publication_status IN ('draft','approved_for_export','awaiting_git','published','needs_review','archived')),
 current_revision_id text,
 published_revision_id text,
 first_import_id uuid,
 last_import_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,skill_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
-- One *live* skill per path. Archived identities keep their path for the
-- record: re-mapping a scope in guidefold.yaml changes a skill's URN while the
-- file stays where it was, and the old identity must stay readable rather than
-- block the new one.
CREATE UNIQUE INDEX IF NOT EXISTS skills_path ON gfm.skills(org_id,repo_id,path)
 WHERE source_status<>'removed';
CREATE INDEX IF NOT EXISTS skills_scope ON gfm.skills(org_id,repo_id,scope);
CREATE INDEX IF NOT EXISTS skills_publication ON gfm.skills(org_id,repo_id,publication_status);
CREATE INDEX IF NOT EXISTS skills_name ON gfm.skills(org_id,repo_id,lower(name));

CREATE TABLE IF NOT EXISTS gfm.skill_revisions (
 org_id uuid NOT NULL,
 revision_id text NOT NULL,
 skill_id text NOT NULL,
 content_sha256 text NOT NULL,
 blob_sha256 text NOT NULL,
 frontmatter jsonb NOT NULL,
 commit text,
 import_id uuid,
 proposal_id uuid,
 origin text NOT NULL DEFAULT 'source' CHECK(origin IN ('source','parsed','inferred','human')),
 source_path text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,revision_id),
 FOREIGN KEY(org_id,skill_id) REFERENCES gfm.skills(org_id,skill_id) ON DELETE CASCADE,
 FOREIGN KEY(org_id,blob_sha256) REFERENCES gfm.blobs(org_id,sha256)
);
CREATE INDEX IF NOT EXISTS skill_revisions_recent ON gfm.skill_revisions(org_id,skill_id,created_at DESC);

CREATE TABLE IF NOT EXISTS gfm.skill_resources (
 org_id uuid NOT NULL,
 revision_id text NOT NULL,
 path text NOT NULL,
 sha256 text NOT NULL,
 size_bytes bigint NOT NULL,
 type text NOT NULL,
 required boolean NOT NULL DEFAULT false,
 available boolean NOT NULL DEFAULT false,
 PRIMARY KEY(org_id,revision_id,path),
 FOREIGN KEY(org_id,revision_id) REFERENCES gfm.skill_revisions(org_id,revision_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gfm.scopes (
 org_id uuid NOT NULL,
 repo_id text NOT NULL,
 scope text NOT NULL,
 owner text,
 parent text,
 paths text[] NOT NULL DEFAULT '{}',
 source text NOT NULL DEFAULT 'guidefold_yaml'
  CHECK(source IN ('guidefold_yaml','directory','codeowners','unknown')),
 import_id uuid,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,repo_id,scope),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS scopes_parent ON gfm.scopes(org_id,repo_id,parent);

CREATE TABLE IF NOT EXISTS gfm.relations (
 org_id uuid NOT NULL,
 relation_id uuid NOT NULL,
 from_skill_id text NOT NULL,
 to_skill_id text NOT NULL,
 type text NOT NULL
  CHECK(type IN ('derived_from','requires','refines','similar','conflicts_with')),
 provenance text NOT NULL DEFAULT 'source',
 revision_id text,
 proposal_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,relation_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS relations_edge
 ON gfm.relations(org_id,from_skill_id,to_skill_id,type,revision_id);
CREATE INDEX IF NOT EXISTS relations_incoming ON gfm.relations(org_id,to_skill_id,type);

CREATE TABLE IF NOT EXISTS gfm.documents (
 org_id uuid NOT NULL,
 document_id uuid NOT NULL,
 repo_id text NOT NULL,
 path text NOT NULL,
 sha256 text NOT NULL,
 kind text NOT NULL,
 scope text,
 size_bytes bigint NOT NULL,
 import_id uuid NOT NULL,
 commit text,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,document_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_content ON gfm.documents(org_id,repo_id,path,sha256);
CREATE INDEX IF NOT EXISTS documents_scope ON gfm.documents(org_id,repo_id,scope);

CREATE TABLE IF NOT EXISTS gfm.owner_queue (
 org_id uuid NOT NULL,
 item_id uuid NOT NULL,
 repo_id text NOT NULL,
 skill_id text NOT NULL,
 revision_id text,
 reason text NOT NULL
  CHECK(reason IN ('negative_feedback','source_changed','source_removed','zero_loads','missing_dependency')),
 evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
 since timestamptz NOT NULL DEFAULT now(),
 state text NOT NULL DEFAULT 'open' CHECK(state IN ('open','resolved')),
 decision text CHECK(decision IN ('reviewed','fixed_in_git','no_change')),
 decision_reason text,
 decided_by uuid,
 decided_at timestamptz,
 PRIMARY KEY(org_id,item_id)
);
-- NULLS NOT DISTINCT so a second run of the same manifest cannot append a
-- second open item for a reason that carries no revision (U9: "a repeated
-- import creates no new owner-queue entries").
CREATE UNIQUE INDEX IF NOT EXISTS owner_queue_open
 ON gfm.owner_queue(org_id,skill_id,reason,revision_id) NULLS NOT DISTINCT
 WHERE state='open';
CREATE INDEX IF NOT EXISTS owner_queue_state ON gfm.owner_queue(org_id,state,since DESC);
INSERT INTO gf.schema_version VALUES (10) ON CONFLICT DO NOTHING;
`
