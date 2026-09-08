Status: archiwalny zapis koordynacji, 2026-09-06; zachowany jako artefakt pracy. Bieżące zasady i API: docs/ui/pipeline/08-components.md oraz ui/src. Poniższy podział pracy agentów nie obowiązuje przy kolejnych zmianach.

# Shared implementation contract
Internal coordination, not a product screen. Root owns Shared.tsx, Shared.module.css, tokens.css, app.tsx, data.ts, domain.ts and package files. Route agents own only assigned route files and their module CSS.
All CSS lengths/colors via tokens. Common variables: --space-1 4px, --space-2 8px, --space-3 16px, --space-4 24px, --space-5 32px; --row-height 40px; --control-height40px/mobile44px; --two-columns (desktop two/mobile one); --aside-columns (desktop content/aside, mobile one); --field-columns (responsive); --border-width; --radius; --font-body; --font-display; --font-mono; --font-size-body; --font-size-small; --line-height-body; palette exact source names. Root can add tokens upon request. No inline dimensions/colors.
Shared exports:
- ActionButton: children, tone?:Tone, disabled?:boolean, onClick?:button handler, type?:button|submit|reset, id?, className?, href?:string. With href it is a navigation link; disabled means no navigation.
- Panel: title:string, eyebrow?:string, icon?:ReactNode, action?:ReactNode, children:ReactNode, className?, id?.
- StateBadge: children:ReactNode, tone?:Tone.
- RouteState: state:DataState, title:string, description:string, action?:ReactNode.
- Tabs: label:string, items:{id:string,label:string,href:string}[], current:string.
- ProvenanceTrail: entries:EvidenceEntry[] (domain.ts).
- ScopeTree: nodes:TreeNode[], selected?:string, label:string.
- DataTable: caption:string, headings:string[], children:ReactNode (tbody rows), className?.
- SkillDiff: source:string, candidate:string.
- MetricRow: items:{label:string,value:string,detail:string}[].
- Urn: value:string (readable full identifier and working copy).
- SkillContent: content:string (safe semantic Markdown, raw HTML skipped, commands inert).
- Field: id:string, label:string, hint?:string, error?:string, children:ReactNode; route controls set matching id.
- BrandMark: no props.
Routes receive {ctx:RouteContext}. Use ctx.href/ctx.go with view + Params. No .html suffix. Use Link from react-router-dom for ordinary links. Root handles page headings/navigation and blocking empty/loading/error/restricted screens. Routes render ready/partial/degraded/member bodies and honor ctx.canWrite/canFeedback.
All data from data.ts fixture; helpers sourceURL, visibleSkills, findSkill, proposalSkill, defaultProposal, bodyPrefix, digest, lineDiff.
No invented observations, classification, API calls or accounts. Fixture session save merges top-level memory. Nested values must be merged explicitly. Login/import/export are labeled local simulation; proposed CLI labeled Proposed CLI.
