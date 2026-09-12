import {Reveal,RevealGroup} from './Reveal';
import {ValuePanel} from './ValuePanel';
import css from './why.module.css';

/**
 * Why teams install it, SPEC v3 screen 2. Three roles, one sentence each, hairlines
 * between and nothing else: no icons, no cards, no third column added for symmetry. A
 * role and what it gets is a term and its description, so the rows are a `dl` rather than
 * a list of paragraphs pretending to be one.
 */
const ROLES=[
 {role:'Platform teams',
  gets:'Keep every rule of the monorepo in one place and wire it into Claude Code, Codex, Copilot and Gemini CLI in one afternoon.'},
 {role:'Tech leads and rule owners',
  gets:'See what a rule change collides with before it merges, and approve what moves up to the whole organisation.'},
 {role:'Developers',
  gets:'Start every task with the four rules that matter for that folder, without asking anyone.'},
] as const;

export function Why(){
 return <section id="why" className={css.section} aria-labelledby="why-title">
  <div className={css.copy}>
   <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Why install it'}</Reveal>
   <Reveal pattern="p1" as="h2" index={1} id="why-title" className={css.heading}>
    {'One place for every rule, wired into every agent.'}
   </Reveal>
  </div>

  <RevealGroup pattern="p1" as="dl" className={css.roles}>
   {ROLES.map(item=>
    <div key={item.role} className={css.role}>
     <dt className={css.roleName}>{item.role}</dt>
     <dd className={css.roleGets}>{item.gets}</dd>
    </div>)}
  </RevealGroup>

  <div className={css.value}>
   <ValuePanel>{'What you get: one source of rules for people and agents, and no more copy-pasted conventions drifting between repos.'}</ValuePanel>
  </div>
 </section>;
}
