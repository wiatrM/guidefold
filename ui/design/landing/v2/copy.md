# Guidefold landing page, v2 copy

Rebuilt from zero on the owner verdict of 2026-09-09, reworked on the value brief of 2026-09-11
(`value-brief.md`), bound by the citation ruling of 2026-09-11, written in the sales tone the owner
directed on 2026-09-11, and rewritten again on the owner verdict of 2026-09-12: **too much scientific
babble, too few concrete use cases, screenshots and value; say what someone can do with this and why
they would use it.** Authority order: preservation contract (`preservationMap` in
`../design-brief.json`) → owner verdict of 2026-09-12 → value brief and citation ruling → `../DESIGN.md`
→ this file.

Spelling is British (`organisation`) to match the protected strings. There are no em dashes or en
dashes anywhere in the copy.

**The tone rule, stated once so every section obeys it.** Headlines and sublines are confident claims
phrased as outcomes. Qualifiers are real and never removed, but outside the evidence section they are
a plain sentence a platform lead reads once, usually just a date. The precise research labels live in
one place: section 7.

**The register rule, new in revision 3.** These words and phrases do not appear in body copy,
headlines, captions or microcopy anywhere on the page except inside section 7: *Wilson*, *one-sided*,
*upper bound*, *deterministic*, *source-backed*, *delivery boundary*, *harmful mutations*, *SRA-Bench*
as a headline word, *USE 1.2 HTTP handler*, *matrix*, `reason=source_proof_complete`. The numbers
themselves stay everywhere they earned their place, written as sentences. Section 7 keeps every
precise label verbatim, in small print, beside a link to the file the numbers come from.

The `?confirm=` and `?unsubscribe=` branch renders the `EmailAction` view **instead of** all marketing
sections below. That branch and its strings are protected and unchanged.

---

## 1. Positioning

**Category (one sentence).**
Guidefold keeps a monorepo's rules in Git next to the code they govern, promotes the reusable ones up
the hierarchy, and hands a coding agent only the few that apply where it is working, each with a link
to the file it came from.

**The enemy (the status quo pain).**
The knowledge that would answer this task exists, written down, in a directory nobody on this task has
opened. It stays there because it was written for one service and never generalised, while the agent's
context fills with rules from teams the developer has never worked in. Every extra coding tool adds
another copy of the same instruction to keep in sync.

**The promise.**
Ordinary team work produces organisation knowledge as a by-product, and an agent standing in
`platforms/atlas/identity/turnstile/` receives the handful of rules that apply *there*, in whichever
coding tool the developer chose, with a link to where each one came from.

**Who this page is written for.** The platform lead of an organisation running several coding tools
over one monorepo (`docs/PRODUCT-FOCUS.md`, "The customer"), plus the tech lead who reviews rule
changes and the developer who receives them. Those three are the three scenes in section 2.

**Three proof points.**

| # | Proof | Exact citation and label | Where it appears |
|---|---|---|---|
| 1 | Nothing reaches an agent unproven | ASK for all 76 harmful mutations, LOAD for all 4 safe cases; the flat control loaded all 76. One-sided Wilson 95% upper bound for harmful delivery 4.81%. Label: **delivery boundary, deterministic, source-backed; not a task-success claim.** 2026-09-11. | Section 6 as a plain sentence with its date; full label only in section 7 |
| 2 | The safe case survives the real delivery path | The same 4/4 safe targets passed through the production USE 1.2 HTTP handler with `reason=source_proof_complete`, and the service verified the cited source hash and range. Same label, same date. | Section 7 only |
| 3 | The hierarchy improves retrieval | +8.53 pp Recall@10 on SRA-Bench, 5,400 queries over 26,262 skills. **Measured**, exploratory offline retrieval. `ui/src/data/research-evidence.json`, 10 September 2026. | Hero proof strip as a plain sentence; section 7 with the full label |

**Source verification, rechecked 2026-09-12 in this working tree.**

| Figure | Source | State |
|---|---|---|
| +8.53 pp Recall@10, 5,400 queries, 26,262 skills | `ui/src/data/research-evidence.json`, with per-artefact SHA-256 in its `sources` block | Verified here. Rendered from the file at runtime. |
| 76 harmful rules answered ASK, 4 safe cases answered LOAD, flat control loaded all 76, Wilson 95% upper bound 4.81% | `ui/src/data/research-evidence.json` → `proof_gate.matrix`, mirrored from `docs/RESEARCH.md` §5.30, 2026-09-11, reproducible from `research/e2-source-backed-20260911/README.md` | Present in the JSON in this tree, with `source` and `reproduce` paths. Verified 2026-09-12. |
| 4/4 through the production USE 1.2 HTTP handler, `reason=source_proof_complete`, service-verified hash and range | `ui/src/data/research-evidence.json` → `proof_gate.http_path`, mirrored from `docs/RESEARCH.md` §5.32 | Same. Verified 2026-09-12. |
| E6.7 replay 17/20 vs 16/20 · 25/25 hierarchical SEARCH · any 30k latency figure | Ruled not citable, 2026-09-11 | **Must not appear on the page in any form, including a softened one.** Unchanged by the owner's deletion of the Q6 sentence: he cut a piece of copy, not the ruling. |

**The one label, and where it now lives.** Revision 2 of this file required the full label
*delivery boundary, deterministic, source-backed; not a task-success claim* in the microcopy beside
both proof-gate figures. The owner verdict of 2026-09-12 removes that register from the body of the
page, and the verdict outranks this file. So: the label survives **verbatim and complete** in section
7's small print and in the `proof_gate.microcopy` field that `ResearchEvidence.tsx` renders, and
section 6 carries the same limit as a plain sentence a reader understands on first pass, with the date.
Nothing is softened; it is relocated and re-said in English. The older synthetic fixture report
(`docs/reports/bakeoff/E2-PROOF-GATE-MATRIX-2026-09-10.md`, 2 safe loads and 6 abstentions) is a
different and earlier run; its counts are not blended with these.

**Figures the page must not produce.** No aggregate "zero risk" from 76 of 76. No latency number for
the 30k corpus. No `+8.53 pp` without its exploratory qualifier somewhere on the same screen. No
revival of an excluded figure in a softer form. No helped-rate or task-success percentage anywhere:
`docs/PRODUCT-FOCUS.md` records telemetry as built but never run on a real developer's data.

**The emotion the page should leave: recognition, turning into confidence.**
A platform lead should recognise their own Tuesday in section 2, see the actual application while they
read it, and reach the evidence section already believing the page. The page brags, and every brag is
either a screenshot of the real product or a number someone can go and reproduce.

---

## 2. Page structure

Ten sections. Section 2 is a chapter of three scenes and is the second thing on the page, because the
verdict was that the page explained before it showed. Header and footer are microcopy (section 5 of
this document), not funnel sections.

### Section 1. Hero

- **Purpose:** show the outcome and one number, then get out of the way.
- **Must believe after it:** "Rules climb out of the repos, the agent gets four, and there is a real product below this."

**Headline** (6 words)

> Your repos are already writing the handbook.

**Subline** (17 words)

> Guidefold promotes what generalises, then hands your agent the four rules that apply, each linked to its source.

**Body** (2 sentences)

> Rules stay in Git, next to the code they govern. The agent gets the few that apply where it is working, each linked to the file and commit it came from.

**Proof strip** (two items above the fold, each one plain sentence plus a date)

> **76 of 76 poisoned rules were refused.**
> The flat baseline loaded every one. Measured 11 September 2026.
>
> **+8.53 pp Recall@10 against flat search.**
> Offline retrieval benchmark, exploratory. 10 September 2026.

**CTA, primary**

> Join the waitlist

**CTA, secondary** (protected control, must stay visible in the hero)

> Play demo

**Trust line, under the actions**

> Open source today. The hosted service is planned.

**Text link, to section 2**

> See what three people do with it

*No eyebrow. The headline is present continuous on purpose: promotion is a diff an owner approves, and
PRODUCT-PIVOT §2 is explicit that Guidefold does not improve knowledge on its own. The hero body no
longer says "designed for a 30k-skill corpus"; the owner deleted the sentence that carried that
envelope, and the corpus size now appears only in section 5 where it is the reason the product exists.*

*Proof-strip rule for the implementer: the figure is the headline weight, the sentence beneath it is
one line of microcopy, and it renders at every breakpoint. An item that cannot fit its sentence is
dropped whole. Both items stack at 720px and both stay above the fold.*

---

### Section 2. Who uses it and for what

- **Purpose:** answer the owner's question directly. What can someone do with this, and why would they use it.
- **Must believe after it:** "I know which person on my team opens this, on which day, and what they get."
- **Layout:** three scenes, each one paired with a screenshot of the real application. Text column and screen alternate sides. Each scene is a person, a moment, what they do, and what they walk away with. No scene carries a figure that is not one of the five citable numbers.

**Chapter headline** (5 words)

> Who uses it and for what

**Chapter subline** (16 words)

> A platform lead, a tech lead and a developer, each with a different reason to open it.

---

#### Scene A. Platform lead (U1 and U5)

**Headline** (7 words)

> Every coding agent onboarded in an afternoon.

**Scene** (3 sentences)

> Dana runs the platform team: forty services, four coding tools, and an instruction file per tool that nobody has updated since March. On Tuesday afternoon she points the CLI at the monorepo and the import lands: every rule file with its path and hash, every skipped file with its reason. By evening Claude Code, Codex, Copilot and Gemini CLI all read the same library.

**Outcome line** (1 sentence, set apart)

> One library, four coding tools, no per-tool copy to keep in sync.

**Paired screen:** **Import**, route `/import?org=<slug>&repo=<id>`. See screen S1 in section 7a.

**Caption under the screen**

> Import: every file the scan found, with its path and hash, and every file it skipped with the reason. Meridian fixture, not a live run.

*Constraint: the scene names the adapter, the caption does not. Adapter installation lives in the
Organization view's Integrations tab, and the Import screen must not be captioned as if it set up a
harness.*

---

#### Scene B. Tech lead (U7 and U9)

**Headline** (6 words)

> See what collides before you merge.

**Scene** (3 sentences)

> Priya reviews a pull request that rewrites the identity team's deployment rule. The report is already on the PR: what changed, what it now collides with, what an agent would see after the merge. She opens Proposals, reads the source beside the candidate, and records the decision against a revision.

**Outcome line**

> The contradiction is caught in review, not in an incident.

**Paired screen:** **Proposals**, route `/proposals?org=<slug>&repo=<id>&proposal=<id>`. See screen S2
in section 7a.

**Caption under the screen**

> Proposals: the source file beside the candidate rule, with the decision recorded against a named revision. Meridian fixture, not a live run.

*Constraint, checked against the code on 2026-09-12: the pre-merge report is produced by
`guidefold report --base <ref>` in CI, not by a hosted view. There is no collision report screen in
`ui/src`. The scene may say the report arrives on the PR; the caption must not call the Proposals view
a collision report. Structural problems block the report, probable collisions only warn
(`_report_trigger_collisions`), so no copy says the merge was blocked by a collision.*

---

#### Scene C. Developer (U8 and U6)

**Headline** (7 words)

> Four rules arrive. You see which helped.

**Scene** (3 sentences)

> Marek opens Claude Code in `platforms/atlas/identity/turnstile/`, a module he has never touched. Four cards arrive instead of the whole handbook: the general identity rules, then the local one that sharpens them, each linked to its source file and commit. He ships without asking anyone which of the three deploy procedures is current.

**Outcome line**

> The developer stops guessing. The rule owner sees the same delivery from the other side.

**Paired screen:** **Usage & quality**, route `/usage?org=<slug>&repo=<id>`. See screen S3 in
section 7a.

**Caption under the screen**

> Usage and quality: what was delivered, what is queued for review, and Unknown wherever there is no observation yet. Meridian fixture, not a live run.

*Constraint: no helped-rate, no success percentage and no adoption count in this scene. The product
renders `helped_ratio: null` as Unknown and shows counts rather than a percentage on a small sample,
and `docs/PRODUCT-FOCUS.md` records the telemetry as never yet run on a real developer's data. "Which
ones helped" on the page means the review queue and the named observations, which is what the view
actually shows. The card count stays "four", matching the hero, and is never raised.*

---

### Section 3. Extraction

- **Purpose:** make the hero headline literal in one sentence, then show it once.
- **Must believe after it:** "Organisation-level knowledge will accumulate here without anyone being assigned to write it."

**Eyebrow**

> Where the rules come from

**Headline** (6 words)

> One team's fix becomes everyone's rule.

**Subline** (17 words)

> Guidefold finds the reusable part of a service rule, promotes it a level, and shows an owner the diff.

**Body** (2 sentences)

> Service, then team, then organisation. The handbook nobody had time to write assembles itself out of work your teams already did, one reviewed diff at a time.

**Microcopy, beneath the body**

> Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.

**CTA:** none. This section ends into retrieval.

*This chapter is unchanged, on the owner's instruction of 2026-09-12: little text, big value, keep it
exactly as it is. It is the one chapter exempt from the "what you get, then one example" re-expression
that revision 3 applies to retrieval, the proof gate and telemetry, and it is the density target every
other chapter was cut to. Roughly 75 words of page copy across four blocks. If the implemented page
renders the Meridian fixture instrument beside this chapter rather than beside retrieval, it stays
where the implementation has it and the protected-string row follows the implementation; the label and
the excerpt are unchanged either way.*

---

### Section 4. Retrieval

- **Purpose:** turn 30,000 rules from a liability into the reason the product exists.
- **Must believe after it:** "Selection happens on every prompt, in a place I control, and I can read the code."

**Eyebrow**

> What the agent gets

**Headline** (7 words)

> Thirty thousand rules. Four reach the agent.

**What you get** (1 plain sentence)

> You get four short cards instead of a filing cabinet, chosen by the task and by where in the repository the agent is standing, on every prompt.

**The example** (1 concrete case)

> An agent in `platforms/atlas/identity/turnstile/` gets the organisation's authentication rules, the identity team's rule that narrows them, and the one rule that belongs to that module. The payments team's rules do not arrive.

**Microcopy, beneath**

> General cards first, then the local rule that sharpens them. Full text loads only when the agent asks for it.

**CTA**

> Try the open-source version

**Supporting elements kept in this section** (layout, not copy): `IntroFigure` and `InstructionReader`
with its protected Meridian fixture label, and the `#quickstart` text link.

*The sentence "Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and
is not claimed here." is deleted here at the owner's instruction. The citation ruling that forbids any
30k latency figure stands untouched: no latency number appears anywhere on the page, and the scale
envelope is stated once, plainly, in section 7.*

---

### Section 5. The proof gate

- **Purpose:** answer the question a platform buyer asks first, with the best number on the page, in English.
- **Must believe after it:** "A bad rule fails loudly here. Everywhere else it would have shipped."

**Eyebrow**

> When a rule cannot prove itself

**Headline** (6 words)

> Seventy-six harmful rules. Seventy-six refusals.

**What you get** (1 plain sentence)

> You get an agent that refuses a rule it cannot trace: nothing is delivered without its file hash, revision and scope, and anything conflicting, stale or out of scope comes back as a question.

**The example** (1 concrete case)

> We poisoned 76 rules in a test corpus and asked for them. Guidefold refused all 76; the flat baseline loaded every one. The four clean rules in the same run were delivered, source checked. Measured 11 September 2026.

**Microcopy, beneath**

> A refusal names its reason. Conflicting rules, missing dependency, revision changed. Precise labels and the interval are in the evidence below.

**CTA:** none.

*Wording constraint: the brag is the comparison, which is why the flat baseline is named in the
example. It is never written as "zero risk", "no unsafe deliveries ever" or "100% safe". The Wilson
interval is not dropped; it moves to section 7 with the full label, where it is read once.*

---

### Section 6. Telemetry and promotion

- **Purpose:** show the buyer the surface they will sit in front of, as control rather than a dashboard.
- **Must believe after it:** "I will know which rule failed, why, and I decide what gets promoted."

**Eyebrow**

> For the organisation

**Headline** (7 words)

> You see which rule failed, and why.

**What you get** (1 plain sentence)

> You get a per-team view of what was delivered, what came back as a question and why, so a rule that is not working becomes a row you can act on rather than a hunch.

**The example** (1 concrete case)

> The identity team's setup rule comes back as "Revision changed" nine times in a week. It lands at the top of the review queue with the revision that broke it, and the fix is a rule edit rather than a support thread.

**Microcopy, beneath**

> Missing data reads Unknown, never zero. A delivered rule is not a rule that helped, and the view keeps those separate.

**CTA:** none.

---

### Section 7. The evidence, in full

- **Purpose:** one place where every precise label, interval and limitation lives, so the rest of the page can speak English.
- **Must believe after it:** "They publish the intervals and the regressions, so the rest of the page is literal too."
- **This is the only section where the research register is allowed.**

**Eyebrow** (already rendered by `ResearchEvidence.tsx`)

> Research update · 10 September 2026

**Headline** (7 words)

> Plus 8.53 points of recall over flat.

**Subline** (13 words)

> 5,400 queries across 26,262 skills on SRA-Bench, against flat dense search.

**Small print, directly beneath the figure** (verbatim, every label kept)

> Measured, exploratory offline retrieval, not completed coding tasks. Four of six datasets improved; CHAMP and TheoremQA regressed. The hierarchy came from benchmark corpus prefixes rather than real repository scopes.

**Second block, the delivery result with its full label** (small print, verbatim)

> ASK for all 76 harmful mutations, LOAD for all 4 safe cases. One-sided Wilson 95% upper bound for harmful delivery: 4.81%. The same 4 safe targets came through the production USE 1.2 HTTP handler with `reason=source_proof_complete`, source hash and range verified by the service. Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.

**Third block, what is still open**

> Task-level value is not settled. The result above says a rule was delivered or refused correctly; it says nothing about whether a delivered rule helped somebody finish the work. That measurement needs real repository snapshots and frozen tasks, and we have not made it yet.

**Fourth block, the scale envelope** (one plain sentence, no figure)

> Corpora of 1k, 10k and 30k skills, cold and warm cache, are in the Q6 validation plan. No latency figure appears on this page until that run exists.

**CTA** (both existing, both kept)

> Read the evidence
> Download results and source hashes

**Binding constraint for the implementer:** the chart, the table, the interval paragraphs, the Pi trace
and the `<details>` method block inside `ResearchEvidence.tsx` stay as they are. This section's copy
sits above them and must not soften them. Values come from `ui/src/data/research-evidence.json` at
render time, never hard-coded into the markup. The `proof_gate.microcopy` string in that file is the
canonical full label and is not edited.

---

### Section 7a. Screens appendix (specification, not page copy)

Every screenshot on the page is a real view of the hosted UI in `ui/`. No mockup, no drawing, no
composite, no invented row. The anti-slop gate requires a visible fixture label on every example
object, so each caption ends with the Meridian fixture sentence.

**How the data gets there.** `ui/README.md` is explicit that the panel has one data source, the hosted
API: there is no `?mode=` parameter and no sample data in the bundle outside the component gallery.
"Fixture mode" therefore means **the real UI reading the real Go service, seeded from the Meridian
example monorepo**, captured locally:

```sh
export PATH=$HOME/.cache/guidefold/toolchain/go/bin:$PATH
python3 tools/dev/stack.py up --generator deterministic
python3 tools/dev/stack.py seed > seed.json        # dev login, org, repo, token, import
# publish the import; without it SEARCH does not answer
cd ui && pnpm dev                                   # http://127.0.0.1:4331
```

Take `org` and `repo` from `seed.json`. Capture with Playwright at a fixed device scale so text is
legible when the image is downscaled on the page. Do not retouch a screenshot, do not paste a row in,
and do not crop away an empty state to make a view look busier than the fixture is.

| # | Screen | Route | Data | Viewport | Must be visible | Caption |
|---|---|---|---|---|---|---|
| S1 | Import | `/import?org=<slug>&repo=<id>` | Seeded stack, Meridian import, terminal state | 1280 × 800, 2× DPR; 390 crop for mobile | The manifest rows with path, size and SHA-256; at least one `accepted` and one `omitted` row with its reason; the terminal import status | Import: every file the scan found, with its path and hash, and every file it skipped with the reason. Meridian fixture, not a live run. |
| S2 | Proposals | `/proposals?org=<slug>&repo=<id>&proposal=<id>` | Seeded stack, one seeded proposal open | 1280 × 800, 2× DPR; 390 crop | Source pane beside the candidate diff; the source path and commit; the decision control; the revision the decision is recorded against | Proposals: the source file beside the candidate rule, with the decision recorded against a named revision. Meridian fixture, not a live run. |
| S3 | Usage & quality | `/usage?org=<slug>&repo=<id>` | Seeded stack, after at least one seeded SEARCH and USE | 1280 × 800, 2× DPR; 390 crop | The "Needs review" queue at the top; at least one observation row with its revision; at least one cell reading Unknown | Usage and quality: what was delivered, what is queued for review, and Unknown wherever there is no observation yet. Meridian fixture, not a live run. |
| S4 | Library (alternate for scene A) | `/library?org=<slug>&repo=<id>` | Seeded stack | 1280 × 800, 2× DPR | The filter row with repo, scope, owner, layer and status; rows showing scope and revision | Library: every instruction in the monorepo, filtered by scope, owner and status. Meridian fixture, not a live run. |

**Rules that bind the implementer.**

1. S4 is used only if the seeded Import view renders too sparse to read. One screen per scene; the page never shows two screenshots for one scene.
2. Every screenshot has a text alternative that names the view, the object and what the reader should notice. A caption is not an `alt` attribute.
3. If a required element in the "must be visible" column is missing from the capture, the screen is not shipped. Neither the caption nor the scene is rewritten to match a weaker screenshot.
4. Screenshots are stored under `ui/public/` with the capture date and the seed commit recorded beside them, so a stale screen can be told from a current one.
5. No screenshot of the landing page itself, no browser chrome, no cursor, no fake notification.

---

### Section 8. Availability

- **Purpose:** convert scepticism into a clone, and separate what exists from what is planned.
- **Must believe after it:** "I can check every claim on this page myself, today, and nothing locks me to one vendor."

**Headline** (6 words)

> Clone it today. It is open.

**Body** (two protected statements, side by side, verbatim)

> **Open source today.** CLI and retrieval service.
>
> **Paid hosting is planned.** Sign up for availability updates.

**Supporting line** (1 sentence)

> Claude Code, Codex, Copilot and Gemini CLI read the same rules, Git stays the source of truth, and the registry is a build artifact you can rebuild.

**Links**

> Read the docs

*Only one "Try the open-source version" link survives in the body of the page, in section 4. The footer
keeps its own. The availability band's copy of it is removed.*

---

### Section 9. Waitlist

- **Purpose:** the single conversion on the page.
- **Must believe after it:** "One email, one address, and I can leave whenever I want."

**Headline** (5 words)

> Be first on hosted Guidefold.

**Subline** (9 words)

> One email when it is ready. Nothing else.

**Form:** every string protected and verbatim, including the signup note, label, placeholder, submit
label, loading label, consent text and honeypot label. See the checklist in section 4 of this document.

**CTA** (protected submit label)

> Join the waitlist

---

### Section 10. Before you join

- **Purpose:** absorb the four objections that would otherwise stop the signup.
- **Must believe after it:** "They answered the price and the privacy question without being asked twice."

**Headline** (3 words)

> Before you join

**Subline** (10 words)

> Price, availability, coding tools, and what happens to your email.

**Body:** none. The four protected question triggers and their protected answers follow, all panels
closed on load, with `#privacy` and `#question-2` still expanding on deep link.

---

## 2a. Revision 4, as built (2026-09-12)

This section records what the polish wave actually shipped. Where it disagrees with the ten-section
plan above, **this section is what is on the page**; nothing above it was reworded, only cut, merged
or moved. Controller ruling 12 of the polish brief is the authority.

**Seven sections, in DOM order, which is reading order and tab order.**

| # | `id` | Heading on the page | Built from |
|---|---|---|---|
| 1 | `hero` | Your coding agent doesn't know your team's rules. Now it does. | Section 1, with the ruling-13 headline and subline and the new product demo stage |
| 2 | `use-cases` | Who uses it and for what | Section 2, three scenes, cut to one scene line plus the outcome line each |
| 3 | `extraction` | One team's fix becomes everyone's rule. | Section 3, unchanged copy |
| 4 | `how-it-works` | Thirty thousand rules. Four reach the agent. | Section 4, instrument re-composed, Q6 sentence deleted |
| 5 | `proof` | Seventy-six harmful rules. Seventy-six refusals. | Sections 5, 6 and 7 merged into one block |
| 6 | `waitlist` | Clone it today. It is open. | Sections 8 and 9 merged into one band |
| 7 | `questions` | Before you join | Section 10, unchanged |

**Strings that moved, and where they went.**

| String | Was | Is |
|---|---|---|
| `Your repos are already writing the handbook.` | hero h1 | Retired from the page (ruling 13). Not reused as an eyebrow: the use-case chapter's own headline does that work. |
| `Guidefold promotes what generalises, then hands your agent the four rules that apply, each one proven.` | hero subline | Replaced by the ruling-13 subline. |
| `Ranking runs across the whole hierarchy in real time…` | hero body | Deleted with the hero body paragraph; both of its claims were already on the revision-3 removal list. |
| `Read the numbers and how we got them` | hero text link | Removed. The scroll cue now owns the one mid-page destination (`#use-cases`), and the proof block carries `Read the evidence`. |
| `How rules move up` / `Scroll to the extraction section` | hero scroll cue | `Who uses it and for what` / `Scroll to the use cases` / `#use-cases`, per section 5 of this document. |
| `You see which rule failed, and why.` | telemetry h2 | Proof block, as an h3 over the five category names. |
| `Missing data reads Unknown, never zero. A delivered rule is not a rule that helped, and the view keeps those separate.` | telemetry microcopy | Proof block, unchanged. |
| The three section-7 small-print blocks, verbatim | research chapter | Proof block, small print, verbatim, beside `Read the evidence` and `Download results and source hashes`. |
| `Open source today.` + `CLI and retrieval service.`, `Paid hosting is planned.` + `Sign up for availability updates.` | availability band | Waitlist band, moved as the same JSX nodes, not retyped. |
| `Be first on hosted Guidefold.` / `One email when it is ready. Nothing else.` | waitlist h2 and subline | Waitlist band, as the h3 and line over the form; `Clone it today. It is open.` is the band's h2. |

**Cut from the page with their sections** (the ruling shortens the page; it does not soften a claim):
the telemetry fixture table, the SRA-Bench results table, the six-dataset `<details>` block, the Pi
trace, and the evidence bento's four tiles. Every number in them is still published, unrounded, at
`/evidence/research-2026-09-10.json`, which the proof block links to and the end-to-end suite fetches.

**Screens appendix, as built.** Scene A pairs with **S4 Library**, not S1 Import. S1 requires "at
least one `accepted` and one `omitted` row with its reason" to be visible, and the capture of the
seeded Import view shows Accepted 10 / Omitted 0 / Failed 0. Rule 3 forbids rewriting a caption to
match a weaker screenshot, and S4 is the documented alternate for this scene, so the alternate ships
with its own caption verbatim. S2 Proposals and S3 Usage and quality are unchanged.

**Demo captions block** (new in revision 4; the hero's product demo, four beats, one numbered
sentence each). Owner instruction, 2026-09-12: *"far too undescriptive, very enigmatic for ordinary
users."* These sentences are the demo's explanation and are written for a reader who has never heard
of Guidefold. No research register, no product noun a stranger would have to learn.

**Stage title** (persistent, above the panel)

> What happens when a developer asks the agent for a change

**Step indicator** (with the live dot)

> Step 1 of 4 · Step 2 of 4 · Step 3 of 4 · Step 4 of 4

**Beat captions** (numbered, one sentence, under the panel)

> 1. Your team writes its rules next to the code they govern, as SKILL.md files in the repo.
> 2. A developer asks the coding agent to change something in the orders service.
> 3. Guidefold sees where they are working and sends the agent only the rules that apply there: four cards, not the whole handbook.
> 4. The agent opens the real rule file and follows it, and afterwards you can see which rule it used.

**Object tags on the stage** (each shown on the beat that introduces the object)

> the repo · a rule (SKILL.md) · the code they are working on · what the developer asked · the four rules the agent gets · rules from other teams: not sent · the rule, in full

*Everything the stage renders as product output is real: the tree is `examples/monorepo`'s layout, the
prompt and the four results are the stdout of `guidefold find "add a column to the orders table"` with
the scores stripped, and the two rule lines are steps 2 and 3 of that fixture's own
`.agents/skills/postgres-production/SKILL.md`. Beats hold 3.5 s, 3.5 s, 4 s and 5 s; under reduced
motion the stage renders beat 4 as a static composite and no timer runs.*

---

## 3. Section by section: what is removed and why

Rows above the rule are removals made in revision 3, on the owner verdict of 2026-09-12. Rows below it
are earlier removals, kept so no cut list is silently reopened.

| Removed | Where it was | Why |
|---|---|---|
| `Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.` | retrieval microcopy | Deleted by the owner, 2026-09-12. The envelope survives as one plain sentence in section 7; the ruling against any 30k latency figure is unchanged. |
| `Ranking runs across the whole hierarchy in real time, designed for a 30k-skill corpus.` | hero body | Same deletion, same sentence in a different place. The hero body now says what the reader gets. |
| The full label `delivery boundary, deterministic, source-backed; not a task-success claim` beside every figure in the hero and section 5 | hero proof strip, proof-gate section | The verdict names this register as the babble. Kept verbatim in section 7 and in `research-evidence.json`; the body says the same limit in English with the date. |
| `ASK for all 76 harmful mutations, LOAD for all 4 safe cases. One-sided Wilson 95% upper bound for harmful delivery: 4.81%.` as a body proof line | proof-gate section | Same register. The counts stay in the section as a sentence; the interval and the exact wording move to section 7. |
| `The same 4 safe targets came through the production USE 1.2 HTTP handler with reason=source_proof_complete` | proof-gate section | Reads as a commit message. Section 7 keeps it verbatim. |
| `+8.53 pp Recall@10 on SRA-Bench.` as the hero proof-strip wording | hero | The benchmark name in a headline-weight figure is jargon for the reader who has not reached section 7. The figure stays; the name moves to the subline in section 7. |
| `Every rule arrives with its source proof attached` | hero body | "Source proof" is our noun. Replaced with the link to the file and commit, which is what a reader can picture. |
| The `Read the numbers and how we got them` hero link as the only mid-page destination | hero | Replaced with `See what three people do with it`, pointing at section 2. The evidence link survives in the footer of section 7's own CTAs. |
| Two separate sections for telemetry and evidence carrying overlapping qualifiers | sections 5 and 6 of revision 2 | The qualifiers were said twice in two registers. One evidence section now carries all of them. |
| --- | --- | --- |
| `Instruction library for coding agents` | hero eyebrow | A category label, which the value brief forbids above the fold. |
| `Team rules. Right where agents work.` | h1 | True of every competitor in the PRODUCT-FOCUS matrix, and it names no outcome. |
| `Rules stay next to the code. Guidefold copies the reusable part up the organisation pyramid, then gives each agent the few rules it needs.` | hero lede | Three clauses doing one job, and "pyramid" is our internal noun. |
| `Why we built it` and its three paragraphs | WHY section | The heading was about us. |
| The three `dt`/`dd` mechanism beats, `RouteRule`, `ScopePyramid`, `View the integration diagram` | HOW | Five visual components in one section is the feature dump the first owner verdict named. |
| Whole `roles` array and the 3-up `RoleCard` grid | VALUE | `promise` and `detail` said the same thing twice per card. Section 2's three scenes replace it with people rather than role labels. |
| `25/25 hierarchical SEARCH requests, no 422 after the bridge fix` | section 3, first v2 draft | Ruled not citable on 2026-09-11. |
| `Task replay E6.7: 17/20 against 16/20` | section 6, first v2 draft | Ruled not citable on 2026-09-11. |
| `Scroll to see how it works` with a disagreeing `aria-label` | hero scroll cue | Visible label, accessible name and destination disagreed. Replaced in section 5 of this document. |

---

## 4. Protected strings checklist

Every row survives **verbatim**. Repositioning is allowed; rewording, re-punctuating and summarising
are not. Source of truth: `preservationMap` in `../design-brief.json`. Section numbers below are the
revision-3 numbers.

| Protected content | Where it lives in the new structure |
|---|---|
| Waitlist form: `Paid hosting is planned. Sign up for availability updates.`, `Your email`, `you@company.com`, `Join the waitlist`, `Saving…`, `Email me about hosted Guidefold. Unsubscribe anytime. Privacy`, honeypot `Website`, `maxLength` 254, `#waitlist-email` / `#waitlist-consent` / `#waitlist-error`, 12s abort | Section 9, unchanged component |
| Waitlist success state: `Check your inbox to confirm.`, `New signups receive one confirmation email. Repeat requests do not send another message. Already confirmed? You’re all set.`, `Missing the email? Contact hello@cloudfloo.io.` | Section 9, replaces the form in place and takes focus |
| Four error strings: `Too many attempts. Please try again in an hour.`, `Please check your email and consent, then try again.`, `This link is invalid or expired. Contact hello@cloudfloo.io for help.`, `We could not confirm the request. Please try again. Your input is still here.` | Section 9, `role="alert"`, typed email retained |
| Confirm and unsubscribe flow: `Confirm your email`, `Leave the waitlist`, `Confirm that you want updates about hosted Guidefold.`, `Stop receiving hosted Guidefold updates.`, `You’re on the hosted Guidefold waitlist. We’ll email you about availability.`, `You’ve been unsubscribed from the Guidefold waitlist.`, `Confirm email`, `Unsubscribe`, `Back to Guidefold` | `EmailAction` branch, rendered **instead of** sections 1 to 10; URL replaced with `/`; the hero video never mounts |
| FAQ trigger `Is Guidefold available now?` and its answer | Section 10, `#question-1`, closed on load |
| FAQ trigger `What will hosting cost?` and both pricing paragraphs, including $99 per organisation per month excluding taxes, the $9 of provider usage costs $10 prepaid budget, no unlimited AI allowance, Enterprise SSO not included, quotas specified before purchase | Section 10, `#question-2`, closed on load, deep link expands it. No figure rounded, restated, or lifted into a pricing card. |
| FAQ trigger `Which coding tools can I use?` and its answer, with the link to `#coding-harness-to-instruction-delivery` | Section 10, `#question-3` |
| FAQ trigger `How is my email used?` and all three paragraphs: the Resend sentence, the 30-day and 365-day deletion schedule, the deduplication-hash sentence, the YouTube paragraph, the `mailto:hello@cloudfloo.io` link | Section 10, `#privacy`, opened by the consent link and by the hash |
| `Open source today.` with `CLI and retrieval service.` | Section 8, left statement |
| `Paid hosting is planned.` with `Sign up for availability updates.` | Section 8, right statement **and** section 9 as the form's signup note. Both instances are required. |
| `Open-source tools. Hosted service planned.` | Footer bottom line |
| GitHub URLs: repository root, `#quickstart`, `#coding-harness-to-instruction-delivery`, the fixture `SKILL.md` blob URL | Header nav (`GitHub`), **section 4** text link (`#quickstart`), section 10 question 3, footer "Open source" group, `InstructionReader` "Open the original file" (blob URL) |
| `/docs/` | Header nav `Docs`, section 8 `Read the docs`, footer `Documentation` |
| The demo `e350wBr1W8c` as the **Play demo** action | Section 1, hero secondary control. `DemoDialog` mounts the `youtube-nocookie` iframe only while open and keeps the `Watch on YouTube` link inside. No YouTube request before opening. |
| Document title `Guidefold \| Team instructions for coding agents` | Route effect, unchanged |
| `Skip to content` | First focusable element, targets `#main` |
| Meridian fixture excerpt and its "not a live run" label | **Section 4**, `InstructionReader`; the four bullet lines and the fixture label unchanged. The same "not a live run" wording is reused in the three screenshot captions in section 2, which is consistency, not a second protected instance. |

**Not protected, despite the v1 copy file marking it so:** the FAQ section heading `Before you join`.
`preservationMap` protects the four triggers and answers, not the heading.

---

## 5. Microcopy

**Header nav** (unchanged labels). `How it works` points at `#extraction`, section 3, because the
mechanism begins there and the label has to agree with its destination. The hero link owns
`#use-cases`. Section 4 keeps `id="how-it-works"` so existing inbound links and the v1 anchor still
resolve.

> How it works · Docs · GitHub

**Header action**

> Join the waitlist

**Skip link** (protected)

> Skip to content

**Hero scroll cue.** Visible label, accessible name and destination must agree.

> Visible: `Who uses it and for what`
> `aria-label`: `Scroll to the use cases`
> `href`: `#use-cases`

**Button labels**

| Control | Label |
|---|---|
| Hero primary, header action, form submit | `Join the waitlist` (protected on the form) |
| Hero secondary | `Play demo` (protected) |
| Form submit, pending | `Saving…` (protected), with `disabled` and `aria-busy` |
| Intro figure | `Replay` |
| Dialog close | `Close` |
| FAQ row | the question text itself, with no added "Read more" |

**Text links**

> See what three people do with it (hero, to `#use-cases`)
> Try the open-source version (section 4, and the footer, and nowhere else)
> Read the docs (section 8)
> Read the evidence · Download results and source hashes (section 7)
> Open the original file (instruction reader, protected destination)

**Screenshot alternative text** (one per screen, written as what the reader should notice, never a
repeat of the caption)

| Screen | `alt` |
|---|---|
| S1 Import | Guidefold Import view listing imported files with their paths and hashes, and skipped files with the reason each was left out. |
| S2 Proposals | Guidefold Proposals view showing a source file on the left, the candidate rule on the right, and the decision recorded against a revision. |
| S3 Usage and quality | Guidefold Usage and quality view with a review queue at the top and observation rows below, some reading Unknown. |

**Footer tagline** (kept)

> Instructions that stay close to the code.

**Footer groups** (labels unchanged)

> Product: Play demo · Documentation · Sign in
> Open source: GitHub · Integrations · Quickstart
> Stay in touch: Join the waitlist · Email us · Privacy
> Bottom: Open-source tools. Hosted service planned. · Built by Cloudfloo

**Empty and degraded states.** Each names what is missing and what the reader can still do. None
apologises, and none invents a reason.

| State | Copy |
|---|---|
| Intro figure cannot decode the video | No copy. The poster renders alone in the same bordered panel with its caption, and the Replay button is not rendered. |
| Reduced motion or Save-Data | Same as above. The still composition is complete on its own. |
| A screenshot fails to load | The caption and the `alt` text remain and carry the scene on their own. No placeholder graphic, no retry button. |
| Research chart has not entered the viewport, or the lazy chunk fails | No copy and no spinner. The table below it already carries every value. |
| A proof-strip item cannot fit its sentence at a breakpoint | The whole item is dropped. A figure never renders without its date and its limit. |
| Waitlist submitted with an address already confirmed | The protected success state, unchanged. It already says `Already confirmed? You’re all set.` |
| Waitlist network failure or 12s abort | `We could not confirm the request. Please try again. Your input is still here.` (protected) |
| Demo dialog opened without network | The `Watch on YouTube` link inside the dialog stays visible and is the fallback. |

---

## 6. Anti-slop self-check

**Read-aloud test, revision 3.** Every line was read as if said to a colleague at their desk. Six
failed and were rewritten.

1. "Every rule arrives with its source proof attached" became "every one of them links back to the file
   and commit it came from". Nobody says "source proof attached" out loud.
2. "Delivery boundary, deterministic, source-backed; not a task-success claim" was removed from the hero
   and the proof-gate section. Read aloud it is four nouns in a row. It survives intact in section 7,
   where a reader who wants the exact label has asked for it.
3. "One-sided Wilson 95% upper bound for harmful delivery: 4.81%" under a headline was unsayable at a
   desk. The section now says what happened and names the date; the interval waits in section 7.
4. "The same 4 safe targets came through the production USE 1.2 HTTP handler" reads like a commit
   message. Same treatment.
5. "Designed for a 30k-skill corpus" was deleted by the owner and not replaced with a softer version.
6. "Guidefold promotes what generalises" survived, because it is exactly what a platform lead says.

**Earlier read-aloud fixes, still in force.** "Up the organisation pyramid" stays out. "Retrieval, not
concatenation" stays out as a negative parallelism. "Every other tool concatenates, then truncates"
stays out as a categorical vendor claim. "Zero unsafe deliveries" stays out in favour of the count and
the comparison. "Your repos already wrote the handbook" stays in the present continuous.

**Where the confidence comes from.** The tone directive is met with three scenes, three real screens
and five numbers, not adjectives. Every headline is either a count from the citable set or an outcome
the reader gets. No qualifier was weakened to achieve that; the precise ones were collected into
section 7 and re-said in plain English where they were, which is what the verdict asked for.

**Banned vocabulary.** The list in `docs/ui/UX.md` §6 was checked line by line against every string
above, and the repository's `check-slop.sh` hook was run against this file with no page-copy hit. The
revision-3 register list (Wilson, one-sided, upper bound, deterministic, source-backed,
delivery boundary, harmful mutations, SRA-Bench as a headline word, USE 1.2 HTTP handler, matrix,
`reason=source_proof_complete`) appears in page copy only in section 7, which is the one section where
it is allowed. Elsewhere in this file it appears only in specification that never renders: section 1's
citation tables, the removal log in section 3, the italic constraint notes, and this checklist. A
removal log has to quote what it removed.

**Structures checked and absent.**

- Em dashes and en dashes: zero. Hyphenated compounds are not em dashes.
- Rule of three: the three scenes are three distinct people drawn from three separate use cases in
  PRODUCT-PIVOT (U1/U5, U7/U9, U8/U6), the same way "service, then team, then organisation" is the
  hierarchy as implemented. Neither is a rhythm. Section 6's list has three ASK reasons because the
  vocabulary has those three; nothing was padded to reach three.
- Title case headings: none. All headings are sentence case.
- Copula avoidance ("serves as", "represents", "stands as"): none.
- Superficial `-ing` clauses ("ensuring...", "highlighting..."): none.
- Exclamation points, emoji, curly quotes in new copy: none. Curly apostrophes inside protected strings
  are preserved exactly, because they are protected.
- Uniform cadence: scene A runs a 7-word headline, then three sentences of 24, 33 and 15 words, then a
  12-word outcome. Section 5 runs 6, then 34, then 40. Read aloud, the rhythm varies.
- Density: the extraction chapter is the measure, on the owner's instruction of 2026-09-12. Its page
  copy is about 75 words across four blocks. Every scene and every mechanism chapter was cut toward
  that range; the extraction chapter itself was not touched.
- Invented people: Dana, Priya and Marek are named roles in a scene, not testimonials, customers or
  logos. No quotation marks, no job title at a named company, no claim that any of them exists.

**Competitor test.** Every headline was checked against the PRODUCT-FOCUS matrix. "One team's fix
becomes everyone's rule" is unsayable by anyone who does not promote a rule upward. "Thirty thousand
rules. Four reach the agent." is unsayable by anyone who concatenates or truncates. "Seventy-six
harmful rules. Seventy-six refusals." is unsayable by anyone who has not run that test. "Every coding
agent onboarded in an afternoon" is unsayable by any single-harness vendor.

**Fabrication check.** No customer, logo, testimonial, certification, adoption count or launch date is
asserted anywhere. Every measurement on the page is one of the five citable numbers, plus `at most
four` cards and the protected pricing figures inside the FAQ. No screenshot shows a real organisation's
data.

**Scene detail is not measurement.** The three scenes are illustrative composites. Forty services, four
coding tools, an instruction file last touched in March, and a rule that comes back nine times in a
week are scene detail, the way a worked example in documentation is: nothing on the page presents them
as observations, and none of them is attributed to a customer. Binding on the implementer: no quantity
inside a scene is rendered in figure styling, in a metric card, in a stat tile or in a chart. Figure
styling is reserved for the hero proof strip and section 7. If a scene number would read as a
measurement at any breakpoint, the number is cut, not restyled.

**Screenshot test.** With the wordmark removed, section 2's first scene and its Import screen name the
product's job in one pass: a monorepo, its rules, and four coding tools reading one library. An answer
of "some AI dashboard" would be a P1, and a page whose second section is three annotated screenshots
of a working application does not produce one.

---

## 7. Revision log

**2026-09-11, first v2 draft.** Rebuilt from zero on the owner verdict of 2026-09-09. Eight sections,
hero on outcome rather than category, role grid and WHY section removed.

**2026-09-11, value brief.** Reworked to nine sections, each mapped to one pillar of `value-brief.md`.
Proof strip added above the fold. Proof gate and telemetry became their own sections.

**2026-09-11, citation ruling.** Proof-gate figures cited with the full label; three figures removed
outright as not citable: 17/20 versus 16/20, 25/25 SEARCH requests, and any 30k latency number.

**2026-09-11, tone directive.** Rewritten to sell. Headlines became claims phrased as outcomes with the
strongest citable number placed where it lands.

**2026-09-12, revision 3: use cases, screens and plain English.** Written on the owner verdict of
2026-09-12 ("too much scientific babble and far too little showing concrete use cases, screenshots from
the application and value; what can someone do with this product and why would they use it"). Five
changes.

1. **A use-case chapter is now the second thing on the page.** Three scenes, each a named person, a
   moment, what they do in Guidefold and what they walk away with, each paired with a real screen of the
   hosted UI: platform lead with Import, tech lead with Proposals, developer with Usage and quality.
   Each scene is traced to its PRODUCT-PIVOT use cases (U1/U5, U7/U9, U8/U6).
2. **The research register was removed from the body.** Eleven named words and phrases now appear only
   in section 7 and in this file's own specification tables. The numbers stayed; they are written as
   sentences with the date as the qualifier.
3. **Retrieval, the proof gate and telemetry were re-expressed as what the reader gets,** one plain
   sentence, followed by one concrete example. Extraction is exempt by owner instruction and keeps its
   subline and body word for word. The three headlines that test well were kept: "Your repos are
   already writing the handbook.", "Thirty thousand rules. Four reach the agent.", "Seventy-six harmful
   rules. Seventy-six refusals.", alongside "One team's fix becomes everyone's rule."
4. **A screens appendix was added** (section 7a) specifying route, data, viewport, required visible
   elements and caption for each screenshot, plus the capture recipe.
5. **Density was set by the extraction chapter.** Owner instruction, 2026-09-12: "One team's fix becomes
   everyone's rule.", its subline, its three beats and its Meridian fixture instrument work because they
   are little text and big value; keep that chapter exactly as it is. Its copy is therefore unchanged,
   and every other chapter was cut toward its length: the three scenes went from four long sentences
   each to three short ones, and retrieval, the proof gate and telemetry are each one headline, one
   sentence of what you get, one example and one line of microcopy.
6. **The waitlist stays the only conversion,** every protected string was re-mapped to its new section
   number, and the banned-word list and read-aloud test were rerun.

**2026-09-12, revision 4: as built.** The polish wave shipped seven sections rather than ten
(controller ruling 12), the ruling-13 hero headline and subline, and a live-DOM product demo in the
hero with its own captions block. Section 2a records the structure, every string that moved, and the
screens-appendix exception for scene A. No copy was reworded to fit the new structure: text was cut,
merged or moved, and every protected string is verbatim and in the DOM.

**Three rulings made in revision 3, recorded because they override earlier text in this file.**

- **The full delivery-boundary label no longer sits beside every figure.** Revision 2 required it in the
  microcopy under both proof-gate figures and forbade shortening it. The owner verdict of 2026-09-12
  names exactly that register as the problem and outranks this file, so the label moved, complete and
  unedited, into section 7 and stays in `proof_gate.microcopy`. The body says the same limit in English
  with the date. Nothing was softened or dropped.
- **The owner's deletion of the Q6 sentence is a copy cut, not a licence.** The sentence is gone from
  the retrieval section and from the hero body. The 2026-09-11 ruling that no 30k latency figure may
  appear on the page "in any form, including a softened one" is untouched, and the scale envelope
  survives as one plain sentence in section 7.
- **"Fixture mode" was corrected to the seeded local stack.** `ui/README.md` states that the hosted
  panel has one data source and no sample-data mode outside the component gallery, so screenshots are
  captured from the real UI reading the real Go service seeded from the Meridian example monorepo, and
  every caption carries the Meridian fixture label. The pre-merge collision report was likewise
  corrected: `guidefold report --base <ref>` produces it in CI, and there is no collision-report screen
  in `ui/src`, so scene B pairs with Proposals and its caption does not claim otherwise.
