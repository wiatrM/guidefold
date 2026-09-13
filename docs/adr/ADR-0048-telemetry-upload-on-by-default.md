# ADR-0048: Telemetry upload is on by default once a token and endpoint exist; opt-out is explicit

**Status:** Accepted · 2026-09-13 · owner, before the automation work in this change started: "klient automatycznie powinien miec opt in na telemetrie" (a client should automatically have telemetry opted in) — the user switches it off explicitly in the CLI settings.
**Amends:** [docs/DESIGN.md](../DESIGN.md) R7 ("opt-in upload") and [docs/SEARCH-USE-TELEMETRY.md](../SEARCH-USE-TELEMETRY.md) §5 ("Enable upload through explicit organization configuration with visible diagnostics"), for the *default* only.
**Purpose:** flip the automatic-upload default from off to on. Nothing about telemetry content, collection, retention, or the hook latency budget changes.
**Inputs:** owner instruction 2026-09-13, given while the automatic-upload mechanism (`guidefold telemetry enable`/`disable`, a detached background flush after `find`/`hook`/`load`) was being built to the previously-written opt-in rules below. This ADR is what makes flipping that default correct rather than a rule violation.

## Context

`docs/SEARCH-USE-TELEMETRY.md` §5 and `docs/DESIGN.md` R7 required explicit enablement before
any telemetry upload. That was the correct read of the documents at the time, and the CLI
implementation honoured it: automatic background upload shipped with
`TELEMETRY_UPLOAD_ENABLED_DEFAULT = False`, requiring `guidefold telemetry enable` before the
first automatic flush.

The owner's decision is the opposite default: once an adapter is genuinely configured as part of
an organisation's deployment — it has a working bearer credential (a signed-in user's token or an
installation token) and a configured SEARCH/USE endpoint — it should already be contributing
telemetry, not wait on a separate manual step per install or per machine. "Explicit
configuration" is expressed going forward as the ability to opt **out**, not a requirement to opt
**in**.

This decision does not relax any control over *what* is collected or *how* it leaves the
machine:

- Spool bounds are unchanged (10 MB / 7 days, oldest-first drop).
- Raw prompt text still stays out of the spool by default; only an optional keyed HMAC for query
  grouping, as before.
- `cmd_hook`'s own process still never opens a socket. The automatic trigger only ever spawns a
  fully detached, unawaited child process (`subprocess.Popen(..., start_new_session=True)`) —
  E1.5 is unaffected regardless of which way the default points.
- The per-repo minimum interval (60s) and the background run's wall-clock budget (10s) are
  unchanged.

## Decision

1. `TELEMETRY_UPLOAD_ENABLED_DEFAULT` flips to `True`. `_telemetry_upload_enabled()`'s
   precedence is unchanged: `GUIDEFOLD_TELEMETRY` env override > the persisted
   `settings.json` value (once `enable`/`disable` has been run) > this default.
2. **Effective behaviour:** as soon as an adapter has both a bearer credential and a configured
   SEARCH/USE endpoint, the next `find`/`hook`/`load` call that emits telemetry triggers an
   automatic background flush — `guidefold telemetry enable` is no longer required to reach that
   state. An adapter with no credential or no endpoint still uploads nothing (never send before
   there is a token or somewhere to send it), same as before this ADR.
3. Opt-out remains three levers, most-to-least persistent:
   - `guidefold telemetry disable` — persisted to `settings.json`, survives across sessions and
     repositories on that machine until re-enabled.
   - `GUIDEFOLD_TELEMETRY=0` — process/CI-scoped override; does not touch the persisted setting.
   - `GUIDEFOLD_TELEMETRY_DISABLE` (pre-existing, unrelated switch) — stops local *spooling*
     entirely, the hardest of the three, and always wins over the other two.
4. The one-time notice — one line to stderr, never stdout (the hook path's stdout is the
   harness's own context channel) — prints **before the background flush is spawned**, i.e.
   before or at the moment of the first upload, never after the fact. It names the exact
   command to turn upload off: `"[guidefold] telemetry: automatic upload is on (guidefold
   telemetry disable to turn it off)."` A persisted flag keeps it from repeating.
5. Nothing about event content changes: no new field, no widening of what is spooled, same
   redaction rules as always.

## Consequences

**An organisation that must not upload telemetry at all now has to say so explicitly**, on every
developer machine and in every CI job that runs the adapter — it is no longer off until someone
turns it on. That is the deliberate trade this ADR makes, and it must be visible wherever an
administrator configures the adapter, not only in this file:

- `docs/CONVENTIONS.md` §11a states the default is ON and gives the disable command and both
  env-var overrides in the same place it documents the mechanism.
- `docs/HOWTO-adapter.md` step 5 states upload is on automatically once a credential and endpoint
  exist, and gives the exact opt-out command for an administrator who reaches that page looking
  for it.
- A monorepo or CI template that provisions the adapter for many machines and must not upload
  telemetry should set `GUIDEFOLD_TELEMETRY_DISABLE=1` (or `GUIDEFOLD_TELEMETRY=0` for one job)
  explicitly — relying on the previous default is no longer correct.

Other consequences:

- An install that already ran `guidefold telemetry disable` is unaffected — the persisted
  setting still wins over the default either way.
- A fresh install with a working credential and endpoint starts uploading on its first
  qualifying `find`/`hook`/`load` call, printing the one-time notice first.
- Test suite: every "default is off" assertion in `tests/test_telemetry_auto_flush.py` becomes
  "default is on"; every opt-out path (disable command, env override, hard disable, the
  min-interval/budget/detached-spawn mechanics) keeps its own test, unchanged in behaviour.

## References

- [docs/DESIGN.md](../DESIGN.md) R7 and [docs/SEARCH-USE-TELEMETRY.md](../SEARCH-USE-TELEMETRY.md)
  §5 — amended by this ADR to read "opt-out, on by default" and link here.
- [docs/adr/ADR-0041-training-signal-storage-and-dataset-boundaries.md](ADR-0041-training-signal-storage-and-dataset-boundaries.md)
  — the telemetry dataset/storage/retention boundaries this ADR does not touch.
- `skills/guidefold/scripts/guidefold`: `_telemetry_upload_enabled`, `_settings_path`/
  `_load_settings`/`_save_settings`, `cmd_telemetry_enable`/`cmd_telemetry_disable`,
  `maybe_trigger_telemetry_auto_flush`, `_spawn_auto_flush`.
