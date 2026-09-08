# Worktree integration, 2026-09-08

Status: integration prepared; CI and merge tracked in the integration pull request.
Purpose: owner-requested commit and integration of missing local work, preserving current main.
Inputs: local refs/worktrees, current origin/main and GitHub merged pull-request history.
Scope: consolidate missing changes; do not restore superseded implementations or cached datasets.

## Included

- Current product, research, pricing and marketing snapshot 9abc83d (22 files).
- README, demo, logo and reviewed architecture diagrams from PR #128.
- Previously untracked dev-only F5 tool, tools/eval/dev_enrich.py.
- Previously untracked vector-layout benchmark: compose.vector-benchmark.yaml, services/search/vector_layout_test.go and tools/search_service/vector_layout.py. This remains opt-in, not a default runtime change.
- Policy/BM25F conformance fixture source hashes regenerated using the repository's scripts after the CLI change. No baseline scores changed to accept a regression.

## Preserved rather than reapplied

GitHub's merged PR history covers the historical branches, including #44, #50, #54, #58, #60, #62, #64, #66, #70, #118, #120, #121 and #122. The vector-layout branch tip is an ancestor of the merged throughput branch; the extra optimization commits are already ancestors of the native-service branch.

Three worktree indexes exactly match older recorded commits: gf-k8s = 23396f9, gf-serve = fd22575, gf-throughput = 790bbec. Their apparent deletions are not applied to current main.

The old gf-f6 implementation differs from the newer, tested tools/eval/dev_sibling.py on main. It and its tools/sibling files remain in the original worktree, not activated or substituted. Large enrichment/vector caches and partial evaluation outputs remain local, as do generated consumer files and Windows metadata. No worktree or branch was deleted.

## Checks

- 55 routing tests passed, including nearest-wins, policy, candidate generation, scoring, selection, composer and independent BM25 reference tests.
- A separate selection of nearest-wins, F6, enrichment and portal tests passed (40 tests).
- CLI and new Python tools compiled; dev_enrich.py --help succeeded.
- Regenerated 144 policy cases and 54 BM25F cases with the provided generators.
- Full Windows pytest collection stops on the existing signal.SIGKILL usage in test_service_encoder_worker.py. Linux CI is required; this is not a full-suite pass.
- No model, corpus or GPU benchmark was executed. Their performance and quality are not newly measured here.

Environment: Windows Python 3.12 in an isolated test virtualenv; repository files on WSL storage.
