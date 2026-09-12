# Landing v3: the simple page (owner reset, 2026-09-12)

Status: binding spec for the rebuild after the owner rejected the v2 demo wave as cluttered and unreadable. Base commit: 39f2396. Everything below overrides v2 DESIGN.md and copy.md where they differ. Nothing may be added to this page that is not in this file.

## The one rule

Each screen carries one idea, in at most one headline, one sentence, one visual and one value line. Owner, 2026-09-12: every block is written the way the "Under the hood" block is: spelled out in plain words, with a real product screen, and it always answers "what value do I get from having this product". No research vocabulary; the numbers stay in the proof band only. Total marketing copy on the page (excluding the protected waitlist, FAQ and legal strings): under 420 words. No qualifiers longer than one short line. No research vocabulary anywhere on the page (no "Wilson", "deterministic", "source-backed", "delivery boundary", "SRA-Bench" in headlines, "USE 1.2", "matrix", "reason=").

## Reading order (eight screens plus footer)

1. **Hero.** id `hero`.
   - H1: `Your coding agent doesn't know your team's rules. Now it does.`
   - One line: `Your agents stop guessing your conventions. Rules live next to the code, CI lifts the good ones into your organisation's brain, and every agent gets exactly what fits the task.`
   - Actions: `Join the waitlist` (protected label, to `#waitlist`) and the protected `Play demo` dialog. Trust line: `Open source today. The hosted service is planned.`
   - Visual: the real organisation portal screen `ui/public/assets/landing/app/proposals.webp` in a thin device frame (radius `--landing-radius-panel`, hairline border, glass shadow token), caption `The organisation portal, sample data`. It sits right of the copy at 1440 (copy columns 1–6, screen 7–12), below the copy at ≤1080, full width at 390. It enters with P3 (settle) once; it parallaxes at most 12 px against the film.
   - Nothing else in the hero. No proof rail, no glyph, no demo stage, no scroll cue text (a bare arrow-down icon link to `#extraction` is allowed).
2. **Why teams install it.** id `why`. Owner instruction 2026-09-12: the visitor must know what the product sells and why to install it.
   - Eyebrow: `Why install it`. H2: `One place for every rule, wired into every agent.`
   - Three rows (a role in bold, one sentence, no icons, hairlines between):
     - **Platform teams** — `Keep every rule of the monorepo in one place and wire it into Claude Code, Codex, Copilot and Gemini CLI in one afternoon.`
     - **Tech leads and rule owners** — `See what a rule change collides with before it merges, and approve what moves up to the whole organisation.`
     - **Developers** — `Start every task with the four rules that matter for that folder, without asking anyone.`
   - Value line under the rows: `What you get: one source of rules for people and agents, and no more copy-pasted conventions drifting between repos.`
   - Visual: none beyond the rows. Entrance P1 with stagger, once.
3. **Chapter 1, extraction.** id `extraction`. Keep the existing extraction chapter exactly as committed at 39f2396 (copy, instrument, pinned three beats). The owner approved it: "little text, big value". Polish only: type rhythm and padding; cap the pin track token `--landing-stage-scroll` from 260vh to 150vh (measured page-length remedy); write the beat opacities per beat element instead of one `--p` on the parent (measured recalc remedy); and one value line after the chapter's last beat: `What you get: a fix written once by one team reaches every team that needs it, with an owner's approval, never by copy-paste.` Nothing else changes.
4. **Chapter 2, the organisation's brain.** id `portal`.
   - Eyebrow: `2 · Share up`. H2: `Your organisation's brain, reviewed by owners.`
   - One line: `CI proposes the rule one level up. An owner approves it in the portal, and every team beneath gets it.`
   - Value line: `What you get: a living handbook of your organisation that writes itself from the teams' work, and one place to see and approve what every agent will follow.`
   - Visual: `app/proposals.webp` or `app/library.webp` (choose the one where a proposal and the hierarchy are both visible; capture a better frame with the e2e stub if neither shows both) in the same device frame, caption `Proposals view, sample data`.
5. **Chapter 3, retrieval.** id `how-it-works`.
   - Eyebrow: `3 · Fetch what fits`. H2: `Thirty thousand rules. Four reach the agent.`
   - One line: `At the start of a task, Guidefold walks your hierarchy and hands the agent the four rules that fit that folder and that job.`
   - Visual: ONE instrument panel, two columns at 1440 (stacked at ≤1080), that reads top to bottom like a story. Left column, "What the developer typed": a terminal line `$ rotate the service token` and beneath it, in small mono, `in platforms/atlas/identity/turnstile/`. Right column, "What Guidefold did", a numbered trace of the real Go API path in plain words, four rows, each a step name, one plain sentence and a small mono detail taken from real service output (run the CLI or the local stack; if a value is illustrative, label it "example"):
     1. `Found the scope` — `This folder belongs to atlas › identity › turnstile.` detail `scope: atlas.identity.turnstile`
     2. `Searched the rules in reach` — `27 rules apply somewhere on that path; Guidefold scored them for this task.` detail `SEARCH · 27 candidates · 4 selected`
     3. `Checked the proof` — `Each chosen rule still matches the file it came from, at the revision it came from.` detail `USE · source hash and revision verified · LOAD`
     4. `Handed the agent four cards` — `General first, local last. Full text loads only when the agent asks.`
     Beneath the trace, the four cards as compact rows, each with its level label in plain words and the rule name: `Organisation · security-baseline`, `Platform · atlas-api-conventions`, `Team · rbac-policies`, `Service · postgres-auth`, one line of the real card description each (from the Meridian fixture), and a small `Proof complete` tag on each. The trace rows enter in sequence (P1, 120 ms stagger) once; static under reduced motion. No "Replay", no "Find the scope. Show short cards. Load the full rule." strip, no "Query"/"Candidates" labels, no IntroFigure.
   - Value line under the instrument: `What you get: every task starts with the right conventions already in the agent's context, so fewer wrong pull requests and no hunting for the rule.`
   - Second visual, below the instrument: `app/usage.webp` in the device frame, caption `Afterwards, the portal shows which rule helped, sample data`.
   - Below that: the InstructionReader (protected: the fixture SKILL.md with its "Not a live run." label and blob URL) inside a collapsed `details` titled `Read the full rule the agent loaded`, open on click. Caption under the instrument: `Meridian fixture, the example repository in this project.`
6. **Under the hood.** id `under-the-hood`. Owner instruction 2026-09-12: explain what SEARCH, USE and ASK are, and that this is a separate search server with a database of the organisation's rules.
   - Eyebrow: `Under the hood`. H2: `A search server for your rules, next to your Git.`
   - One line: `Guidefold is a separate service with a database of every rule in your organisation. Git stays the source of truth; the service is the fast index your agents call.`
   - Three panels side by side at 1440 (stacked at ≤720), each a mono verb, a plain title and one sentence:
     - `SEARCH` — **The agent asks for the rules of this folder and this task.** `The service walks your hierarchy, scores every rule in reach and returns at most four short cards.`
     - `USE` — **The agent asks to load one rule in full.** `The service checks that the rule still matches its source file at the right revision, then delivers it.`
     - `ASK` — **The service refuses when something is off.** `A stale, conflicting or out-of-scope rule never loads silently; the agent stops and asks a human.`
   - Footnote line: `It runs in CI to tidy and lift rules, and at every agent session start to fetch them. The organisation portal is the UI on top of the same service.`
   - Value line: `What you get: agents that never load a stale or wrong rule, and a service you can run yourself today or let us host.`
   - Visual: `app/library.webp` in the device frame, caption `The rule database with your hierarchy, sample data`.
   - Entrance P3 per panel, once. No chips, no numbers, no diagram.
7. **Proof.** id `proof`. One band, two figures side by side, each a figure line and one small-print line, then one link.
   - `76 of 76 poisoned rules refused.` small print: `Sample repository, September 2026.`
   - `+8.53 pp recall over flat search.` small print: `SRA-Bench, September 2026.`
   - Value line: `What you get: numbers you can check, not promises.`
   - Link: `Read the numbers and how we got them` → `/docs/` (the precise labels live there, not on the page). Figures derive from `ui/src/data/research-evidence.json` as today; digits count once on reveal (number-ticker) with final values rendered without JS.
8. **Waitlist band.** id `waitlist`, form id `waitlist-form`. H2 `Be first on hosted Guidefold.` line `One email when it is ready. Nothing else.` The two protected availability statements (`Open source today.` … / `Paid hosting is planned.` …) as JSX nodes moved from the current Availability component, then the untouched WaitlistForm. Links: `Try the open-source version` (GitHub quickstart) and `Read the docs`.
9. **FAQ.** id `questions`. H2 `Before you join`. The four protected Collapsible answers, rows aligned to the page column, a top hairline separating the band.
10. **Footer.** Unchanged from 39f2396 apart from column alignment.

Removed from the page: the use-case chapter, the proof-gate and telemetry chapters, the research-results section and its chart, the hero proof rail, the tier glyph, the demo stage, the pre-JS text shell, IntroFigure, the Q6 qualifier sentence, every "Delivery boundary…" and "Measured, exploratory…" qualifier.



## Page grid (owner screenshot, 2026-09-12: "no proper margins in the blocks")

One container for the whole page: `--landing-container` max-width (1280 px at 1440, token) centred, with `--landing-gutter` side padding (token per breakpoint: 72 / 48 / 24 / 20 px). Every section's content box is that container: the nav, the hero copy and screen, every headline, sentence, value panel, device frame, the waitlist band's copy and form, the FAQ rows and the footer all share the same left and right edges. Backgrounds, scrims and the film bleed the full viewport width behind the container; no seam or gutter of film may show at the viewport edge (the fixed film layer covers the whole viewport; section planes and bands are full-bleed). Inside the container, two-column blocks split on the same 12-column grid with one `--landing-column-gap`. The waitlist band: copy columns 1–5, form columns 7–12, the form's submit button ends at the container's right edge; the FAQ rows span columns 1–12. The QA pass checks, for every section at 1440/1080/720/390, that the content box left and right edges equal the container's, within 1 px, and that `documentElement.scrollWidth === clientWidth`.

## The value panel (owner, 2026-09-12: "barely visible, looks vibe-coded; make it visible, animated, beautiful")

Every `What you get:` line is rendered by ONE shared component, `ValuePanel`, used on every block, never as plain small text:
- Composition: a full-column panel on the graphite glass surface (`--glass-*` tokens, `--landing-radius-panel`), inner padding `--landing-panel-pad`, an accent rule on its left edge in the survey teal accent (2 px, full height), the label `What you get` in the accent colour at the eyebrow size with letter-spacing, and the sentence at the lede size (`--landing-lede` scale, not body), in the display ink colour. Width: the panel spans the block's FULL content column at every width (at 1440 the same left and right edges as the block's headline, never a 34ch/46ch measure; the sentence inside wraps at the panel width minus padding); at 390 it is full width. Owner, 2026-09-12: the first render had it squeezed to half width; that is a defect.
- Motion, once, on entering 30% of the viewport: the accent rule draws from top to bottom (P2, `scaleY` from a token origin, 520 ms, `--ease-entrance`), the label fades in at 80 ms, the sentence rises 12 px and fades in at 160 ms (P1); a soft teal glow token on the rule for 900 ms then settles to the resting glow. Reduced motion: the resting state.
- It must read as the single most legible element of the block after the headline: measure contrast (label ≥ 4.5:1, sentence ≥ 7:1) and record it.
- One implementation, one test (renders the label and the sentence, static under reduced motion).

## Motion (unchanged vocabulary, less of it)

Film stays, scrubbed by scroll, with the poster image removed (the film fades in from the graphite field; reduced motion and Save-Data show the field). Apply the measured seek fix: gate each `currentTime` write on the previous seek having presented (`requestVideoFrameCallback`, fallback `seeked`), a 33 ms cap, a 100 ms stall guard, and stop the rAF loop at rest. Entrances: P1 lift for copy, P3 settle for the device frames, once. The extraction pin as committed. No other scroll-linked motion. Reduced motion: static final composition, no sampler.

## Loader

A fixed full-viewport overlay in `index.html`: the graphite field and the Guidefold mark centred (small webp, preloaded), a 900 ms breathing opacity on the mark, static under reduced motion; fades out over 240 ms when `document.fonts.ready` resolves and the hero has mounted; a 4 s CSS-only fallback fade and a `noscript` rule so content is never trapped. CLS 0.000; LCP under 2.0 s on the 4G emulation at 1440 and 390 (the mark may be the LCP element).

## Naming of sample content (owner, 2026-09-12)

Nobody outside the project knows "Meridian". Every caption, label and tag on the page that marks example content says `Sample data` (or `sample data` inside a caption), never "Meridian" or "fixture": this includes the extraction chapter's instrument label and any level or rule tags. The single exception is the protected InstructionReader label ("… from the Meridian example repository in this project. Not a live run."), which stays byte-identical under the preservation contract.

## Hard constraints (unchanged)

Protected strings byte-identical (preservationMap in `ui/design/landing/design-brief.json`; the protected-strings test stays green). Tokens only in `tokens.css`; no hex elsewhere; `node qa/check-contracts.mjs` zero diagnostics. Spectrum components where they fit, hash-pinned, adapted at the wiring layer; no new dependency. DOM order = visual order = tab order; 44 px targets; axe clean with contrast on. No horizontal overflow at 1440/1080/720/390. Page height under 8.5 viewports at 1440. Unit and e2e suites green; the film anchor map matches the ids that exist.

## Acceptance (the owner's tests)

- Three-second test: a stranger reads the H1 and the one line and can say what the product does.
- Screenshot test at 1440 and 390 with the logo covered: the page names rules next to code, an organisation portal, an agent getting four rules.
- Nothing on any screen is enigmatic: every visual has a plain caption; every chip or label on a screen is a real product word.
- The extraction chapter looks and reads as it does today.

## v3, as built (2026-09-12)

Implemented at `ui/src/routes/landing/`; the durable record is that directory's `DESIGN.md`.
Everything above was built as written except the following, each recorded rather than
silently resolved.

**Deviations.**

1. **The hero screen does not parallax.** Screen 1 allows "at most 12 px"; the Motion
   section says "No other scroll-linked motion". The second rule was taken as the stricter
   one, and a scroll registration for 12 px is the cost R1 exists to remove.
2. **The trace rows use the page's own P1 stagger**, 60 ms steps capped at 240 ms, not the
   120 ms this spec names. A 120 ms ladder needs four new delay tokens for one block, and
   the Motion section asks for the vocabulary unchanged.
3. **The retrieval instrument's caption reads `Sample data, the example repository in this
   project.`** Screen 5 spells it with "Meridian fixture"; the later "Naming of sample
   content" section overrides that, and the later instruction was followed.
4. **The four named cards are not the four a ranked run returns.** Screen 5's four names are
   the example repository's rules at the four levels of its hierarchy, which is what the
   four level labels say. `guidefold find --scope atlas.identity.turnstile --limit 4
   "rotate the service token"` returns `postgres-auth`, `rbac-policies`,
   `turnstile-oncall-runbook` and `postgres-production`. The `27 candidates · 4 selected`
   detail is literal from that run and from `find . -iname SKILL.md | wc -l`; the card set
   illustrates the hierarchy. Recorded in DESIGN.md §7 with the commands.
5. **Card lines are the opening clause of each rule's own `description`**, not the whole
   description. The full descriptions are 40+ words each and four of them alone would
   double the page's copy budget.
6. **The proof band carries no heading.** Screen 7 lists two figures, two small-print lines,
   a value line and a link, and "nothing may be added that is not in this file"; the
   landmark takes its name from an `aria-label`.

**Conflicts inside this spec, left as they are.**

7. **Copy budget.** The prose this spec prescribes totals about 636 words against its own
   "under 420". Every string is byte-binding and screen 3 is owner-approved as committed, so
   nothing was cut.
8. **The waitlist band prints the same sentence twice.** `Paid hosting is planned. Sign up
   for availability updates.` is both the moved availability statement and the untouched
   form's signup note, and both are protected. Shipped as specified.

**Targets not met.**

9. **LCP is 2 132 ms at 1440 and 2 276 ms at 390**, against "under 2.0 s". It began at
   3 972 ms; the 177 kB loader mark, the 2880 px screenshot encodes and the missing image
   preload were fixed, and what is left is critical-path serialisation at 1.6 Mbps.
   CLS is 0.0000 at both widths, as specified.

**Not fixable here.** The app screenshots still read "Meridian" inside the image. They are
captures of the running hosted UI against that example repository; renaming needs a
re-capture against a differently named workspace.
