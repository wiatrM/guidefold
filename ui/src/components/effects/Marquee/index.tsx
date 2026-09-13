import type {ReactNode} from 'react';
import {useMotionGate} from '../useMotionGate';
import css from './Marquee.module.css';

/**
 * A scrolling row, decorative (ADR-0049): a track duplicated once so the loop is seamless,
 * paused on hover or focus so a reader can stop it to read or click an item. Static, single
 * copy, under reduced motion, off-screen or a hidden tab.
 */
export function Marquee({children,className,ariaLabel}:{children:ReactNode[];className?:string;ariaLabel?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 return <div ref={gate.ref} role={ariaLabel?'group':undefined} aria-label={ariaLabel} data-slot="marquee"
  className={[css.viewport,className].filter(Boolean).join(' ')}>
  <div className={[css.track,gate.active?css.scroll:''].filter(Boolean).join(' ')}>
   <div className={css.set}>{children}</div>
   <div className={css.set} aria-hidden="true">{gate.active?children:null}</div>
  </div>
 </div>;
}
