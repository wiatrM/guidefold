# M1: rule text applicable at a leaf of real monorepos

This is the committed copy of the write-up. `results.json`, `leaves/*.csv`, `measure.py` and the protocol live under `research/applicable-set-real-monorepos-2026-09-08/`, which is gitignored; the per-repository table below carries the commit ids needed to reproduce every row.

Status: completed. Date: 2026-09-08. Protocol: `PROTOCOL.md`, frozen before the first repository
was measured. No model calls, no cost. 40 of 40 candidate repositories measured
(0 failed to clone). Reproduce: `python3 measure.py` then `python3 make_readme.py`.

**Result, by the pre-registered rule: the truncation regime is common.** Across the ten selected
repositories, 53.7 percent of source directories (macro average) sit under a root-to-leaf chain
of rule files longer than 12,000 characters, the Windsurf default; 26.7 percent sit under more
than 32,768, the Codex default. The rule said over 30 percent means common. It is.

The same number computed the stricter way, counting only the single convention a given tool would
actually read (post hoc, see below), is 53.4 percent for the ten and 36.5 percent across all
40 measured repositories. 14 of 40 repositories have a majority of their
source directories over 12,000 characters under one convention; 3 have a majority over
32,768.

## What was measured

For every directory containing a source file, the characters of rule files a nearest-wins,
root-to-leaf concatenating tool would load there: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.cursorrules`, `.windsurfrules`, `.clinerules` in the directory and every ancestor, plus
`.github/copilot-instructions.md` at the root. Cursor `.mdc` rules with `alwaysApply` or a matching
glob are reported as a second column and are not in the headline. Sizes are characters of the
actual blobs, fetched in one batch per repository from blobless clones; nothing else was
downloaded. Skills (`.agents/skills`, `.claude/skills`) are counted but not added, because both
Codex and Claude Code list them by name and load bodies on demand.

## Aggregates

| Group | Measure | over 8,000 | over 12,000 | over 32,768 |
|---|---|---:|---:|---:|
| ten selected | all chain files summed (pre-registered), macro | 70.8 | 53.7 | 26.7 |
| ten selected | all chain files summed (pre-registered), pooled | 39.1 | 31.7 | 19.2 |
| ten selected | largest single convention (post hoc), macro | 70.7 | 53.4 | 26.7 |
| ten selected | largest single convention (post hoc), pooled | 39.1 | 31.3 | 19.2 |
| all 40 measured | all chain files summed (pre-registered), macro | 70.7 | 50.5 | 11.9 |
| all 40 measured | all chain files summed (pre-registered), pooled | 58.4 | 44.1 | 10.6 |
| all 40 measured | largest single convention (post hoc), macro | 59.4 | 36.5 | 9.4 |
| all 40 measured | largest single convention (post hoc), pooled | 53.8 | 37.5 | 10.1 |

Macro averages each repository equally; pooled weights by directory count, so it is dominated by
the repositories with tens of thousands of directories (kibana, next.js, posthog). Both are shown
because they disagree and a reader should see by how much.

## The post hoc correction that matters

The pre-registered chain sums every convention's files. A Codex user never sees `CLAUDE.md`, and
a Claude Code user never sees `AGENTS.md`. `34` of the measured repositories carry
`AGENTS.md` and `30` carry `CLAUDE.md`; where both exist, one is often a symlink to the
other (next.js's `CLAUDE.md` is nine characters: the path of `AGENTS.md`). The "largest single
convention" rows take, per directory, the biggest chain any one tool would read. On the ten
selected repositories the correction changes the headline by 0.3 points. Across
all 40 it changes it more, and the stricter number is the one to quote.

## Per repository

Sorted by chain-file count; the first ten with at least three chain files are the selection.
Shares are percentages of source directories.

| Repository | Commit | Leaves | Chain files | AGENTS.md | CLAUDE.md | Cursor rules | Skills | Median chain | Max chain | Leaves over 12,000 | over 32,768 | Single-convention over 12,000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PostHog/posthog | `5f6f41d` | 6,446 | 95 | 47 | 47 | 3 | 96 | 48,499 | 154,714 | 100.0 | 100.0 | 100.0 |
| mastra-ai/mastra | `e558ae7` | 2,200 | 30 | 25 | 5 | 2 | 21 | 2,212 | 9,751 | 0.0 | 0.0 | 0.0 |
| pydantic/pydantic-ai | `edcb123` | 60 | 26 | 15 | 10 | 0 | 11 | 22,151 | 40,004 | 100.0 | 31.7 | 100.0 |
| n8n-io/n8n | `6f5269a` | 5,197 | 25 | 14 | 11 | 0 | 22 | 21,961 | 38,758 | 100.0 | 1.5 | 100.0 |
| sst/opencode | `dff8fbc` | 562 | 18 | 18 | 0 | 0 | 0 | 8,748 | 33,396 | 28.6 | 2.5 | 28.6 |
| apache/airflow | `77cf38b` | 2,687 | 16 | 14 | 2 | 0 | 6 | 42,503 | 56,625 | 100.0 | 100.0 | 100.0 |
| twentyhq/twenty | `3af9f5d` | 6,170 | 16 | 8 | 8 | 16 | 1 | 4,830 | 14,154 | 2.8 | 0.0 | 0.0 |
| grafana/grafana | `e0b3069` | 2,471 | 14 | 13 | 1 | 0 | 3 | 9,968 | 42,105 | 5.4 | 0.2 | 5.4 |
| oven-sh/bun | `d745f03` | 803 | 14 | 5 | 9 | 0 | 8 | 25,139 | 59,235 | 100.0 | 31.5 | 100.0 |
| elastic/kibana | `ad7c76d` | 22,923 | 13 | 11 | 2 | 0 | 56 | 7,584 | 32,753 | 0.1 | 0.0 | 0.1 |
| ghostty-org/ghostty | `4480625` | 207 | 11 | 10 | 1 | 0 | 1 | 1,397 | 5,848 | 0.0 | 0.0 | 0.0 |
| cloudflare/workers-sdk | `dbf6aad` | 829 | 10 | 9 | 1 | 0 | 0 | 12,387 | 24,046 | 61.2 | 0.0 | 61.2 |
| microsoft/vscode | `68be8ad` | 2,440 | 10 | 9 | 0 | 0 | 4 | 11,752 | 79,734 | 3.6 | 3.1 | 3.5 |
| getsentry/sentry | `f1faa4a` | 2,467 | 9 | 5 | 4 | 0 | 27 | 14,285 | 14,941 | 99.4 | 0.0 | 99.4 |
| supabase/supabase | `41e6d48` | 1,923 | 9 | 4 | 4 | 0 | 22 | 14,468 | 24,228 | 100.0 | 0.0 | 43.8 |
| google-gemini/gemini-cli | `24cab68` | 157 | 8 | 0 | 0 | 0 | 0 | 6,075 | 7,580 | 0.0 | 0.0 | 0.0 |
| vercel/next.js | `662b035` | 10,815 | 8 | 5 | 3 | 0 | 20 | 31,045 | 33,593 | 100.0 | 0.1 | 100.0 |
| calcom/cal.com | `1251ba5` | 2,102 | 7 | 4 | 3 | 0 | 0 | 9,232 | 9,232 | 0.0 | 0.0 | 0.0 |
| block/goose | `13f4d26` | 237 | 5 | 2 | 2 | 0 | 1 | 9,924 | 10,625 | 0.0 | 0.0 | 0.0 |
| zed-industries/zed | `20d3cd1` | 499 | 5 | 3 | 1 | 0 | 4 | 18 | 11,743 | 0.0 | 0.0 | 0.0 |
| huggingface/transformers | `0a959de` | 1,150 | 4 | 2 | 1 | 0 | 0 | 3,555 | 3,555 | 0.0 | 0.0 | 0.0 |
| medusajs/medusa | `6cbc092` | 4,110 | 4 | 0 | 3 | 0 | 7 | 10,821 | 27,360 | 18.3 | 0.0 | 18.3 |
| nrwl/nx | `89f02c1` | 1,323 | 4 | 1 | 3 | 0 | 22 | 19,172 | 24,252 | 100.0 | 0.0 | 0.8 |
| payloadcms/payload | `2bdb79f` | 2,706 | 4 | 1 | 3 | 0 | 7 | 20,956 | 27,183 | 100.0 | 0.0 | 100.0 |
| directus/directus | `3df2ba9` | 721 | 3 | 1 | 1 | 0 | 0 | 14,117 | 14,205 | 100.0 | 0.0 | 0.0 |
| hyperdxio/hyperdx | `c8cc8e5` | 243 | 3 | 2 | 1 | 2 | 4 | 20,110 | 37,442 | 100.0 | 4.5 | 100.0 |
| remotion-dev/remotion | `53e4dd4` | 1,058 | 3 | 1 | 1 | 0 | 57 | 3,650 | 3,650 | 0.0 | 0.0 | 0.0 |
| vercel/ai | `36b3364` | 1,281 | 3 | 2 | 1 | 0 | 0 | 13,361 | 14,444 | 100.0 | 0.0 | 100.0 |
| denoland/deno | `336da42` | 2,561 | 2 | 0 | 1 | 0 | 6 | 24,331 | 24,331 | 100.0 | 0.0 | 0.0 |
| facebook/react | `6c0e104` | 393 | 2 | 0 | 2 | 0 | 14 | 359 | 10,692 | 0.0 | 0.0 | 0.0 |
| langchain-ai/langchain | `db613a9` | 473 | 2 | 1 | 1 | 0 | 0 | 39,012 | 39,012 | 100.0 | 100.0 | 100.0 |
| openai/codex | `6515a72` | 482 | 2 | 2 | 0 | 0 | 0 | 22,363 | 22,927 | 100.0 | 0.0 | 100.0 |
| openai/openai-agents-js | `78b67df` | 188 | 2 | 1 | 1 | 0 | 15 | 35,629 | 35,629 | 100.0 | 100.0 | 100.0 |
| prisma/prisma | `07580b3` | 1,176 | 2 | 1 | 1 | 0 | 0 | 11,058 | 11,058 | 0.0 | 0.0 | 0.0 |
| temporalio/temporal | `1458e58` | 508 | 2 | 1 | 0 | 1 | 1 | 18,785 | 18,785 | 100.0 | 0.0 | 0.0 |
| dagger/dagger | `6b3a9ff` | 3,513 | 1 | 1 | 0 | 0 | 0 | 0 | 6,428 | 0.0 | 0.0 | 0.0 |
| github/github-mcp-server | `6e00cee` | 47 | 1 | 0 | 0 | 0 | 0 | 12,872 | 12,872 | 100.0 | 0.0 | 0.0 |
| kubernetes/kubernetes | `79f041d` | 3,203 | 1 | 1 | 0 | 0 | 0 | 1,584 | 1,584 | 0.0 | 0.0 | 0.0 |
| langchain-ai/langchainjs | `56130de` | 495 | 1 | 1 | 0 | 0 | 0 | 11,697 | 11,697 | 0.0 | 0.0 | 0.0 |
| anthropics/claude-code | `ab9b2cf` | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 0.0 |

Failed to clone: none.

## Reading it honestly

- **It is bimodal.** 37 of 40 repositories are either under 10 percent or over 90
  percent. The chain is almost always one large root file, so every directory in the repository
  inherits it or none does. "How deep is the tree" matters less than "how long is the root
  AGENTS.md", and several projects keep a 20,000 to 50,000 character root file.
- **The Codex limit already bites on most directories in 3 repositories** (PostHog/posthog, apache/airflow, openai/openai-agents-js).
  In those a Codex user is silently losing the tail of the rules on every prompt today.
- **The selection is not GitHub.** Candidates were listed from memory of projects that publish
  rule files, then ranked by how many they have. This is the population the product addresses
  (platform teams that write rules) and it overstates the share for a random repository, which
  the all-40 rows and the near-zero repositories in the table make visible.
- **Bytes and characters.** Sizes are characters of decoded UTF-8; limits are stated by vendors
  in characters or KiB. The difference is under one percent for these files.
- **Cursor rules with globs** are matched against at most fifty source files per directory;
  directories with more files may undercount cursor text. This affects the second column only.
- **The 8,000 threshold** is an approximation of a listing cap, not a body cap, and is reported
  for scale only.

## What this changes

The first value proposition ("location-scoped tools concatenate until a limit and truncate") is
no longer an assumption. In repositories that use rule files, a third to a half of source
directories are over the Windsurf default under a single convention, and a quarter are over the
Codex default in the selected ten. The 2026-09-08 delivery run measured the wrong regime because
its synthetic tree spread filler wide instead of putting a 20 to 50 kilobyte file at the root,
which is what real repositories do. PROTOCOL-v2 in `../delivery-vs-concatenation-2026-09-08/`
should place filler to reproduce the per-repository distributions in `leaves/*.csv`, not a
median.

## Files

- `PROTOCOL.md`: frozen design, decision rule, candidate list.
- `measure.py`: clone, tree, batch blob fetch, per-directory chains.
- `results.json`: per-repository aggregates with commit ids. `results.pre-convention.json`: the
  first pass before the per-convention columns were added; identical headline numbers.
- `leaves/<owner>__<repo>.csv`: one row per source directory with chain, cursor and
  per-convention characters.
- `make_readme.py`: this file's generator.
