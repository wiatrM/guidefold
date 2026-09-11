import {Reveal} from './Reveal';
import css from './proofgate.module.css';

/** ProofGate section shell, DESIGN.md 3.4. The instrument and its copy land in a later task. */
export function ProofGate(){
 return <section id="proof-gate" className={css.section} aria-labelledby="proof-gate-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Safety boundary'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="proof-gate-title" className={css.heading}>{'Seventy-six harmful rules. Seventy-six refusals.'}</Reveal>
 </section>;
}
