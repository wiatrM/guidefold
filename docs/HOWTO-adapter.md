# HOWTO: install and run the adapter

Status: how-to, updated 2026-09-13 (owner instructions: sign in the way Claude Code does — a
device code confirmed in the browser, no token copied by hand — and telemetry upload is
automatic and on by default once a credential and endpoint exist, [ADR-0047](adr/ADR-0047-telemetry-upload-on-by-default.md); an organisation that must not upload has to disable it
explicitly). Originally written 2026-09-12 after an owner asked "what is an
adapter? did you write a HOWTO how to install both?" on seeing "No adapter installed" and "No
telemetry in the last 30d" on Overview. This is the reference version of the same steps shown in
the console (Organization → Integrations → "Set up an adapter"), plus troubleshooting. Every
command below is quoted verbatim from `skills/guidefold/scripts/guidefold` — its usage block and
the `cmd_install`, `cmd_login`, `cmd_doctor`, `cmd_telemetry_enable`/`cmd_telemetry_flush`
functions and their argparse definitions. If a flag is not in that file, it is not a real flag;
do not invent one.

## What is an adapter?

The adapter is the consumer-side harness integration: the `skills/guidefold/` package this repo
ships, copied into a consumer repo at `.agents/skills/guidefold/`. It has two parts:

- **Hook templates** (`skills/guidefold/hooks/*.json`) that wire a harness (Claude Code, Copilot
  CLI, Codex, Gemini CLI) to call the CLI automatically.
- **A single-file CLI** (`skills/guidefold/scripts/guidefold`) that performs SEARCH/USE against
  this hosted service — authenticated by the same sign-in as step 2 below, an installation token
  only as the CI/scripted fallback (step 4) — and queues telemetry events that are sent
  automatically once a credential and endpoint exist (step 5, on by default), no manual flush
  required.

Without an adapter installed and authenticated, no delivery or feedback reaches this
organization's ledger, so usefulness stays Unknown — that is what "No adapter installed" and
"No telemetry in the last 30d" on Overview mean.

## Steps

### 1. Install the adapter

Run this from the consumer repo checkout. It copies the CLI and wires the harness hook into
`.agents/skills/guidefold/`.

```sh
guidefold install --harness claude
```

`--harness` accepts `claude`, `copilot` or `gemini` — the choices the CLI's own `install`
subcommand takes today (`skills/guidefold/scripts/guidefold:8543`
`INSTALL_HARNESSES = ("claude", "copilot", "gemini")`). `install` is idempotent and has an
`uninstall` counterpart. Source: `cmd_install` at `skills/guidefold/scripts/guidefold:8747`.

### 2. Sign in — this is the whole authentication step

```sh
guidefold login
```

Starts the device flow: the CLI prints a short code and this console's URL, exactly like
`gh auth login`/Claude Code's own device sign-in. Open the link, confirm the code shown there
matches the one the terminal printed, and approve — under **Organization › Integrations**, in
the "Device authorization" panel that appears when a pending code is in the URL (any signed-in
member can approve their own sign-in; approving does not require being an owner). The token this
stores goes to `$GUIDEFOLD_CREDENTIALS` or `~/.config/guidefold/credentials.json` (mode 0600),
never into the repo. Source: `cmd_login` at `skills/guidefold/scripts/guidefold:7727`.

**That token is now enough on its own for SEARCH and USE.** `resolve_search_config`
(`skills/guidefold/scripts/guidefold:2181`) tries `GUIDEFOLD_TOKEN`, then `search.token_file`/
`GUIDEFOLD_SEARCH_TOKEN_FILE`, then — last resort, added 2026-09-13 — the same credentials file
`login` just wrote (`_login_token`, `skills/guidefold/scripts/guidefold:2138`). Nothing is
copied, pasted, exported, or written by hand. The request also carries `X-Guidefold-Org`/
`X-Guidefold-Repo` so the server can resolve this personal token's org/repo (it is not bound to
one the way an installation token is, API-CONTRACT §2/§3) — `_search_extra_headers`.

One thing login does **not** supply: the SEARCH/USE **endpoint** itself. `search.url` (or
`GUIDEFOLD_SEARCH_URL`) still needs to be configured — normally by `guidefold init`/`install`,
not by hand — because `hook` reads that from the environment only (E1.5) and never parses
guidefold.yaml.

### 3. Check the setup

```sh
guidefold doctor
```

Diagnoses gcloud/ADC/roles, hook wiring, skill layout, index freshness, hosted-service
reachability and identity, and the installed adapter — and prints a fix for every failure. The
`search-token` check now names which of `GUIDEFOLD_TOKEN`/`token_file`/`guidefold login` is
actually supplying the bearer, instead of just "configured". Source: `cmd_doctor` at
`skills/guidefold/scripts/guidefold:6596`.

### 4. Fallback for CI or another script without a browser: an installation token

`guidefold login`'s device flow needs a human with a browser to approve the code. CI and any
other unattended, scripted run has none, so it keeps using an installation token instead — this
step is a fallback, not part of the default interactive flow above.

An owner clicks **Create an installation** in the Integrations tab (collapsed, under "CI or
another script without a browser: use an installation token"). It issues a token scoped to
`search`, `use` and `events`, shown exactly once. Save it to a file only the job can read, then
point the adapter at it:

```sh
printf '%s' "<paste the installation token>" > ~/.config/guidefold/search-token \
  && chmod 600 ~/.config/guidefold/search-token \
  && export GUIDEFOLD_SEARCH_TOKEN_FILE=~/.config/guidefold/search-token
```

This is `search.token_file`/`GUIDEFOLD_SEARCH_TOKEN_FILE` in `resolve_search_config`'s
precedence above — it is checked, and wins, **before** the stored login token, so an explicit
installation token always overrides a human's own sign-in on the same machine.

### 5. Telemetry — on automatically, once a credential and endpoint exist

Telemetry upload is **on by default** — owner decision 2026-09-13
([ADR-0047](adr/ADR-0047-telemetry-upload-on-by-default.md)), amending the earlier opt-in
reading of `docs/SEARCH-USE-TELEMETRY.md` §5 and `docs/DESIGN.md` R7. As soon as steps 2 (or 4)
have given the adapter a bearer credential and an endpoint, the next `find`/`hook`/`load` call
that emits telemetry triggers an upload automatically — nothing to run by hand, and
`guidefold telemetry flush` no longer needs to be scheduled in CI for the common case. The
trigger respects a per-repo minimum interval so a burst of hook calls starts at most one flush,
and always runs as a **separate, detached process** — the hook itself never opens a socket
(E1.5 is unaffected: `maybe_trigger_telemetry_auto_flush`/`_spawn_auto_flush`,
`skills/guidefold/scripts/guidefold:5786`). Before the first upload actually happens, one line
appears on stderr naming the exact command to turn it off; it does not repeat.

**Turn it off** — this is now the explicit step, for a person or an organisation that must not
upload telemetry:

```sh
guidefold telemetry disable    # persisted; survives across sessions/repos on this machine
```

For CI or one job only, without touching the persisted setting: `GUIDEFOLD_TELEMETRY=0`. To stop
local spooling entirely (a harder switch, wins over both): `GUIDEFOLD_TELEMETRY_DISABLE=1`. An
organisation that must not upload telemetry at all needs one of these set explicitly on every
developer machine and every CI job that runs the adapter — it is on by default, not off.

```sh
guidefold telemetry status     # ON/OFF, plus queued/produced/acknowledged/dropped per partition
guidefold telemetry enable     # turn it back on after a disable
```

CI, or anything that wants one manual, synchronous send instead of waiting for the automatic
trigger, still can:

```sh
guidefold telemetry flush [--url <api>]
```

`--url` defaults to whatever `search.url`/`GUIDEFOLD_SEARCH_URL` already resolves to, so it only
needs to be spelled out when that is not configured. `--token-file` overrides the default token
(the same file from step 4, or the login token from step 2). Source: `cmd_telemetry_flush` at
`skills/guidefold/scripts/guidefold:5624`, `_flush_token` at
`skills/guidefold/scripts/guidefold:5606`, `cmd_telemetry_enable`/`cmd_telemetry_disable` at
`skills/guidefold/scripts/guidefold:5536`/`5553`.

## What you will see once this works

Overview (`/home`) stops showing "No adapter installed" once sign-in and an endpoint are
configured, and stops showing "No telemetry in the last 30d" once telemetry has been enabled and
a harness call has run. Usage & quality then starts filling in as SEARCH/USE events and
assessments accumulate — a rate still needs a floor of 20 assessments before it is shown as a
percentage rather than a raw count.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `guidefold login`, `guidefold doctor` or `telemetry flush` fails with `401` | No token is configured yet, or a stored one was revoked | Run step 2 (`guidefold login`) again, or — for CI — recreate an installation token (step 4) |
| Adapter installed, signed in, but Usage shows no events | Telemetry was explicitly disabled (`guidefold telemetry disable` / `GUIDEFOLD_TELEMETRY=0` / `GUIDEFOLD_TELEMETRY_DISABLE`), or nothing has been sent yet | Run `guidefold telemetry status` to see which switch is off; `guidefold telemetry enable` to turn it back on — the next harness call triggers a flush automatically. To force one now: `guidefold telemetry flush` |
| An installation shows **Silent N d** | The adapter has not reported to this organization in N days | Confirm `guidefold telemetry status` reports upload ON, run `guidefold doctor`, and check the token/endpoint are still valid |
| `guidefold telemetry status` reports upload ON but nothing is arriving | No `search.url`/`GUIDEFOLD_SEARCH_URL` is configured, so the automatic trigger has nowhere to send to — it only checks, never dies loudly | Configure `search.url` (normally via `guidefold init`), or set `GUIDEFOLD_SEARCH_URL` |

## Adapter setup is separate from publishing an import

Installing and authenticating the adapter (steps 1-5 above) only lets SEARCH/USE reach this
organization and lets telemetry flow. It does not publish anything: an import's files are stored
once `guidefold import`/`guidefold sync` finishes, but nothing is served until a snapshot is
activated (publication). The two are independent — an adapter can be fully set up with nothing
published yet, and a publication does not itself install or authenticate an adapter.
