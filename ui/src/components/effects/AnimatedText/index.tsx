import {motion} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './AnimatedText.module.css';

/**
 * Animated text reveal (ADR-0049): each word rises and fades in, staggered left to right,
 * once the text enters view. A screen reader gets the plain string; the animated words are
 * aria-hidden. Reduced motion, off-screen or a hidden tab show the finished text directly.
 */
export function AnimatedText({text,className}:{text:string;className?:string}){
 const gate=useMotionGate<HTMLSpanElement>();
 const words=text.split(' ');
 return <span ref={gate.ref} className={[css.text,className].filter(Boolean).join(' ')} data-slot="animated-text">
  <span className="sr-only">{text}</span>
  <span aria-hidden="true" className={css.words}>
   {words.map((word,i)=><motion.span key={i} className={css.word}
    initial={gate.active?{opacity:0,y:10}:false}
    animate={{opacity:1,y:0}}
    transition={{duration:gate.active?0.42:0,delay:gate.active?i*0.032:0,ease:[0.16,1,0.3,1]}}>
    {word}{i<words.length-1?' ':''}
   </motion.span>)}
  </span>
 </span>;
}
