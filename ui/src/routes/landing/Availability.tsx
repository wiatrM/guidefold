import {Reveal,RevealGroup} from './Reveal';
import css from './availability.module.css';

/**
 * Availability, DESIGN.md 3.7. Two facts, so two statements and no third for symmetry.
 * Both statements are protected and were moved here verbatim, each with its detail
 * sentence in its own inline element so it stays independently addressable; the band's
 * own "Try the open-source version" link is removed per copy.md section 3, and section 3
 * plus the footer keep theirs.
 */
export function Availability(){
 return <section id="availability" className={css.section} aria-labelledby="availability-title">
  <Reveal pattern="p1" as="h2" id="availability-title" className={css.heading}>{'Clone it today. It is open.'}</Reveal>
  <div className={css.body}>
   <RevealGroup pattern="p1" as="div" className={css.availabilityStatements}>
    <p><strong>Open source today.</strong> <span>CLI and retrieval service.</span></p>
    <p><strong>Paid hosting is planned.</strong> <span>Sign up for availability updates.</span></p>
   </RevealGroup>
   <Reveal pattern="p1" as="p" index={2} className={css.supporting}>{'Claude Code, Codex, Copilot and Gemini CLI read the same rules, Git stays the source of truth, and the registry is a build artifact you can rebuild.'}</Reveal>
   <Reveal pattern="p1" as="div" index={3} className={css.availabilityLinks}>
    <a className={css.textLink} href="/docs/">Read the docs</a>
   </Reveal>
  </div>
 </section>;
}
