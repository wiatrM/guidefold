import {AnimatePresence,motion} from 'motion/react';
import {CheckCircleIcon} from '@phosphor-icons/react';
import {useMotionGate} from '../useMotionGate';
import css from './SuccessBurst.module.css';

/**
 * Success moment after an import or run finishes (ADR-0049): a check mark and label scale
 * into a brief teal glow, once. No confetti or particles — a moment, not a celebration set
 * piece. Appears without motion under reduced motion, off-screen or a hidden tab.
 */
export function SuccessBurst({show,label,className}:{show:boolean;label:string;className?:string}){
 const gate=useMotionGate<HTMLSpanElement>();
 return <span ref={gate.ref} role="status" data-slot="success-burst" className={[css.wrap,className].filter(Boolean).join(' ')}>
  <AnimatePresence>
   {show&&<motion.span key="burst" className={css.burst}
    initial={gate.active?{opacity:0,scale:0.6}:false}
    animate={{opacity:1,scale:1}}
    exit={{opacity:0}}
    transition={{duration:gate.active?0.32:0,ease:[0.16,1,0.3,1]}}>
    <span aria-hidden="true" className={css.icon}><CheckCircleIcon weight="fill"/></span>
    <span>{label}</span>
   </motion.span>}
  </AnimatePresence>
 </span>;
}
