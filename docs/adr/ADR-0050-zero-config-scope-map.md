# ADR-0050: `guidefold.yaml` is an override, not a requirement — the scope map is inferred

**Status:** Accepted · 2026-09-15 · owner decision the same day: "nie podoba mi się mus tworzenia
guidefold.yaml" and "CODEOWNERS też daje dużo info". The file must never be required.
**Governs:** `load_map()` and every command that reads it in `skills/guidefold/scripts/guidefold`
(`where`, `find`, `scan`, `validate`, `index`, `materialize`, `report`, `extract`, `doctor`,
`init`), `tools/worker/build_tree.py`, `import.parse`'s `writeScopes`, the
`github.import_repo`/`live.repo` fetch path, `gfm.scopes.source` and the Map › Scopes view.
**Depends on:** [ADR-0008](ADR-0008-registry-id-mapping-and-node-flattening.md) (node flattening
and collisions), [ADR-0033](ADR-0033-api-contract-first-and-mvp-storage.md) (contract before
code), [ADR-0046](ADR-0046-live-agent-on-demand-across-connected-repositories.md) (the Live
Agent's per-target skip reasons), [ADR-0047](ADR-0047-organisation-is-the-default-read-scope.md).
**Does not change:** the ranking (`Router`, `Index`, BM25F, the index artifact), the harness hook
(which reads `nodes.json` from the built artifact and never `guidefold.yaml` or PyYAML), any
route or mutation, or the precedence a repository that *does* have the file enjoys.

## Context

`docs/PRODUCT-PIVOT.md:69` (U1) has always said: "guidefold.yaml ma pierwszeństwo w mapowaniu
scope. Katalogi i CODEOWNERS dostarczają propozycji, jeśli mapy brak. Niepewna hierarchia/owner
są widoczne i nie stają się samoczynnie polityką." *Precedence*, not *requirement*.

The code was stricter than that everywhere it mattered:

- `load_map()` read `root / "guidefold.yaml"` unconditionally and raised without it.
- `doctor` reported `fail: guidefold.yaml not found at repo root`.
- `report --base` refused a base commit that had no file.
- `tools/worker/build_tree.py:150` raised `import_tree_has_no_guidefold_yaml`.
- `fetchRepositoryImport` skipped any GitHub repository with no file, writing
  `gfm.repos.import_blocked_reason = 'guidefold_yaml_missing'`.

On 2026-09-15 production had 43 repositories synced through the GitHub App, **0 imports**, and
one repository already blocked for exactly this reason
(`docs/reports/product/2026-09-15-mvp-closure-status.md` §7). This repository — the product's own
monorepo — has no `guidefold.yaml` either. The first thing a new user had to do was author a file
describing a hierarchy the tree already states, before Guidefold would look at their skills at
all. That is the opposite of what the product sells.

The information needed to answer "which scope is this skill in, and who owns it" is already in
the repository: the directory a skill directory sits in, and CODEOWNERS. Both were already parsed
by the CLI — `_scan_suggestions` computed exactly this, but strictly as advice that was never fed
back into `node_for()`/`urn()`.

## Decision

### 1. Precedence

A scope map has three tiers, most specific first:

| Tier | `gfm.scopes.source` | Written by |
|---|---|---|
| The repository declares it | `guidefold_yaml` | the committed `guidefold.yaml` |
| A human approved a proposal | `console` / `llm_approved` | the review module (designed here, implemented by a sibling change; no code in this ADR's change) |
| Nobody said anything | `inferred` | `infer_map()` |

A file that exists always wins. An inferred map never overwrites a declared one, and an inferred
scope is visible as inferred everywhere it is stored or shown — it does not quietly become
policy (U1 AC2).

### 2. The inference rules

One implementation, `infer_map()` in the CLI, reached by the CLI, `report --base` (over the tree
`git archive` materialises for the base ref) and the worker's `build_tree.py` (which already
loads and executes the CLI's own module). A second implementation would be the fastest way to
produce URNs that disagree with the ranker's.

- **Node** — every directory that holds a *recognised skill directory*, using the same pair the
  CLI already recognises (`_SKILL_DIR_MARKERS`: `.agents/skills/`, `.claude/skills/`), i.e. the
  directory **above** the `.../skills/<name>` wrapper, plus every directory above it on the way
  down. The intermediate nodes exist so `ancestors()` never names a node the map does not hold
  (`platforms.atlas` implies `platforms`).
- **Node name** — the directory path relative to the root with `/` → `.`, each segment slugified
  to the `[a-z0-9-]` alphabet node validation already demands. ADR-0008's flattening (`.` → `-`)
  and its collision rule are unchanged; two directories that slugify to the same node name share
  one node, and their globs are merged, rather than one silently shadowing the other.
- **`paths`** — `["<dir>/**"]`. `_root` is implied with `["**"]`.
- **Owner** — CODEOWNERS' own documented "last matching rule wins" verdict for the node's
  directory (`_codeowners_rules`/`_codeowners_match`, already in the CLI); `_root` takes the
  whole-repo rule (`_infer_owner_from_codeowners`); `unknown` when CODEOWNERS says nothing.
- **`publisher`** — the logged-in organisation slug from the credentials `guidefold login`
  writes, else the git remote's owner segment, else the root directory name. `publisher_source`
  records which of the three answered. A caller that already knows the answer passes it:
  `report --base` passes the working tree's publisher so base and head URNs are comparable, and
  `build_tree.py` is given `--publisher <repo_id>` by the Go builder, because a materialised
  worker tree has neither a git remote nor credentials and would otherwise name every URN after
  a scratch directory.
- **Marking** — the synthesized config carries `_source: "inferred"`, and the builder's envelope
  carries `scope_source`, so `index`/`materialize`/`report` and the importer can record it.

Only the standard library is used on this path: existence of the file is tested *before* PyYAML
is imported, so a repository without one needs nothing installed.

### 3. What this costs, and what stays

- **Node names follow directories.** Meridian declares `atlas` for `platforms/atlas/**`; inferred,
  the same directory is `platforms.atlas`. That difference is the point of writing the file: a
  `guidefold.yaml` is how an organisation names its nodes something other than its folders.
- **URN stability.** An inferred node name follows the directory, so moving a skill directory
  renames its node and therefore its URN. This is not a new risk — the same move without an
  `import.aliases` entry already looked like delete + create — and the existing safeguard stays
  the only one: a rename goes to review (U1 AC5), and `guidefold.yaml`'s `aliases` remains the
  way to pin a name across a move.
- **The hook is unaffected.** `cmd_hook` resolves `cwd -> node` from `nodes.json` inside the
  prebuilt index artifact, never from the working tree, and imports no PyYAML. It gets an
  inferred map the same way it gets a declared one: baked into the artifact by `guidefold index`.
- **Ranking is unaffected.** Nothing in `Index`, `Router`, BM25F or the artifact format changes.
  A repository that has `guidefold.yaml` produces byte-identical snapshots, digests and rankings.

### 4. What leaves `guidefold.yaml` (designed, not implemented here)

`search.*` and `registry.*` are deployment coordinates of an *organisation*, not facts about a
tree, and they are the reason `install` still wants a file to write into. They belong in what
`guidefold login` stores (`~/.config/guidefold/credentials.json`, already per-API) and in
organisation settings served by the management API. This ADR records the direction; the move is
not in this change, because it touches `resolve_search_config`, `install`/`uninstall` and the
`service:` block, which is more than the zero-config decision needs. Until then `install` says so
in its plan instead of telling the owner to run `init` first.

### 5. Blocking is now reserved for a declared map that cannot be read

`guidefold_yaml_missing` stops being written. A repository with no file is imported. A repository
that *declares* a `guidefold.yaml` this run cannot read (today only a file over
`ghapp.MaxFileBytes`) still ends `worker.Skipped`, now with `guidefold_yaml_unreadable`:
inferring a map that contradicts a map the owner actually wrote would be worse than saying so.
`guidefold_yaml_missing` stays defined and decodable — production holds one row with it.

`import.parse` still fails an import whose `guidefold.yaml` does not parse
(`import_tree_guidefold_yaml_unparseable`); that was already a named failure, not a block.

## Consequences

- Contract 1.14.0: `gfm.scopes.source` accepts `inferred` (a widened CHECK — **production needs
  the `migrate` Job before the new images**), `ScopeNode.source` documents the value, and §3 gains
  `guidefold_yaml_unreadable`. Widening a CHECK never rejects a stored row.
- `guidefold init` no longer writes a `guidefold.yaml` skeleton by default; `--scope-map` does,
  and the plan says why it did not.
- `doctor`'s `guidefold-yaml` check can no longer fail for absence. It reports what was inferred
  and from how many skill directories, and hints that a file is worth adding only if that map is
  wrong.
- A tree with no `SKILL.md` at all now fails the build with `import_tree_has_no_skills` instead
  of producing a 0-card snapshot the publisher later rejects as `invalid_snapshot_dimensions`.
  That shape was always possible; this decision makes it common, because a repository with no
  `guidefold.yaml` is no longer filtered out before the builder runs.
- **Not done here, deliberately:** the GitHub App's fetch list is unchanged, so CODEOWNERS is not
  fetched on that path and a scope inferred from GitHub content has `owner: unknown` until a
  separate, contract-visible change adds it. `tools/serve_spike/repository.py` (the git spike
  serving path) still requires the file; it is a development spike, not the import path.
- Evidence level: R. Proven on the Meridian fixture without the file, on a synthetic tmp fixture
  with a CODEOWNERS the test writes, and through `import.parse`, `github.import_repo` and
  `live.repo` against a real Postgres. No pilot (P) evidence is claimed.
