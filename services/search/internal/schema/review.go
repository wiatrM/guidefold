package schema

// Review and publication tables (API-CONTRACT §7). They are the only tables the
// *review* module owns: a proposal, the provenance of each of its fields, the
// decisions taken on it, the export that turns an approved candidate into a
// patch, and the publication that turns an import into a serving snapshot.
//
// Two shapes here carry a rule rather than a convenience.
//
// `UNIQUE(org_id, cache_key)` is what makes "a rejected proposal is never
// regenerated" true (U2 §Review). The key is sha256(org, sorted input digests,
// recipe version, model revision, candidate identity), so the same inputs under
// the same recipe collide with the row that already holds the owner's decision
// instead of producing a second candidate.
//
// `gfm.publications` keeps the engine's five states while the import DTO shows
// four (`ImportPublication.state`, §5.2): `active` and `superseded` both read as
// `published` from an import's point of view, because what an import wants to
// know is whether its build ever reached the head, not whether it still is it.
const reviewSQL = `
CREATE TABLE IF NOT EXISTS gfm.proposals (
 org_id uuid NOT NULL,
 proposal_id uuid NOT NULL,
 repo_id text NOT NULL,
 import_id uuid,
 job_id uuid,
 kind text NOT NULL CHECK(kind IN ('extraction','enrichment','consolidation')),
 state text NOT NULL DEFAULT 'draft'
  CHECK(state IN ('draft','approved_for_export','awaiting_git','published','rejected','superseded')),
 scope text,
 owner text,
 target_skill_id text,
 target_revision_id text,
 expected_revision text,
 candidate_path text NOT NULL,
 candidate_sha256 text NOT NULL,
 candidate_blob_sha256 text NOT NULL,
 candidate_frontmatter jsonb NOT NULL DEFAULT '{}'::jsonb,
 sources jsonb NOT NULL DEFAULT '[]'::jsonb,
 recipe_version text NOT NULL,
 generator text NOT NULL,
 model text,
 cache_key text NOT NULL,
 cost jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,proposal_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
-- The cache key is the whole dedupe rule: same organisation, same inputs, same
-- recipe and model revision, same candidate — one row, whatever its state.
CREATE UNIQUE INDEX IF NOT EXISTS proposals_cache ON gfm.proposals(org_id,cache_key);
CREATE INDEX IF NOT EXISTS proposals_state ON gfm.proposals(org_id,state,created_at DESC);
CREATE INDEX IF NOT EXISTS proposals_repo ON gfm.proposals(org_id,repo_id,created_at DESC);

CREATE TABLE IF NOT EXISTS gfm.proposal_fields (
 org_id uuid NOT NULL,
 proposal_id uuid NOT NULL,
 field text NOT NULL,
 origin text NOT NULL CHECK(origin IN ('source','parsed','inferred','human')),
 source_path text,
 source_sha256 text,
 line_from integer,
 line_to integer,
 needs_confirmation boolean NOT NULL DEFAULT false,
 value_sha256 text,
 PRIMARY KEY(org_id,proposal_id,field),
 FOREIGN KEY(org_id,proposal_id) REFERENCES gfm.proposals(org_id,proposal_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gfm.decisions (
 org_id uuid NOT NULL,
 decision_id uuid NOT NULL,
 proposal_id uuid NOT NULL,
 decision text NOT NULL CHECK(decision IN ('approve','edit','reject')),
 reason text NOT NULL,
 actor_user_id uuid NOT NULL,
 expected_revision text,
 result_revision_id text,
 request_id text NOT NULL DEFAULT '',
 at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,decision_id),
 FOREIGN KEY(org_id,proposal_id) REFERENCES gfm.proposals(org_id,proposal_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS decisions_proposal ON gfm.decisions(org_id,proposal_id,at DESC);

CREATE TABLE IF NOT EXISTS gfm.exports (
 org_id uuid NOT NULL,
 export_id uuid NOT NULL,
 proposal_id uuid NOT NULL,
 base_commit text,
 files jsonb NOT NULL DEFAULT '[]'::jsonb,
 patch text NOT NULL,
 files_digest text NOT NULL,
 created_by uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,export_id),
 FOREIGN KEY(org_id,proposal_id) REFERENCES gfm.proposals(org_id,proposal_id) ON DELETE CASCADE
);
-- Exporting the same approved candidate twice is the same export: the patch is
-- a function of the files, not of when the button was pressed.
CREATE UNIQUE INDEX IF NOT EXISTS exports_content ON gfm.exports(org_id,proposal_id,files_digest);

CREATE TABLE IF NOT EXISTS gfm.publications (
 org_id uuid NOT NULL,
 publication_id uuid NOT NULL,
 repo_id text NOT NULL,
 import_id uuid,
 job_id uuid,
 snapshot_id text,
 state text NOT NULL DEFAULT 'building'
  CHECK(state IN ('building','validated','active','failed','superseded')),
 commit text,
 n_skills integer NOT NULL DEFAULT 0,
 builder_sha256 text,
 validation jsonb,
 error text,
 activated_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,publication_id),
 FOREIGN KEY(org_id,repo_id) REFERENCES gfm.repos(org_id,repo_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS publications_snapshot
 ON gfm.publications(org_id,repo_id,snapshot_id) WHERE snapshot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS publications_recent ON gfm.publications(org_id,repo_id,created_at DESC);

-- Which snapshot a skill's published revision is serving in. USE 1.2 answers
-- "what are this revision's package resources" from gfm.skill_resources, and it
-- may only do so for the revision the *active* snapshot actually carries — a
-- resource list from a newer, unpublished revision would be a quiet mixture.
ALTER TABLE gfm.skills ADD COLUMN IF NOT EXISTS published_snapshot_id text;

-- The card revision (gf.skills.skill_revision) this revision was published as.
-- The delivery path hands a harness that identifier and adapter telemetry echoes
-- it, while a judgment recorded in the UI names the catalog revision. Storing the
-- pair is what lets the usage report resolve both to one row instead of counting
-- one skill twice under two identifiers (API-CONTRACT §5.5).
ALTER TABLE gfm.skill_revisions ADD COLUMN IF NOT EXISTS card_revision text;
CREATE INDEX IF NOT EXISTS skill_revisions_card
 ON gfm.skill_revisions(org_id,card_revision) WHERE card_revision IS NOT NULL;

INSERT INTO gf.schema_version VALUES (12) ON CONFLICT DO NOTHING;
`
