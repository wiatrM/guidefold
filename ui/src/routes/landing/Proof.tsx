import {useRef} from 'react';
import {useReducedMotion} from 'motion/react';
import evidence from '../../data/research-evidence.json';
import {Reveal,useRevealed} from './Reveal';
import {formatDelta} from './format';
import {ValuePanel} from './ValuePanel';
import {NumberTicker} from '../../components/spectrumui/number-ticker';
import css from './proof.module.css';

/**
 * Proof, SPEC v3 screen 7. Two figures, one small-print line each, one link to where the
 * precise labels live. Both figures are read from `src/data/research-evidence.json` — the
 * same mirror the research document publishes — so a refreshed run moves the page and no
 * number is ever typed into this file.
 *
 * The digits roll once on reveal (P4 Count). `NumberTicker` rounds to an integer, so the
 * two-decimal delta is carried as hundredths and unscaled by `format`. Both figures are
 * rendered at their final value without JavaScript: the ticker replaces a complete
 * sentence, never a placeholder.
 */
const gate=evidence.proof_gate.matrix;
const delta=evidence.vs_flat.recall10.delta_pp;
const centipp=(value:number)=>Math.round(value*100);
const formatPp=(value:number)=>(value/100).toFixed(2);

export function Proof(){
 const figuresRef=useRef<HTMLDivElement>(null);
 const revealed=useRevealed(figuresRef);
 const reducedMotion=useReducedMotion();
 // NumberTicker calls motion/react's useInView on mount, which throws where there is no
 // IntersectionObserver (jsdom, and any platform without it). The static branch below is
 // already the final sentence, so that is the degradation.
 const canTick=typeof IntersectionObserver!=='undefined'&&!reducedMotion;

 // The spec gives this band two figures, two small-print lines, a value line and a link,
 // and nothing else — so it carries no heading, and the landmark takes its name from the
 // label rather than from copy invented to fill the slot.
 return <section id="proof" className={css.section} aria-label="Proof">
  <div ref={figuresRef} className={css.figures}>
   <Reveal pattern="p1" as="div" className={css.figure}>
    <p className={css.figureLine}>
     {revealed&&canTick
      ?<NumberTicker value={gate.harmful_mutations} startOnView={false} className={css.count}/>
      :<span className={css.count}>{gate.harmful_mutations}</span>}
     {` of ${gate.harmful_asked} poisoned rules refused.`}
    </p>
    <p className={css.small}>{'Sample repository, September 2026.'}</p>
   </Reveal>
   <Reveal pattern="p1" as="div" index={1} className={css.figure}>
    <p className={css.figureLine}>
     {revealed&&canTick
      ?<NumberTicker value={centipp(delta)} format={formatPp} prefix="+" startOnView={false} className={css.count}/>
      :<span className={css.count}>{formatDelta(delta)}</span>}
     {' pp recall over flat search.'}
    </p>
    <p className={css.small}>{'SRA-Bench, September 2026.'}</p>
   </Reveal>
  </div>
  <ValuePanel>{'What you get: numbers you can check, not promises.'}</ValuePanel>
  <a className={css.textLink} href="/docs/">{'Read the numbers and how we got them'}</a>
 </section>;
}
