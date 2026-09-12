# HOWTO: install and run the adapter

Status: how-to, 2026-09-12. Written after an owner asked "what is an adapter? did you write a
HOWTO how to install both?" on seeing "No adapter installed" and "No telemetry in the last 30d"
on Overview. This is the reference version of the same five steps shown in the console
(Organization → Integrations → "Set up an adapter"), plus troubleshooting. Every command below
is quoted verbatim from `skills/guidefold/scripts/guidefold` — its usage block and the
`cmd_install`, `cmd_login`, `cmd_doctor`, `cmd_telemetry_flush` functions and their argparse
definitions. If a flag is not in that file, it is not a real flag; do not invent one.

## What is an adapter?

The adapter is the consumer-side harness integration: the `skills/guidefold/` package this repo
ships, copied into a consumer repo at `.agents/skills/guidefold/`. It has two parts:

- **Hook templates** (`skills/guidefold/hooks/*.json`) that wire a harness (Claude Code, Copilot
  CLI, Codex, Gemini CLI) to call the CLI automatically.
- **A single-file CLI** (`skills/guidefold/scripts/guidefold`) that performs SEARCH/USE against
  this hosted service with an installation token, and queues telemetry events that
  `guidefold telemetry flush` posts to `/v1/events:batch`.

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
subcommand takes today (`skills/guidefold/scripts/guidefold:8038` `INSTALL_HARNESSES = ("claude",
"copilot", "gemini")`, wired at `:9584`-`:9585`). `install` is idempotent and has an `uninstall`
counterpart. Source: `cmd_install` at `skills/guidefold/scripts/guidefold:8241`.

### 2. Sign in

```sh
guidefold login
```

Starts a device flow: the CLI prints a link and a code. Open the link and approve the code
under **Organization › Integrations** here — an owner approves it from the "Device
authorization" panel that appears when a pending code is in the URL. The token this stores goes
to `$GUIDEFOLD_CREDENTIALS` or `~/.config/guidefold/credentials.json` (mode 0600), never into the
repo. Source: `cmd_login` at `skills/guidefold/scripts/guidefold:7222`, subcommand at `:9537`.

### 3. Create an installation, then store its token

An owner clicks **Create an installation** in this tab. It issues a token scoped to `search`,
`use` and `events`, shown exactly once. Save it to a file only you can read, then point the
adapter at it:

```sh
printf '%s' "<paste the installation token>" > ~/.config/guidefold/search-token \
  && chmod 600 ~/.config/guidefold/search-token \
  && export GUIDEFOLD_SEARCH_TOKEN_FILE=~/.config/guidefold/search-token
```

The CLI reads the bearer token from `$GUIDEFOLD_TOKEN`, or from a file named by
`$GUIDEFOLD_SEARCH_TOKEN_FILE`, or from `search.token_file` in `guidefold.yaml` — in that order
(`resolve_search_config` at `skills/guidefold/scripts/guidefold:2138`; the env var is read at
`:2134`-`:2135`, the yaml field at `:2168`-`:2171`). This is the one credential SEARCH, USE and
`telemetry flush` all use — never guidefold.yaml directly, never logged.

### 4. Check the setup

```sh
guidefold doctor
```

Diagnoses gcloud/ADC/roles, hook wiring, skill layout, index freshness, hosted-service
reachability and identity, and the installed adapter — and prints a fix for every failure.
Source: `cmd_doctor` at `skills/guidefold/scripts/guidefold:6161`, subcommand at `:9505`.

### 5. Send telemetry

```sh
guidefold telemetry flush --url <api>
```

Posts queued SEARCH/USE events to `/v1/events:batch`, in batches, one tenant/environment
partition at a time. `--url` is required; `--token-file` overrides the default token (the same
`search.token_file` / `GUIDEFOLD_SEARCH_TOKEN_FILE` from step 3). This is never called from the
hook — run it by hand or from CI. Source: `cmd_telemetry_flush` at
`skills/guidefold/scripts/guidefold:5382`, `_flush_token` at `:5365`, subcommand at
`:9507`/`:9511`-`:9514`.

## What you will see once this works

Overview (`/home`) stops showing "No adapter installed" once an installation exists, and stops
showing "No telemetry in the last 30d" once a flush has posted events. Usage & quality then
starts filling in as SEARCH/USE events and assessments accumulate — a rate still needs a floor of
20 assessments before it is shown as a percentage rather than a raw count.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `guidefold login`, `guidefold doctor` or `telemetry flush` fails with `401` | The stored token's scopes don't cover the call, or it was revoked | Create a new installation with scopes `search`, `use`, `events`, then repeat step 3 |
| Adapter installed, but Usage shows no events | `guidefold telemetry flush` has not been run | Run step 5 by hand, or schedule it in CI; it is never triggered by the hook |
| An installation shows **Silent N d** | The adapter has not reported to this organization in N days | Confirm the token file/env var is still valid and reachable, then run `guidefold doctor` and `guidefold telemetry flush --url <api>` again |

## Adapter setup is separate from publishing an import

Installing and authenticating the adapter (steps 1-5 above) only lets SEARCH/USE reach this
organization and lets telemetry flow. It does not publish anything: an import's files are stored
once `guidefold import`/`guidefold sync` finishes, but nothing is served until a snapshot is
activated (publication). The two are independent — an adapter can be fully set up with nothing
published yet, and a publication does not itself install or authenticate an adapter.
