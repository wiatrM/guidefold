# Structured-corpus SEARCH parity — Meridian fixture, 2026-09-05 (E1.1b/E2.9)

**0 / 243 mismatches** (220 labelled golden queries + 23 synthetic structural probes) through
`POST /v1/search` against the real Go/ParadeDB service, on the 26-skill Meridian fixture — the
first corpus with `requires`/`refines` edges, scope hierarchy depth, `negative_triggers`, a
deprecated skill and node-scoped queries. PR #61's `telemetry_health.parity_mismatch` alert was
real, but the root cause is **two client-side defects in the CLI's `search_with_backend`**, not a
Go ranking defect: the client never sent `budget.max_cards`, so the service silently applied its
own default of 4 regardless of the caller's actual `k`; and `--include-deprecated --backend
service` had no way to express that intent on the wire at all. Both are fixed in this PR, covered
by tests, and verified live against the isolated service. With both fixed, the Go service shows
**zero ranking disagreement** with the reference CLI on every structural feature ADR-0024 §1
promises parity for.

## 1. Why PR #54's 0/1,000 gate missed this

`tools/search_service/parity.py` ran only the frozen SKILLRET DEV queries — a flat 10,123-document
corpus with no `requires`/`refines` edges, no scope hierarchy, no `negative_triggers`, no
deprecated skills, and no node context (every query effectively fires from `_root`). It could not
have caught either defect: `budget.max_cards` only matters when the caller's local `k` differs
from Go's hardcoded default of 4, and the DEV gate always requests exactly `k=4`; the graph/scope/
policy features it never exercises have no path in a flat corpus at all.

## 2. Setup

Isolated stack, distinct from any other agent's ports: `COMPOSE_PROJECT_NAME=gf-par-e29`,
`GUIDEFOLD_PORT=8792`, `GUIDEFOLD_IMAGE=gf-par-e29-search:local`. Deployed via
`tools/search_service/dev.py deploy --repo-root examples/monorepo --repo-id meridian` (builds the
Go image from the current worktree — including `/app/policy-source`, a build-time `COPY` of the
CLI script whose sha256 gates every snapshot's publish and the service's own `/health/ready`, see
§5 — then publishes and brings `api` up healthy).

`tools/search_service/parity.py --fixture` (new mode, this PR):
- Builds the Meridian fixture + 220 golden cases via `tools/search_service.quality.dataset('regression', cli)`
  (same helper the golden-eval CI job uses), under repo id `meridian-fixture-parity` so it never
  collides with the `meridian` repo the interactive stack itself uses.
- Adds 23 hand-designed synthetic queries (`FIXTURE_SYNTHETIC_QUERIES` in `parity.py`), one row
  per structural feature named in the brief that the golden set does not reliably stress alone.
- Computes expected `ranked`/`selected` locally via the unchanged CLI's
  `policy_filter → candidates → score → select(admissible=…, query=q)`, compares byte-for-byte
  against the live HTTP response (top-10 URN+integer score, selected ordered URNs, card
  revisions) — identical comparison shape to the existing DEV gate.
- Runs a fourth check, `_budget_adapter_checks`: calls the real, unmodified
  `cli.search_with_backend(...)` adapter (not a raw HTTP diff) at the three k values the product
  actually uses — hook (`k=3`), `find`'s default (`k=8`), interactive (`k=4`) — and asserts
  `parity_mismatch is False` for each, plus that `k=8` never opens the remote socket at all.

Real run against the isolated stack (`.guidefold/checks/router-parity-fixture.json`):

```json
{"attempted": 243, "http_ok": 243, "mismatches": 0, "exact_output_parity_passed": true,
 "documents": 26, "wall_s": 0.75,
 "budget_adapter_checks": [
   {"label": "hook",         "k": 3, "backend": "online_sparse", "degradation_reason": null,    "parity_mismatch": false, "passed": true},
   {"label": "find_default", "k": 8, "backend": "local_sparse",  "degradation_reason": "config", "parity_mismatch": false, "passed": true},
   {"label": "interactive",  "k": 4, "backend": "online_sparse", "degradation_reason": null,    "parity_mismatch": false, "passed": true}
 ]}
```

Wall time for the full `--fixture` invocation (publish + HTTP measurement, warm stack): **~24 s**,
well under the 3-minute budget. `documents: 26` and `attempted: 243` confirm the 26-skill/243-query
corpus, not the flat DEV set.

## 3. Feature-attribution table

Post-fix, every structural feature has **0 affected queries** — the Go service agrees with the
CLI in every case tested. `n` is the number of queries covering that feature in this run.

| feature | n | example (qid @ node) | result |
|---|---|---|---|
| scope-distance (near/far ancestor, cross-subtree via `requires`) | 4 | `scope-1a`/`scope-1b` @ `atlas.identity.turnstile` / `forge.ontology`, `scope-2a`/`scope-2b` | 0 mismatches |
| graph propagation, decayed closure (`ppr_mode=closure`, the shipped default — 2-hop, `requires`-only) | 2 | `graph-1` @ `atlas.identity.turnstile`, `graph-2` (two simultaneous `requires` edges) @ `forge.pipelines.streaming` | 0 mismatches |
| `requires`-closure pulled into `select()`'s admissible set | 2 | `reqclosure-1` @ `forge.ontology`, `reqclosure-2` @ `security.audit` | 0 mismatches |
| `negative_triggers` hard-drop in `policy_filter` | 3 | `negtrig-1` @ `_root`, `negtrig-2` @ `relay.k8s`, `negtrig-3` @ `shared` | 0 mismatches |
| deprecated-skill filtering | 1 | `deprecated-1` @ `atlas.identity` | 0 mismatches (see footnote — `replaces`-edge propagation is unreachable under the default, so this only exercises the drop itself, not a replacement boost) |
| abstention (`scored=[]` on zero vocabulary overlap) | 2 | `abstain-1` @ `_root`, `abstain-2` @ `atlas.geo` | 0 mismatches |
| tokenizer accent-folding (NFC vs NFD of the same string) | 2 | `tok-accents-nfc`/`tok-accents-nfd` @ `atlas.geo` | 0 mismatches |
| tokenizer digits (alnum boundaries) | 2 | `tok-digits-1`/`tok-digits-2` | 0 mismatches |
| per-field BM25F weight coverage (triggers-only / digest-only / name-only match) | 3 | `field-triggers-1`, `field-digest-1`, `field-name-1` | 0 mismatches |
| `refines` edge (confirmed **not** a propagation input under `ppr_mode=closure`; no incidental scoring effect) | 1 | `graph-3` @ `relay.k8s` | 0 mismatches |
| multi-skill composite query (`compose_mode` default off → legacy closure-fill) | 1 | `multi-1` @ `forge.ontology` | 0 mismatches |
| tie-break (`depth asc, score desc, urn asc`) | 0 natural | — | **no live tie exists** in this 26-skill fixture (220 golden cases + a brute-force single-term × all-17-nodes sweep, ~39,066 combinations, produced zero ties); correctness rests on the static code-audit equivalence of Python's `_emit`/`_select_closure` and Go's final `sort.Slice`, both keyed identically — documented as a finding, not fabricated as a synthetic tie |
| 220 golden queries (own `node` context, `tests/golden/*.yaml`) | 220 | — | 0 mismatches |
| **total** | **243** | | **0 mismatches** |

## 4. The two real defects — both client-side, in `search_with_backend`

| defect | trigger | pre-fix behavior | fix |
|---|---|---|---|
| **`budget.max_cards` never sent** (root cause of PR #61's alert) | any local `k != 4` — hook (`k=3`), `find`'s default (`k=8`), any `--limit` | Go applies its own hardcoded default of 4 (`services/search/main.go:171`, `integer(budget, "max_cards", 4)`); local and remote selections structurally differ in size whenever `k != 4` | send `"budget": {"max_cards": k}` whenever `0 <= k <= 4`; when `k` falls outside that range, never open the remote socket — fall back to local with `degradation_reason="config"` (contract v1.1's `budget.max_cards` tops out at 4, so an unrepresentable `k` can never get an honest remote answer regardless of ranking correctness) |
| **`include_deprecated=True` + `backend: service`** | `--include-deprecated --backend service` | contract v1.1's `search_request` schema has no field for it at all, and the service unconditionally excludes deprecated cards with no override; racing the remote silently drops deprecated cards the caller explicitly asked to see | same guard: never open the remote socket in this combination, fall back to local with `degradation_reason="config"` |

Both are unified into one `budget_representable = 0 <= k <= 4` guard in `search_with_backend`
(`skills/guidefold/scripts/guidefold`). Covered by `tests/test_service_backend.py`:
`test_budget_max_cards_is_sent_for_every_representable_k` (k=0,1,3,4),
`test_unrepresentable_k_never_races_the_service_backend` (k=5,8,-1, asserts the socket is never
opened), `test_include_deprecated_never_races_the_service_backend`, and an updated assertion on
the existing happy-path test. 42/42 pass; full suite (`pytest tests/`) passes, 2 skips unrelated
(missing optional `torch`).

Verified live, not just against mocks: `cli.search_with_backend(...)` was invoked directly against
the isolated service for the exact scenario PR #61 would have hit — query "monorepo conventions
and adr process for a new service" at `_root`, across hook (`k=3`), find-default (`k=8`) and
interactive (`k=4`) — and independently as `_budget_adapter_checks` inside `parity.py --fixture`
above; every scenario now reports `parity_mismatch=False`.

**This is independently corroborated**: a parallel investigation on branch `codex/graph-parity`
(commit `a0ad16d`, not merged, not touched by this branch) built its own probes
(`tools/search_service/graph_parity.py`, `client_budget_probe.py`) and reached the identical root
cause in `docs/reports/bakeoff/MERIDIAN-GRAPH-PARITY-2026-09-05.md`: 3,448/3,448 SEARCH responses
identical across 220 golden queries × 2 graph modes (closure, pagerank) × 4 budgets (0,1,3,4) × 2
addressing methods, 72/72 correct unmapped-path rejections, 52/52 USE checks — i.e. the Go service
itself is clean; the client's missing `budget.max_cards` is what PR #61 saw. That report
explicitly left the CLI unchanged "under the existing ownership restriction," deferring the fix to
the CLI owner — this PR is that fix.

## 5. A structural note on the fixture stack (not a parity bug)

The Go image bakes the CLI script into `/app/policy-source` at build time
(`services/search/Dockerfile:12`) and hashes it as `PolicySHA`; both `/health/ready` and every
snapshot publish reject a mismatch (`services/search/store.go:111,328`, `snapshot_policy_mismatch`).
Editing the CLI without rebuilding the image makes an already-running stack reject its own
previously-published snapshots. This is by design (it is exactly what stops a silent CLI/service
skew), but it means: after editing `skills/guidefold/scripts/guidefold`, rebuild (`docker compose
build api`) and republish before trusting a long-running dev stack. Encountered and resolved during
this work; not a code change.

## 6. Client-side vs. service-side verdict

**Both real defects are client-side**, in the CLI's `search_with_backend`, now fixed with tests.
**No Go/ParadeDB ranking defect was found** on the tested corpus: 0/243 mismatches covering scope
distance, graph propagation (both `requires`-closure modes), `refines`'s correct non-effect,
`negative_triggers`, deprecated filtering, abstention, tokenizer accent/digit edge cases, and
per-field weight coverage. `skills/guidefold/scripts/guidefold` (the reference CLI, per the brief)
was not modified outside `search_with_backend`; the Go service (owned by another session) was not
modified at all.

Two footnotes, out of scope for this PR (not client-side bugs, and touching Router/Index or the Go
service is excluded by this brief):
- Under the shipped default (`ppr_mode="closure"`), the `replaces` edge (deprecated → replacement
  propagation) is **dead code** in both implementations — `_decayed_closure` (Python) and its Go
  mirror only ever read the `requires` graph. Only the non-default `pagerank` mode uses `replaces`,
  and even there Python's and Go's own edge construction appears inverted relative to their
  documented deprecated→replacement direction (consistently between the two, so not a parity gap).
- `_decayed_closure`'s docstring (`skills/guidefold/scripts/guidefold`, near line 1754) says
  "default stays 'pagerank'," which contradicts the actual `DEFAULT_WEIGHTS["ppr_mode"] = "closure"`.
  Stale comment, not a behavior bug.

## 7. Acceptance criteria for the service owner

**Already met by this run.** `python tools/search_service/parity.py --fixture` reports 0/243
mismatches against the current Go service. The new step is wired into CI as a **strictly
blocking** step (no `continue-on-error`) — there is no known mismatch to work around, so weakening
it would hide a real regression rather than tolerate a known one. If a future service-side change
regresses structured-corpus parity, this step fails CI immediately; the fix is to correct the
regression, not to add `continue-on-error`.

## 8. Deviation from the brief: CI job placement

The brief names the `native-service` job. `.github/workflows/ci.yml`'s `native-service` job
(lines ~79–102) runs only Go race tests, `go vet`, and regenerates policy/BM25F/telemetry
conformance fixtures from the CLI with `git diff --exit-code` — it has no Compose/HTTP capability
at all. The existing 1,000-query DEV parity gate (the thing this PR extends) already lives in the
`compose-service` job, which deploys the real Go+ParadeDB stack via `dev.py deploy`. The new
`--fixture` step is added there, immediately after the existing DEV parity step, and its output is
added to the same "Upload integration evidence" artifact. **Independently corroborated**: the
`codex/graph-parity` branch's own report reaches the identical conclusion ("Branch protection must
require `compose-service` to enforce the HTTP gate; `native-service` alone only enforces the
existing Go unit/fixture checks").

## 9. What was not done

Nothing from the brief's deliverables is outstanding. Not attempted (explicitly out of scope per
the brief): fixing the Go service's `replaces`-edge dead-code/direction quirk or its stale
`_decayed_closure` docstring (§6 footnotes) — both are pre-existing, shared between languages, and
not parity bugs.
