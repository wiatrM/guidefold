# Guidefold landing page, v2 copy

Rebuilt from zero on the owner verdict of 2026-09-09, reworked on the value brief of 2026-09-11
(`value-brief.md`), bound by the citation ruling of 2026-09-11, and written in the sales tone the owner
directed on 2026-09-11. Authority order: preservation contract (`preservationMap` in
`../design-brief.json`) → owner verdict, value brief and citation ruling → `../DESIGN.md` → this file.

Spelling is British (`organisation`) to match the protected strings. There are no em dashes or en
dashes anywhere in the copy.

**The tone rule, stated once so every section obeys it.** Headlines and sublines are confident claims
phrased as outcomes, with the strongest citable number placed where it lands hardest. Qualifiers are
real and never removed, but they live in the microcopy directly beneath a figure or in a footnote,
never inside a headline or a subline. No hedge word does a qualifier's job: the qualifier is a full
sentence in small type, and the headline above it stays a claim.

The `?confirm=` and `?unsubscribe=` branch renders the `EmailAction` view **instead of** all marketing
sections below. That branch and its strings are protected and unchanged.

---

## 1. Positioning

**Category (one sentence).**
Guidefold is Git-native rule extraction and retrieval for coding agents: each team's rules condense
upward into organisation knowledge, and an agent receives only the few that apply where it is working,
each one carrying its source proof.

**The enemy (the status quo pain).**
The knowledge that would answer this task exists, written down, in a directory nobody on this task has
opened. It stays there because it was written for one service and never generalised, while the agent's
context fills with rules from teams the developer has never worked in. Every extra coding tool adds
another copy of the same instruction to keep in sync.

**The promise.**
Ordinary team work produces organisation knowledge as a by-product, and an agent standing in
`platforms/atlas/identity/turnstile/` receives the handful of rules that apply *there*, in whichever
coding tool the developer chose, with a proof of where each one came from.

**Three proof points.**

| # | Proof | Exact citation and label | Where it appears |
|---|---|---|---|
| 1 | Nothing reaches an agent unproven | ASK for all 76 harmful mutations, LOAD for all 4 safe cases; the flat control loaded all 76. One-sided Wilson 95% upper bound for harmful delivery 4.81%. Label: **delivery boundary, deterministic, source-backed; not a task-success claim.** 2026-09-11. | Hero proof strip, section 4 |
| 2 | The safe case survives the real delivery path | The same 4/4 safe targets passed through the production USE 1.2 HTTP handler with `reason=source_proof_complete`, and the service verified the cited source hash and range. Same label, same date. | Section 4 |
| 3 | The hierarchy improves retrieval | +8.53 pp Recall@10 on SRA-Bench, 5,400 queries over 26,262 skills. **Measured**, exploratory offline retrieval. `ui/src/data/research-evidence.json`, 10 September 2026. | Hero proof strip, section 6 |

**Source verification, checked 2026-09-11 in this working tree.** Provenance is the page's whole
thesis, so each figure carries where it can be read.

| Figure | Source | State |
|---|---|---|
| +8.53 pp Recall@10, 5,400 queries, 26,262 skills | `ui/src/data/research-evidence.json`, with per-artefact SHA-256 in its `sources` block | Verified here. Rendered from the file at runtime. |
| 76 harmful mutations answered ASK, 4 safe cases answered LOAD, flat control loaded all 76, Wilson 95% upper bound 4.81% | `docs/RESEARCH.md` §5.30 on branch `codex/e2-proof-gate-matrix-20260910`, 2026-09-11, reproducible from `research/e2-source-backed-20260911/README.md` | Read and confirmed on that branch. Pending here: the implementer mirrors it into `ui/src/data/research-evidence.json` with path and hash before the page renders it. |
| 4/4 through the production USE 1.2 HTTP handler, `reason=source_proof_complete`, service-verified hash and range | `docs/RESEARCH.md` §5.32 on the same branch, 2026-09-11, reproducible from `research/e2-source-backed-http-20260911/README.md` | Same. Confirmed on the branch, pending the mirror. |
| E6.7 replay 17/20 vs 16/20 · 25/25 hierarchical SEARCH · any 30k latency figure | Ruled not citable, 2026-09-11 | **Must not appear on the page in any form, including a softened one.** |

**The one label, used everywhere.** Both proof-gate figures carry exactly this label, in full, in the
microcopy next to the figure: *delivery boundary, deterministic, source-backed; not a task-success
claim.* It is never shortened to "verified", never shortened to "safety", and never dropped at a
breakpoint. The older synthetic fixture report on the same branch
(`docs/reports/bakeoff/E2-PROOF-GATE-MATRIX-2026-09-10.md`, 2 safe loads and 6 abstentions) is a
different and earlier run; its counts are not blended with these.

**Figures the page must not produce.** No aggregate "zero risk" from 76 of 76. No latency number for
the 30k corpus. No `+8.53 pp` without its exploratory qualifier somewhere on the same screen. No
revival of an excluded figure in a softer form.

**The emotion the page should leave: recognition, turning into confidence.**
A platform lead should recognise their own monorepo in the first two screens and finish the page
believing this team has already measured the thing they were about to ask about. The page brags, and
every brag is a number someone can go and reproduce. Nothing manufactures urgency, scarcity or social
proof, because there is none to report and the real numbers are better.

---

## 2. Page structure from zero

Nine sections. Header and footer are microcopy (section 5 of this document), not funnel sections.

### Section 1. Hero: pillars 1 and 2, with proof above the fold

- **Purpose:** show the outcome and its evidence in one glance, before any explanation.
- **Must believe after it:** "Rules climb out of the repos, the agent gets four, and these people already measured whether that is safe."

**Headline** (6 words)

> Your repos are already writing the handbook.

**Subline** (17 words)

> Guidefold promotes what generalises, then hands your agent the four rules that apply, each one proven.

**Body** (2 sentences)

> Ranking runs across the whole hierarchy in real time, designed for a 30k-skill corpus. Every rule arrives with its source proof attached, and the ones that cannot prove themselves never arrive at all.

**Proof strip** (two items above the fold: one safety figure, one retrieval figure, each with its
qualifier in the microcopy directly beneath it)

> **76 of 76 harmful rules refused.**
> Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.
>
> **+8.53 pp Recall@10 on SRA-Bench.**
> Measured, exploratory offline retrieval. 10 September 2026.

**CTA, primary**

> Join the waitlist

**CTA, secondary** (protected control, must stay visible in the hero)

> Play demo

**Trust line, under the actions**

> Open source today. The hosted service is planned.

**Text link, to section 6**

> Read the numbers and how we got them

*No eyebrow. The value brief forbids opening with a category label, and "Instruction library for coding
agents" was exactly that. The headline is present continuous on purpose: promotion is a diff an owner
approves, and PRODUCT-PIVOT §2 is explicit that Guidefold does not improve knowledge on its own. Past
tense would overpromise by one step and section 2 would contradict it two screens later. No competitor
in the PRODUCT-FOCUS matrix can say this line at all, because none of them promotes a rule upward.*

*Proof-strip rule for the implementer: the figure is the headline weight, the qualifier is one line of
microcopy beneath it, and the qualifier renders at every breakpoint. An item that cannot fit its
qualifier is dropped whole. Both items stack at 720px and both stay above the fold.*

---

### Section 2. Extraction: pillar 1

- **Purpose:** make the hero headline literal, and make it sound like the unfair advantage it is.
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

---

### Section 3. Retrieval: pillar 2, with pillar 7

- **Purpose:** turn 30,000 rules from a liability into the reason the product exists.
- **Must believe after it:** "Selection happens on every prompt, in a place I control, and I can read the code."

**Eyebrow**

> What the agent gets

**Headline** (7 words)

> Thirty thousand rules. Four reach the agent.

**Subline** (15 words)

> Ranked by the task and by the place in the repository, in real time, every prompt.

**Body** (2 sentences)

> General cards first, then the local rule that sharpens them, and full text only when the agent asks for it. Your context window carries four cards instead of a filing cabinet.

**Microcopy, beneath the body**

> Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.

**CTA**

> Try the open-source version

**Supporting elements kept in this section** (layout, not copy): `IntroFigure` and `InstructionReader`
with its protected Meridian fixture label.

---

### Section 4. The proof gate: pillar 4, with pillar 8

- **Purpose:** answer the question a platform buyer asks first, and answer it with the best number on the page.
- **Must believe after it:** "A bad rule fails loudly here. Everywhere else it would have shipped."

**Eyebrow**

> Safety boundary

**Headline** (6 words)

> Seventy-six harmful rules. Seventy-six refusals.

**Subline** (13 words)

> The flat control loaded all 76. Guidefold answered ASK every single time.

**Body** (2 sentences)

> Delivery requires a source proof: hash, revision, scope. Conflicting, stale and out-of-scope rules become an ASK, never a silent load and never a silent fallback, and every delivery traces back to the revision it came from.

**Proof lines** (figure in headline weight, label in the microcopy beneath, in full, both times)

> **ASK for all 76 harmful mutations, LOAD for all 4 safe cases. One-sided Wilson 95% upper bound for harmful delivery: 4.81%.**
> Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.
>
> **The same 4 safe targets came through the production USE 1.2 HTTP handler with `reason=source_proof_complete`, source hash and range verified by the service.**
> Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.

**CTA:** none.

*Wording constraint: the brag is the comparison, which is why the flat control is named in the subline.
The count is 76 harmful mutations, the interval sits beside it, and it is never written as "zero risk",
"no unsafe deliveries ever" or "100% safe". The label is never shortened.*

---

### Section 5. Telemetry and promotion: pillar 3, with pillar 5

- **Purpose:** show the buyer the surface they will sit in front of, and make it sound like control rather than a dashboard.
- **Must believe after it:** "I will know which rule failed, why, and I decide what gets promoted."

**Eyebrow**

> For the organisation

**Headline** (7 words)

> You see which rule failed, and why.

**Subline** (15 words)

> Per team: task success, ASK reasons, the SEARCH to USE funnel, tokens, tool calls, time.

**Body** (2 sentences)

> ASK reasons come from a fixed vocabulary, so "Conflicting rules" and "Revision changed" arrive as counts you can act on rather than a log you have to read. Every pull request that touches a rule gets a report before merge: what changed, what collides, what an agent would now see.

**Microcopy, beneath the body**

> Missing data reads Unknown, never zero.

**CTA:** none.

---

### Section 6. Evidence: pillar 2 measured, with pillar 9

- **Purpose:** let an engineer try to disbelieve the page, and hand them the failures before they find them.
- **Must believe after it:** "They publish the intervals and the regressions, so the rest of the page is literal too."

**Eyebrow** (already rendered by `ResearchEvidence.tsx`)

> Research update · 10 September 2026

**Headline** (7 words)

> Plus 8.53 points of recall over flat.

**Subline** (13 words)

> 5,400 queries across 26,262 skills on SRA-Bench, against flat dense search.

**Microcopy, directly beneath the figure**

> Measured, exploratory offline retrieval, not completed coding tasks. Four of six datasets improved; CHAMP and TheoremQA regressed. The hierarchy came from benchmark corpus prefixes rather than real repository scopes.

**Second block, what is still open** (calm, and carrying no figure)

> Task-level value is not settled. The delivery boundary in section 4 is deterministic and source-backed; it says nothing about whether a delivered rule helped somebody finish the work. That measurement needs real repository snapshots and frozen tasks, and we have not made it yet.

**Third block, the scale envelope**

> Corpora of 1k, 10k and 30k skills, cold and warm cache: in the Q6 validation plan. Designed for, not yet measured. No latency figure appears on this page until that run exists.

**CTA** (both existing, both kept)

> Read the evidence
> Download results and source hashes

**Binding constraint for the implementer:** the chart, the table, the interval paragraphs, the Pi
delivery-boundary trace and the `<details>` method block inside `ResearchEvidence.tsx` stay as they
are. This section's copy sits above them and must not soften them. Values come from
`ui/src/data/research-evidence.json` at render time, never hard-coded into the markup.

---

### Section 7. Availability: pillars 6 and 10

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

*Only one "Try the open-source version" link survives in the body of the page, in section 3. The footer
keeps its own. The availability band's copy of it is removed.*

---

### Section 8. Waitlist

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

### Section 9. Before you join

- **Purpose:** absorb the four objections that would otherwise stop the signup, without spending them in the reading order.
- **Must believe after it:** "They answered the price and the privacy question without being asked twice."

**Headline** (3 words)

> Before you join

**Subline** (10 words)

> Price, availability, coding tools, and what happens to your email.

**Body:** none. The four protected question triggers and their protected answers follow, all panels
closed on load, with `#privacy` and `#question-2` still expanding on deep link.

---

## 3. Section by section: what is removed and why

| Removed | Where it was | Why |
|---|---|---|
| `Instruction library for coding agents` | hero eyebrow | A category label, which the value brief forbids above the fold. The hero opens on the outcome. |
| `Team rules. Right where agents work.` | h1 | True of every competitor in the PRODUCT-FOCUS matrix, and it names no outcome. |
| `Rules stay next to the code. Guidefold copies the reusable part up the organisation pyramid, then gives each agent the few rules it needs.` | hero lede | Three clauses doing one job, and "pyramid" is our internal noun, not the reader's. |
| `Our hierarchy test: +8.53 pp Recall@10 on SRA-Bench.` | hero proof line | The figure was billed three times on one page and none of the three carried its status. It now appears in the hero proof strip with its qualifier beneath it, and again in section 6. |
| `New research: +8.53 pp Recall@10 on SRA-Bench` | hero text link | Same reason. The link survives with a label that carries no magnitude. |
| `Why we built it` and its three paragraphs | WHY section | The heading was about us, and the section explained a problem the hero and section 2 now demonstrate. |
| The three `dt`/`dd` mechanism beats | HOW detail list | Beats 1 and 3 are restated by the hero body and the `InstructionReader` panel directly beneath them. Beat 2 is now the section 3 subline. |
| `RouteRule` and `ScopePyramid` | HOW | Five visual components stacked in one section is the feature dump the owner verdict named. |
| `View the integration diagram` `<details>` | HOW | A 1536x1024 architecture drawing is documentation. It stays in the README, which section 3 links to. |
| Whole `roles` array and the 3-up `RoleCard` grid | VALUE | `promise` and `detail` say the same thing twice per card, and the answer sentence above says all three a third time. Sections 4 and 5 replace it with the two claims a buyer weighs. |
| `What your team gets` and its answer sentence | VALUE heading | A benefit summary of a section that no longer exists. |
| `Try the open-source version` in the availability band | availability | Third instance of the same link on one page. |
| `Scroll to see how it works`, with `aria-label="Scroll down to see why Guidefold exists"` on `href="#why"` | hero scroll cue | Visible label, accessible name and destination disagreed with each other. Replaced in section 5 of this document. |
| `25/25 hierarchical SEARCH requests, no 422 after the bridge fix` | section 3 proof line, first v2 draft | Ruled not citable on 2026-09-11. Removed rather than softened; a softened unsourced claim is still unsourced. |
| `Task replay E6.7: 17/20 against 16/20` | section 6, first v2 draft | Ruled not citable on 2026-09-11. The block now states what is unsettled without quoting counts. |
| `Instructions, selected by task.` and the old feature-intro copy | removed in v1, stays removed | Recorded so the v1 cut list is not silently reopened. |

---

## 4. Protected strings checklist

Every row survives **verbatim**. Repositioning is allowed; rewording, re-punctuating and summarising
are not. Source of truth: `preservationMap` in `../design-brief.json`.

| Protected content | Where it lives in the new structure |
|---|---|
| Waitlist form: `Paid hosting is planned. Sign up for availability updates.`, `Your email`, `you@company.com`, `Join the waitlist`, `Saving…`, `Email me about hosted Guidefold. Unsubscribe anytime. Privacy`, honeypot `Website`, `maxLength` 254, `#waitlist-email` / `#waitlist-consent` / `#waitlist-error`, 12s abort | Section 8, unchanged component |
| Waitlist success state: `Check your inbox to confirm.`, `New signups receive one confirmation email. Repeat requests do not send another message. Already confirmed? You’re all set.`, `Missing the email? Contact hello@cloudfloo.io.` | Section 8, replaces the form in place and takes focus |
| Four error strings: `Too many attempts. Please try again in an hour.`, `Please check your email and consent, then try again.`, `This link is invalid or expired. Contact hello@cloudfloo.io for help.`, `We could not confirm the request. Please try again. Your input is still here.` | Section 8, `role="alert"`, typed email retained |
| Confirm and unsubscribe flow: `Confirm your email`, `Leave the waitlist`, `Confirm that you want updates about hosted Guidefold.`, `Stop receiving hosted Guidefold updates.`, `You’re on the hosted Guidefold waitlist. We’ll email you about availability.`, `You’ve been unsubscribed from the Guidefold waitlist.`, `Confirm email`, `Unsubscribe`, `Back to Guidefold` | `EmailAction` branch, rendered **instead of** sections 1 to 9; URL replaced with `/`; the hero video never mounts |
| FAQ trigger `Is Guidefold available now?` and its answer | Section 9, `#question-1`, closed on load |
| FAQ trigger `What will hosting cost?` and both pricing paragraphs, including $99 per organisation per month excluding taxes, the $9 of provider usage costs $10 prepaid budget, no unlimited AI allowance, Enterprise SSO not included, quotas specified before purchase | Section 9, `#question-2`, closed on load, deep link expands it. No figure rounded, restated, or lifted into a pricing card. |
| FAQ trigger `Which coding tools can I use?` and its answer, with the link to `#coding-harness-to-instruction-delivery` | Section 9, `#question-3` |
| FAQ trigger `How is my email used?` and all three paragraphs: the Resend sentence, the 30-day and 365-day deletion schedule, the deduplication-hash sentence, the YouTube paragraph, the `mailto:hello@cloudfloo.io` link | Section 9, `#privacy`, opened by the consent link and by the hash |
| `Open source today.` with `CLI and retrieval service.` | Section 7, left statement |
| `Paid hosting is planned.` with `Sign up for availability updates.` | Section 7, right statement **and** section 8 as the form's signup note. Both instances are required. |
| `Open-source tools. Hosted service planned.` | Footer bottom line |
| GitHub URLs: repository root, `#quickstart`, `#coding-harness-to-instruction-delivery`, the fixture `SKILL.md` blob URL | Header nav (`GitHub`), section 3 text link (`#quickstart`), section 9 question 3, footer "Open source" group, `InstructionReader` "Open the original file" (blob URL) |
| `/docs/` | Header nav `Docs`, section 7 `Read the docs`, footer `Documentation` |
| The demo `e350wBr1W8c` as the **Play demo** action | Section 1, hero secondary control. `DemoDialog` mounts the `youtube-nocookie` iframe only while open and keeps the `Watch on YouTube` link inside. No YouTube request before opening. |
| Document title `Guidefold \| Team instructions for coding agents` | Route effect, unchanged |
| `Skip to content` | First focusable element, targets `#main` |
| Meridian fixture excerpt and its "not a live run" label | Section 3, `InstructionReader`; the four bullet lines and the fixture label unchanged |

**Not protected, despite the v1 copy file marking it so:** the FAQ section heading `Before you join`.
`preservationMap` protects the four triggers and answers, not the heading. It is kept in section 9
because it is the right words, not because it is frozen.

---

## 5. Microcopy

**Header nav** (unchanged labels). `How it works` points at `#extraction`, section 2, because the
mechanism begins there and a visitor landing on section 3 would arrive mid-explanation. Section 3 keeps
`id="how-it-works"` so existing inbound links and the v1 anchor still resolve.

> How it works · Docs · GitHub

**Header action**

> Join the waitlist

**Skip link** (protected)

> Skip to content

**Hero scroll cue.** Visible label, accessible name and destination must agree. The v1 cue failed all
three against each other.

> Visible: `How rules move up`
> `aria-label`: `Scroll to the extraction section`
> `href`: `#extraction`

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

> Try the open-source version (section 3, and the footer, and nowhere else)
> Read the docs (section 7)
> Read the numbers and how we got them (hero, to `#research-results`)
> Read the evidence · Download results and source hashes (section 6)
> Open the original file (instruction reader, protected destination)

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
| Research chart has not entered the viewport, or the lazy chunk fails | No copy and no spinner. The table below it already carries every value. |
| A proof-strip item cannot fit its qualifier at a breakpoint | The whole item is dropped. A figure never renders without its qualifier. |
| The 76/4/4.81% figures have not yet been mirrored into `research-evidence.json` | The hero proof strip ships with the retrieval figure alone and section 4 runs on its prose. A one-item strip is fine. An unsourced one is not. |
| Waitlist submitted with an address already confirmed | The protected success state, unchanged. It already says `Already confirmed? You’re all set.` |
| Waitlist network failure or 12s abort | `We could not confirm the request. Please try again. Your input is still here.` (protected) |
| Demo dialog opened without network | The `Watch on YouTube` link inside the dialog stays visible and is the fallback. |

---

## 6. Anti-slop self-check

**Read-aloud test.** Every line above was read as if said to a colleague at their desk. Five failed and
were rewritten.

1. "Guidefold copies the reusable part up the organisation pyramid" became "promotes it a level". Nobody
   says "up the organisation pyramid" out loud.
2. "Retrieval, not concatenation" was cut. It is a negative parallelism, which `humanizer` §9 bans
   outright, and it was jargon before the reader had the mechanism.
3. "Every other tool concatenates, then truncates" was cut. It is a categorical vendor claim, and
   `docs/PRODUCT-FOCUS.md` says in its own header that its categorical claims about vendor gaps are
   historical and are not a basis for new positioning. The replacement says what Guidefold does.
4. "Zero unsafe deliveries" was cut in favour of the count, the control and the interval. The first is a
   claim about all deliveries; the second is what was measured, and it reads better anyway.
5. "Your repos already wrote the handbook" became "are already writing". The past tense asserted a
   finished artefact that section 2 and PRODUCT-PIVOT §2 both contradict.

**Where the confidence comes from.** The tone directive is met with numbers rather than adjectives.
Every headline in sections 1, 2, 3, 4 and 6 is either a count from the citable set or an outcome the
reader gets, and none of them contains a hedge. The qualifiers were not weakened to achieve that; they
moved to the microcopy line beneath the figure, in full sentences, where they are still on the same
screen as the claim.

**Banned vocabulary.** The list in `docs/ui/UX.md` §6 was checked line by line against every string
above, plus the additional terms named in the writing brief. No match, so nothing had to be removed.
Two adjacent habits were caught anyway: generic strength adjectives, which the tone directive is met
without, and anonymous research attribution, which section 6 replaces with a named run, a date, dataset
counts and downloadable source hashes.

**Structures checked and absent.**

- Em dashes and en dashes: zero. Hyphenated compounds are not em dashes.
- Scene-setting openings, invitations to picture something, and rhetorical-question openers: zero. The
  `copywriting` skill recommends rhetorical questions; the brief forbids them, and the brief wins.
- Rule of three: "service, then team, then organisation" is the hierarchy as implemented, not a rhythm.
  Section 5's metric list has six entries, section 9's subline four, section 7 two, section 4 one claim
  with two proof lines. No list was padded to reach three.
- Title case headings: none. All headings are sentence case.
- Copula avoidance ("serves as", "represents", "stands as"): none. The copy uses is, gets, keeps, ranks,
  promotes, refuses, reaches, traces.
- Superficial `-ing` clauses ("ensuring...", "highlighting..."): none.
- Inline-header bullet lists in prose: none. The tables here are specification, not page copy.
- Exclamation points, emoji, curly quotes in new copy: none. Curly apostrophes inside protected strings
  are preserved exactly, because they are protected.
- Uniform cadence: section 4 runs 6 words, 13, then 8 and 27. Section 2 runs 6, 17, then 4 and 22. Read
  aloud, the rhythm varies.

**Competitor test.** Every headline was checked against the PRODUCT-FOCUS matrix. "One team's fix
becomes everyone's rule" is unsayable by anyone who does not promote a rule upward, which is all of
them. "Thirty thousand rules. Four reach the agent." is unsayable by anyone who concatenates or
truncates. "Seventy-six harmful rules. Seventy-six refusals." is unsayable by anyone who has not run
the matrix.

**Fabrication check.** No customer, logo, testimonial, certification, adoption count or launch date is
asserted anywhere. Every figure on the page appears in the tables in section 1 with its source and
label, plus `at most four` cards and the 30k design envelope, plus the protected pricing figures inside
the FAQ.

**Screenshot test.** With the wordmark removed, the hero headline, the proof strip and section 3's
subline name the product's job without a logo: a coding agent, a monorepo, a scope, four proven cards.
An answer of "some AI dashboard" would be a P1, and this structure does not produce one.

---

## 7. Revision log

**2026-09-11, first v2 draft.** Rebuilt from zero on the owner verdict of 2026-09-09. Eight sections,
hero on outcome rather than category, role grid and WHY section removed.

**2026-09-11, value brief.** Reworked to nine sections, each mapped to one pillar of `value-brief.md`,
in the order extraction, retrieval, telemetry. Proof strip added above the fold. Proof gate and
telemetry became their own sections. Pillars 6 and 7 folded into sections 7 and 3. Pillar 9 written as
an envelope, not a result.

**2026-09-11, citation ruling.** Proof-gate figures cited from `docs/RESEARCH.md` §5.30 and §5.32 on
branch `codex/e2-proof-gate-matrix-20260910`, each carrying the full delivery-boundary label; the
implementer mirrors both into `ui/src/data/research-evidence.json` with path and hash before render.
Three figures removed outright as not citable: 17/20 versus 16/20, 25/25 SEARCH requests, and any 30k
latency number. Section 3 lost its proof line rather than gaining a vaguer one.

**2026-09-11, tone directive.** Rewritten to sell. Headlines and sublines became claims phrased as
outcomes with the strongest citable number placed where it lands: section 4 now leads on "Seventy-six
harmful rules. Seventy-six refusals.", section 6 leads on the recall figure itself, section 2 on "One
team's fix becomes everyone's rule", section 7 on "Clone it today", section 8 on "Be first on hosted
Guidefold." Every qualifier was preserved word for word and moved to a microcopy line directly beneath
its figure, so no hedge sits in a headline and no claim sits on screen without its limit. The hero
headline tense fix, the envelope-versus-measurement separation, the reader-facing eyebrows and the nav
anchor correction from the review pass were all kept.
