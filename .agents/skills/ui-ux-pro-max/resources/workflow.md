# UI UX Pro Max repository workflow

## Authority

Use only sanitized job inputs and the pinned local files in this skill. The authority order is:

1. preservation contract;
2. sanitized source evidence and customer brief;
3. approved `reports/design-brief.json`;
4. UI UX Pro Max search results;
5. general style preferences.

A lower item never overrides a higher item. The database can suggest a system; it cannot invent copy, facts, routes, assets, claims, or capabilities.

## Mandatory shaping pass

During `shape-premium-direction`, form a short query from the verified product type, industry, audience, and tone. Never paste source-page copy into the command.

Run:

```bash
python3 /harness/skills/ui-ux-pro-max/scripts/search.py "<product industry audience tone>" --design-system --variance <1-10> --density <1-10> -p "<project slug>" --json
```

Do not pass `--motion`; upstream motion results can include GSAP examples, while this repository uses Motion. Run focused follow-ups only when the first result leaves a real decision open:

```bash
python3 /harness/skills/ui-ux-pro-max/scripts/search.py "<verified keyword>" --domain ux --max-results 8
python3 /harness/skills/ui-ux-pro-max/scripts/search.py "<verified keyword>" --domain landing --max-results 8
python3 /harness/skills/ui-ux-pro-max/scripts/search.py "<verified keyword>" --stack react --max-results 8
```

Write the `uiUxProMaxEvidence` object in `reports/design-brief.json` containing:

- the exact sanitized query and dial values;
- the returned product match, style, palette, type pairing, layout, and anti-patterns;
- accepted recommendations with a reason tied to source evidence;
- rejected recommendations with the conflicting preservation rule, evidence, or project constraint;
- any zero-result query and the narrower retry.

A design brief without that object is incomplete. If the bundled script or data is missing or unreadable, fail shaping truthfully. Do not guess a substitute result.

## Writer pass

Before tokens, layout, or component styling, the selected writer reads this skill and `uiUxProMaxEvidence` in `reports/design-brief.json`. Apply accepted recommendations to `DESIGN.md`; do not rerun a broad design-system query or create a second system.

Focused local searches are allowed when implementation exposes a concrete gap. Do not use `--persist`; record the decision in the existing `DESIGN.md` or `reports/build-notes.md`. Do not install `uipro`, packages, GSAP, icon libraries, fonts, or other dependencies. Translate any useful motion principle to the repository's Motion stack and reduced-motion contract.

Before handoff, run one focused UX or React query against the riskiest implemented interaction. Record the query, finding, and disposition in `reports/build-notes.md`. This is a check, not permission to change the approved direction.

## Repair and review

During repair, load the skill only for a verified visual, responsive, accessibility, or interaction finding. Use a focused local query and make the smallest change that satisfies the finding, brief, and preservation contract.

The Claude reviewer is read-only. It reads this workflow, the brief evidence, and relevant bundled data, then checks whether accepted rules were implemented and rejected rules stayed rejected. It never runs the script, edits source, installs the CLI, or turns a taste preference into a release blocker.

## Copy boundary

UI UX Pro Max may inform hierarchy, labels, and interaction placement, but `humanizer` and `avoid-ai-writing` own editable prose. Protected copy remains unchanged. Never copy promotional wording from the database into the page without the normal copy gates.
