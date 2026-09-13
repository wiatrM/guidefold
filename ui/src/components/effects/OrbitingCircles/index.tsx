import type {ReactNode} from 'react';
import {useMotionGate} from '../useMotionGate';
import css from './OrbitingCircles.module.css';

/**
 * Decorative orbit around a central icon (ADR-0049), e.g. connected sources around a
 * repository. Up to six satellites, positioned at fixed angles; the ring rotates and each
 * satellite counter-rotates so its own icon stays upright. Static, evenly spaced, no
 * rotation, under reduced motion, off-screen or a hidden tab.
 */
export function OrbitingCircles({center,items,className}:{center:ReactNode;items:ReactNode[];className?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 const satellites=items.slice(0,6);
 return <div ref={gate.ref} data-slot="orbiting-circles" className={[css.field,className].filter(Boolean).join(' ')}>
  <div className={css.center}>{center}</div>
  <div aria-hidden="true" className={[css.orbit,gate.active?css.spin:''].filter(Boolean).join(' ')}>
   {satellites.map((item,i)=><div key={i} className={css.satellite} data-index={i+1}>
    <div className={[css.satelliteInner,gate.active?css.counterSpin:''].filter(Boolean).join(' ')}>{item}</div>
   </div>)}
  </div>
 </div>;
}
