import type {ReactNode} from 'react';
import {motion} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './HeaderGlow.module.css';

/**
 * View header treatment (ADR-0049): a soft halo behind the page's IconTile plus a single
 * light sweep across it on mount. Wrap the IconTile a route already renders; this adds no
 * layout, only the decorative surface behind and over it. Static halo, no sweep, under
 * reduced motion or while off-screen/tab-hidden (useMotionGate).
 */
export function HeaderGlow({children,tone='system',className}:{children:ReactNode;tone?:'system'|'human';className?:string}){
 const {ref,active}=useMotionGate<HTMLSpanElement>();
 return <span ref={ref} data-slot="header-glow" data-tone={tone} className={[css.wrap,tone==='human'?css.human:'',className].filter(Boolean).join(' ')}>
  <span aria-hidden="true" className={css.halo}/>
  {active&&<motion.span aria-hidden="true" className={css.sweep} initial={{x:'-120%',opacity:0}} animate={{x:'220%',opacity:[0,1,0]}} transition={{duration:0.9,ease:'easeOut'}}/>}
  <span className={css.content}>{children}</span>
 </span>;
}
