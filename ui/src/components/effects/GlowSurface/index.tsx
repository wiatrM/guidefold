import type {PointerEvent,ReactNode} from 'react';
import {useMotionGate} from '../useMotionGate';
import css from './GlowSurface.module.css';

/**
 * Pointer-tracked spotlight for a panel or card on hover (ADR-0049). The glow position is
 * written imperatively to the element's own --effect-pointer-x/-y (declared with a static
 * default in tokens.css, same pattern as Base UI's --collapsible-panel-height), so no React
 * re-render happens per pointer move. Desktop pointers only; disabled under reduced motion.
 */
export function GlowSurface({children,tone='system',className}:{children:ReactNode;tone?:'system'|'human';className?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 const onPointerMove=(event:PointerEvent<HTMLDivElement>)=>{
  if(!gate.active||event.pointerType==='touch')return;
  const rect=event.currentTarget.getBoundingClientRect();
  const x=((event.clientX-rect.left)/rect.width)*100;
  const y=((event.clientY-rect.top)/rect.height)*100;
  event.currentTarget.style.setProperty('--effect-pointer-x',x+'%');
  event.currentTarget.style.setProperty('--effect-pointer-y',y+'%');
 };
 return <div ref={gate.ref} onPointerMove={onPointerMove} data-slot="glow-surface"
  className={[css.surface,tone==='human'?css.human:'',className].filter(Boolean).join(' ')}>
  <span aria-hidden="true" className={css.glow}/>
  <div className={css.content}>{children}</div>
 </div>;
}
