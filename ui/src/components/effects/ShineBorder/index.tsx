import {useEffect,useState,type ReactNode} from 'react';
import {motion,AnimatePresence} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './ShineBorder.module.css';

/**
 * Animated card/panel border #2 (ADR-0049): one light pass along the top edge, replayed when
 * `trigger` changes (e.g. an import finishing) or looped when `repeat` is set. Distinct from
 * BorderBeam's continuous rotation: this is a moment, not an idle state. Static hairline, no
 * sweep, under reduced motion, off-screen or a hidden tab.
 */
export function ShineBorder({children,trigger,repeat=false,className}:{children:ReactNode;trigger?:unknown;repeat?:boolean;className?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 const [pass,setPass]=useState(0);
 useEffect(()=>{if(trigger!==undefined)setPass(p=>p+1);},[trigger]);
 return <div ref={gate.ref} className={[css.frame,className].filter(Boolean).join(' ')} data-slot="shine-border">
  <span aria-hidden="true" className={css.edge}/>
  {gate.active&&<AnimatePresence>
   <motion.span key={pass} aria-hidden="true" className={css.sweep} initial={{x:'-100%'}} animate={{x:'100%'}}
    transition={{duration:0.9,ease:'easeOut',repeat:repeat?Infinity:0,repeatDelay:repeat?2:0}}/>
  </AnimatePresence>}
  <div className={css.content}>{children}</div>
 </div>;
}
