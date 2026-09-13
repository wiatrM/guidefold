import type {ReactNode} from 'react';
import {AnimatePresence,motion} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './AnimatedList.module.css';

export interface AnimatedListItem{id:string;content:ReactNode}

/**
 * Animated list for event logs and repository lists (ADR-0049): a newly prepended item
 * enters with a small rise and fade instead of appearing mid-scroll unannounced; removed
 * items collapse instead of jumping the rows below them. Renders as a plain <ul> with no
 * animation under reduced motion, off-screen or a hidden tab.
 */
export function AnimatedList({items,className,ariaLabel}:{items:AnimatedListItem[];className?:string;ariaLabel?:string}){
 const gate=useMotionGate<HTMLUListElement>();
 return <ul ref={gate.ref} aria-label={ariaLabel} data-slot="animated-list" className={[css.list,className].filter(Boolean).join(' ')}>
  <AnimatePresence initial={false}>
   {items.map(item=><motion.li key={item.id} className={css.item}
    layout={gate.active}
    initial={gate.active?{opacity:0,y:-8}:false}
    animate={{opacity:1,y:0}}
    exit={gate.active?{opacity:0,height:0}:{opacity:0}}
    transition={{duration:gate.active?0.28:0,ease:'easeOut'}}>
    {item.content}
   </motion.li>)}
  </AnimatePresence>
 </ul>;
}
