import css from './landing.module.css';

/**
 * Where a rule applies, drawn as the scope ladder it actually is: the organisation at
 * the top, one service at the bottom, and the real skills that live at each level.
 *
 * It replaces the animated three-dimensional pyramid, which never showed either the
 * organisation or a single skill name. Everything here is text and one bar per row, so
 * the structure survives with no JavaScript, no canvas and no motion.
 *
 * Every scope and skill name below is read from the bundled Meridian example repository
 * at `examples/monorepo`; nothing is invented for the page.
 */
const levels = [
 {
  scope: 'meridian',
  indent: 0,
  reach: 'every folder',
  skills: ['security-baseline', 'release-process', 'monorepo-conventions'],
 },
 {
  scope: 'atlas',
  indent: 1,
  reach: 'one platform',
  skills: ['atlas-api-conventions'],
 },
 {
  scope: 'atlas / identity',
  indent: 2,
  reach: 'one component',
  skills: ['rbac-policies', 'legacy-session-auth'],
 },
 {
  scope: 'atlas / identity / turnstile',
  indent: 3,
  reach: 'one service',
  skills: ['postgres-auth', 'turnstile-oncall-runbook'],
 },
];

export function ScopePyramid(){
 return <div className={css.scope}>
  <h3 className={css.scopeTitle}>Every rule has a scope</h3>
  <p className={css.scopeLede}>An organisation keeps rules at more than one level. The scope decides where each one applies, so a service rule never becomes advice for the whole company.</p>
  <ol className={css.scopeList}>
   {levels.map((level)=><li key={level.scope} className={css.scopeLevel} data-indent={level.indent}>
    <span className={css.scopeBar} aria-hidden="true"/>
    <div className={css.scopeHead}>
     <code className={css.scopePath}>{level.scope}</code>
     <span className={css.scopeReach}>{level.reach}</span>
    </div>
    <ul className={css.scopeSkills}>
     {level.skills.map((skill)=><li key={skill} className={css.scopeSkill}>{skill}</li>)}
    </ul>
   </li>)}
  </ol>
  <p className={css.scopeCaption}>Working in turnstile, an agent can see all four levels, general first. Working in another service, the turnstile rules are not offered at all. Scopes and skill names come from the Meridian example repository in this project.</p>
 </div>;
}
