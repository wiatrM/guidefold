## Commands

| Command | Category | Description | Reference |
|---|---|---|---|
| `craft [feature]` | Build | Deprecated alias for an ordinary new-work request | [resources/craft.md](./craft.md) |
| `shape [feature]` | Build | Plan UX/UI before writing code | [resources/shape.md](./shape.md) |
| `init` | Build | Capture durable product context in PRODUCT.md | [resources/init.md](./init.md) |
| `document` | Build | Generate DESIGN.md from existing project code | [resources/document.md](./document.md) |
| `extract [target]` | Build | Pull reusable tokens and components into design system | [resources/extract.md](./extract.md) |
| `critique [target]` | Evaluate | UX design review with heuristic scoring | [resources/critique.md](./critique.md) |
| `audit [target]` | Evaluate | Technical quality checks (a11y, perf, responsive) | [resources/audit.md](./audit.md) · native: [resources/audit.native.md](./audit.native.md) |
| `polish [target]` | Refine | Final quality pass before shipping | [resources/polish.md](./polish.md) |
| `bolder [target]` | Refine | Amplify safe or bland designs | [resources/bolder.md](./bolder.md) |
| `quieter [target]` | Refine | Tone down aggressive or overstimulating designs | [resources/quieter.md](./quieter.md) |
| `distill [target]` | Refine | Strip to essence, remove complexity | [resources/distill.md](./distill.md) |
| `harden [target]` | Refine | Production-ready: errors, i18n, edge cases | [resources/harden.md](./harden.md) |
| `onboard [target]` | Refine | Design first-run flows, empty states, activation | [resources/onboard.md](./onboard.md) |
| `animate [target]` | Enhance | Add purposeful animations and motion | [resources/animate.md](./animate.md) |
| `colorize [target]` | Enhance | Add strategic color to monochromatic UIs | [resources/colorize.md](./colorize.md) |
| `typeset [target]` | Enhance | Improve typography hierarchy and fonts | [resources/typeset.md](./typeset.md) |
| `layout [target]` | Enhance | Fix spacing, rhythm, and visual hierarchy | [resources/layout.md](./layout.md) |
| `delight [target]` | Enhance | Add personality and memorable touches | [resources/delight.md](./delight.md) |
| `overdrive [target]` | Enhance | Push past conventional limits | [resources/overdrive.md](./overdrive.md) |
| `clarify [target]` | Fix | Improve UX copy, labels, and error messages | [resources/clarify.md](./clarify.md) |
| `adapt [target]` | Fix | Adapt for different devices and screen sizes | [resources/adapt.md](./adapt.md) · native: [resources/adapt.native.md](./adapt.native.md) |
| `optimize [target]` | Fix | Diagnose and fix UI performance | [resources/optimize.md](./optimize.md) |
| `live` | Iterate | Visual variant mode: pick elements in the browser, generate alternatives | [resources/live.md](./live.md) |

Routing:

- **No argument:** read [routing.md](./routing.md) and present its context-aware menu; never auto-run a command.
- **Explicit or clearly implied command:** load its reference (native variant on native platforms) and follow it. Ask once if two commands fit.
- **Otherwise:** treat the request as general design work. Missing PRODUCT.md routes a new surface or replacement world through init, then new-work; a narrow refinement of existing code proceeds on the incumbent implementation as context.mjs directs, offering init afterward rather than blocking on it.
- `teach` aliases `init`. `craft` is a deprecated alias for ordinary new-work and adds nothing. `shape` owns task discovery, then enters new-work only for visual-world and surface-concept decisions.

After init writes PRODUCT.md, resume without rerunning `context.mjs`; init loads the native platform reference itself when the platform it recorded is `ios`, `android`, or `adaptive`.

**Pin / Unpin:** `node .agents/skills/impeccable/scripts/pin.mjs <pin|unpin> <command>` creates or removes a standalone `$<command>` shortcut. Report the script's result concisely; relay stderr verbatim on error.

**Hooks:** `$impeccable hooks <on|off|status|ignore-rule|ignore-file|ignore-value|reset>` manages the design detector hook for this project (auto-runs the detector after UI file edits and surfaces findings). Load [resources/hooks.md](./hooks.md) when the user invokes it with any argument.

**Doctor:** `$impeccable doctor` reports and repairs drift between this project's Impeccable artifacts (PRODUCT.md, DESIGN.md and its sidecar, config, surface briefs, the hook) and what this version reads. Load [resources/doctor.md](./doctor.md) when the user invokes it, or when they ask what is out of date, stale, or needs refreshing. A `CONTEXT_STALE` directive in Setup's output is the cheap subset of the same report; act on it there per its own instructions rather than running doctor unasked.

**Never repair drift as a side effect of a design task.** A `CONTEXT_STALE` finding is reported, not acted on, unless the user asks. The one exception is a finding marked `auto`, which the next write to that file performs anyway.

