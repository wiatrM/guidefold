Status: archiwalny zapis koordynacji, 2026-09-06; zachowany jako artefakt pracy. Bieżące zasady i API: docs/ui/pipeline/08-components.md oraz ui/src. Poniższy podział pracy agentów nie obowiązuje przy kolejnych zmianach.

# Extraction contract
Internal development coordination, stage 8; Meridian fixture only.
Root owns package/config/tokens/domain pure helpers/Gallery/QA. Port agent owns app/routes/data.
Component API and rendering match frozen hifi Shared.tsx. Each component gets index.tsx, Name.module.css, Name.test.tsx, Name.stories.tsx.
Imports: types from ../../domain; SkillDiff helper from ../../domain/diff. No component imports data.ts or JSON fixture.
Tests use Vitest, Testing Library, user-event; global cleanup already configured. Browser Router wrappers in tests/stories when links require them.
Stories are typed standard CSF objects with default {title,component}, named Fixture {args/render}; no Storybook runtime needed by the fixture gallery. Use actual fixture input imported ONLY in stories from ../../data/fixture.json.
CSS module must preserve source class rules relevant to the component, not copy all Shared CSS. All colors and dimensions use ../.. /tokens/tokens.css variables; no new raw sizes/colors outside tokens.
Do not modify frozen prototypes/pipeline-hifi/src or qa/baseline. Do not edit a neighbor's component or package/config.
