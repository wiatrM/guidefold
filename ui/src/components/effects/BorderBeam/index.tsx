import type {ReactNode} from 'react';
import {useMotionGate} from '../useMotionGate';
import css from './BorderBeam.module.css';

/**
 * Animated card/panel border #1 (ADR-0049): a conic beam travels continuously around a 1px
 * ring. Wrap a Panel or card's content; the ring sits outside the content box and never
 * changes layout. Frozen (not removed) under reduced motion, off-screen or a hidden tab, so
 * the ring still reads as a border rather than flashing away.
 */
export function BorderBeam({children,active=true,className}:{children:ReactNode;active?:boolean;className?:string}){
 const gate=useMotionGate<HTMLDivElement>(active);
 return <div ref={gate.ref} className={[css.frame,className].filter(Boolean).join(' ')} data-slot="border-beam">
  <span aria-hidden="true" className={css.mask}>
   <span data-spin={gate.active||undefined} className={[css.spinner,gate.active?css.spin:''].filter(Boolean).join(' ')}/>
  </span>
  <div className={css.content}>{children}</div>
 </div>;
}
