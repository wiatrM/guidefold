import {Reveal} from './Reveal';
import css from './extraction.module.css';

/** Extraction section shell, DESIGN.md 3.2. The instrument and its copy land in a later task. */
export function Extraction(){
 return <section id="extraction" className={css.section} aria-labelledby="extraction-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Where the rules come from'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="extraction-title" className={css.heading}>{"One team's fix becomes everyone's rule."}</Reveal>
 </section>;
}
