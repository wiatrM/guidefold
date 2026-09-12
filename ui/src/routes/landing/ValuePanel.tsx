import {useEffect,useRef,useState} from 'react';
import {useRevealed} from './Reveal';
import css from './value.module.css';

/**
 * The value panel, SPEC v3 "The value panel". Every block on this page ends by answering
 * what the reader gets, and the owner's note on the first attempt was that a small grey
 * paragraph reads as filler. So there is exactly one implementation of that answer and it
 * is a panel: glass surface, a teal rule down its left edge, the label in the accent
 * colour and the sentence at the lede size in display ink.
 *
 * The label is part of the sentence rather than a badge above it, so the rendered text
 * reads exactly as the spec writes it and a screen reader hears one sentence.
 *
 * Entrance, once, when 30 % of the panel is in view — the same threshold and the same
 * shared observer pool the page's P3 panels already use, so this adds no observer. The
 * rule draws top to bottom, the label follows at 80 ms, the sentence lifts at 160 ms, and
 * the rule's glow settles after 900 ms. `data-value-ready` is written in an effect, so
 * every entrance rule in the stylesheet applies only once the observer really exists: a
 * missed callback or a platform without IntersectionObserver leaves the finished panel.
 * Under reduced motion the durations are zero in tokens.css and `useRevealed` reports
 * entered immediately, which is the resting state.
 */
const PREFIX='What you get: ';

export function ValuePanel({children}:{children:string}){
 const ref=useRef<HTMLDivElement>(null);
 const entered=useRevealed(ref);
 const [armed,setArmed]=useState(false);
 useEffect(()=>{setArmed(true);},[]);
 const body=children.startsWith(PREFIX)?children.slice(PREFIX.length):children;

 return <div ref={ref} className={css.panel}
  data-value-ready={armed?'true':undefined}
  data-value-entered={entered?'true':undefined}>
  <span className={css.rule} aria-hidden="true"/>
  <p className={css.line}>
   <span className={css.label}>{PREFIX}</span>
   <span className={css.sentence}>{body}</span>
  </p>
 </div>;
}
