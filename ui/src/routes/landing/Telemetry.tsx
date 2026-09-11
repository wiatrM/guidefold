import {Reveal} from './Reveal';
import css from './telemetry.module.css';

/** Telemetry section shell, DESIGN.md 3.5. The instrument and its copy land in a later task. */
export function Telemetry(){
 return <section id="telemetry" className={css.section} aria-labelledby="telemetry-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'For the organisation'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="telemetry-title" className={css.heading}>{'You see which rule failed, and why.'}</Reveal>
 </section>;
}
