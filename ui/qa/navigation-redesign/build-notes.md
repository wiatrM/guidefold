# Navigation and component redesign

Status: navigation, graph, combined landing and animated mini-demos deployed as Helm revision 4; API auth configuration remains blocked, 2026-09-09.
Cel: zapis decyzji i weryfikacji migracji hostowanego UI na kompozycje shadcnspace.

The production capture established the baseline problem: clipped identity, a decorative image competing with navigation, no task grouping and excessive dead width. The new shell removes every background image, groups destinations by owner task, collapses to a 64 px icon rail, uses a modal mobile sheet, and moves account/profile/logout into a stable footer.

All 15 public components keep their domain APIs and accessibility contracts but now expose shadcn-style `data-slot` composition. Base UI owns Button, Avatar, Dropdown Menu, Context Menu, Collapsible and Dialog/Sheet behavior; Motion owns fold-label and whole-title entry/exit. Sonner owns brief, non-blocking action feedback. The other equivalents are deliberately local copy-style recipes because Shadcnspace is a copy-and-customize library and the repository requires CSS Modules plus one token source.

Shadows are limited to controls, cards, table containers and portal layers. The requested Shine Border appears once at route entry as a 1 px teal sweep and is disabled by `prefers-reduced-motion`. There is no raster/pattern in either desktop or mobile navigation, no glass blur, glow, gradient text, parallax or infinite animation.

Focused UI UX Pro Max query: `collapsible sidebar dark developer platform profile dropdown reduced motion --domain ux --max-results 8`. It returned four applicable rules: reduced-motion support, no excessive motion, ease-out entry, and no parallax/scroll-jacking. All four are implemented.

Verified on 2026-09-09: `pnpm build` PASS; `pnpm test --maxWorkers=2` PASS with 30 files and 284 tests; `pnpm test:contracts` PASS with 15 components, 23 CSS files, 163 tokens and zero diagnostics. `pnpm exec playwright test --workers=1`: 35/35 PASS, including seven views/gallery axe at 1280/820/390, all view states, keyboard owner workflow, mobile sheet, fold sidebar, profile menu, context menu, persistent favorite and Sonner feedback. The shell contains no background image. These tests use a stub management API, not production accounts.

## Schema-flow and landing continuation

The owner expanded the direction to Mintlify/Airuncode and xyflow's MIT database-schema-node. Captures in `references/` were opened and compared with screenshots in `previews/`. Airuncode's centered hero, near-black surfaces and thin borders inform the landing; Mintlify's green connector emphasis informs the explanatory diagram. No source statistics, customer logos or unverified product claims were copied.

`PyramidChart/SchemaFlow.tsx` uses real React Flow, semantic schema tables and directed edges. The application starts paused; explanatory landing edges animate only in view, with a pause button and reduced-motion override. Mobile frames one readable selected node. Large application graphs focus a selected node instead of shrinking the entire graph; all nodes remain in the List alternative. Horizontal zoom controls avoid covering schema fields. Application `refines` edges connect from left-facing child handles to right-facing parent handles.

Visual QA repaired low-contrast navigation-group labels, initially tiny mobile graphs, reversed connector routing and controls overlapping node fields. Initial obsolete SVG unit expectations were replaced with Graph/List composition tests; actual edges/zoom/motion are checked in Playwright, not simulated jsdom layout.

The existing landing and waitlist implementation lives in `/home/mike/projects/gf-waitlist-20260908`. Its redesigned hero, diagram, demo, CTA and signup sections preserve the actual waitlist client, explicit consent, error handling and email actions. The navigation migration is now integrated in that checkout without changing the waitlist backend or sender configuration. Combined verification: build PASS, contracts PASS (15 components, 24 CSS files, 201 tokens), 32 Vitest files / 299 tests PASS, six post-integration browser checks PASS (seven screens/gallery at three widths, mobile sheet, profile/context/favorites/Sonner, graph), two landing flow/axe browser tests PASS (1440 and 390). Preview `/` and `/import` share the same bundle at `http://127.0.0.1:4332/`. The shared checkout remains unchanged outside the redesign's named paths. No commit or push was made.

## Requested deployment

Update 2026-09-09: owner supplied the kubeconfig path, now persisted in AGENTS.md. Docker became available; the combined UI was built and published as `redesign-20260909-motion-02`. The preflight diff changed only the UI container image. Helm revision 4 rolled out with 2/2 UI replicas ready; root/import and matching assets return 200. See [deployment-report.json](deployment-report.json) and the environment runbook. No backend, database or secret changed. API remains 503 with `workos_requires_api_key_and_client_id`. The missing-access preflight below is historical, not the current blocker.

The owner explicitly requested deployment after completion. Read-only preflight finds public `/` HTTP 200, but `/api/v1/auth/providers` and `/api/v1/waitlist` HTTP 503 before this release. WSL has only `docker-desktop`; Windows has `docker-desktop` and unrelated `do-fra1-webkd-1`. No configured production context for the runbook's `192.168.8.128` cluster was found. The user was asked for a production kubeconfig **path**, never its contents. No secret was read, no image published, no cluster resource mutated and no production deployment claimed.
