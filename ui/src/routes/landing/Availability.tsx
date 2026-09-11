import {Reveal} from './Reveal';
import css from './availability.module.css';

/**
 * Availability, DESIGN.md 3.7. Two facts, so two statements and no third for symmetry.
 * Both statements are protected and were moved here verbatim; the band's own
 * "Try the open-source version" link is removed per copy.md section 3, and section 3
 * plus the footer keep theirs. A later task restyles the band.
 */
export function Availability(){
 return <section id="availability" className={css.section} aria-labelledby="availability-title">
  <Reveal pattern="p1" as="h2" id="availability-title" className={css.heading}>{'Clone it today. It is open.'}</Reveal>
  <div className={css.availabilityStatements}>
     <p><strong>Open source today.</strong> CLI and retrieval service.</p>
     <p><strong>Paid hosting is planned.</strong> Sign up for availability updates.</p>
  </div>
  <div className={css.availabilityLinks}>
     <a className={css.textLink} href="/docs/">Read the docs</a>
  </div>
 </section>;
}
