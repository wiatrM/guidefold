# Landing v2: what we sell (owner brief, 2026-09-11)

Owner instruction: **show real value at first sight.** The page sells three things, in this order,
plus the supporting pillars below. Every section must map to one of them.

## 1. Extraction: knowledge moves up the hierarchy

Teams write rules next to their code. Guidefold, in CI or from the CLI, extracts the reusable part
and promotes it one level up (service → team → organisation). The whole organisation gets
general-level knowledge as a by-product of ordinary team work. Nobody writes the company handbook;
it condenses out of the repos.

## 2. Retrieval: intelligent, real time, at 30k skills

We handle a very large number of skills (30k order of magnitude). The service ranks by task and by
place in the repo and hands the agent at most a few cards, in real time. Evidence from the Pi
harness (branch `codex/e2-proof-gate-matrix-20260910`, worker + HTTP USE 1.2, 2026-09-10/11):

| Claim | Evidence | Status label to use |
|---|---|---|
| Sources delivered with proof | 4/4 sources published, 4/4 LOAD answers, 4/4 `source_proof_complete`; hash and source range checked by the service | integrity, verified |
| No harmful delivery | E2: 0/76 unsafe deliveries; Wilson upper bound 4.81% | safety, verified |
| Hierarchical SEARCH on a running service | 25/25 requests, no 422 after bridge fix | integration, verified |
| Task replay E6.7 | 17/20 candidate vs 16/20 flat baseline, 20 frozen tasks, 3 teams; all safe cases ended in ASK | **feasibility only, inconclusive** |
| Existing retrieval research | +8.53 pp Recall@10 on SRA-Bench (see ui/src/data/research-evidence.json, dated) | measured |

Rules for using these: cite exactly, with the date and the status label. "Feasibility" and
"inconclusive" results may not be presented as proof of task-level value. Never round 0/76 into
"zero risk"; say what was measured.

## 3. Telemetry, tuning and promotion with organisation gates

The organisation view shows, per team: Task success, Safety boundary (ASK count, harness errors),
SEARCH → USE funnel, Cost and time (tokens, tool calls, mean time), ASK reasons from a safe
vocabulary ("Conflicting rules", "Missing dependencies", "Revision changed"). Missing data is
Unknown, never zero. Owners tune what gets promoted and gate promotion with organisation rules.

## Supporting pillars (what else we sell)

4. **Proof-gated delivery.** A rule reaches the agent only with a source proof (hash, revision,
   scope). Conflicting, stale or unproven rules become an ASK, never a silent load and never a
   silent fallback. This is the safety boundary buyers ask about first.
5. **Review before merge.** Every pull request that touches a rule gets a report: what changed,
   what collides, what an agent would now see.
6. **Harness-agnostic, Git-native.** Claude Code, Codex, Copilot, Gemini CLI. Git is the source of
   truth; the registry is a build artifact. No vendor lock, no hand-edited registry.
7. **Fewer tokens per task.** At most four short cards, general first, full text loaded on demand.
   Cost and time are measured, not promised.
8. **Provenance and audit.** Every delivery is traceable: which rule, which revision, which proof,
   which decision (LOAD or ASK, and why).
9. **Scale envelope.** Corpora of 1k / 10k / 30k skills, cold and warm cache, p50/p95 latency
   are part of the validation plan (Q6). Present as "designed for", not as a measured number,
   until the run exists.
10. **Open source today, hosted planned.** The CLI and retrieval service are public; the waitlist
    is for hosted availability.

## Structure implication

Hero must show the value at first sight: the pyramid mechanic (rules condensing upward) and the
retrieval promise (the right few rules, proven, in real time) in one glance, with the proof numbers
visible above the fold. Do not open with a category label; open with the outcome.

## Tone (owner, 2026-09-11)

Sales-driven and colourful. Brag hard about the positives; do not lie or invent numbers. Results that are still incomplete get only a light qualifier in adjacent microcopy or a footnote, never a hedge in a headline or subline.
