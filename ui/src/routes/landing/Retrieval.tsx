import {Reveal} from './Reveal';
import css from './retrieval.module.css';

/** Retrieval section shell, DESIGN.md 3.3. The instrument and its copy land in a later task. */
export function Retrieval(){
 return <section id="how-it-works" className={css.section} aria-labelledby="retrieval-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'What the agent gets'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="retrieval-title" className={css.heading}>{'Thirty thousand rules. Four reach the agent.'}</Reveal>
 </section>;
}
