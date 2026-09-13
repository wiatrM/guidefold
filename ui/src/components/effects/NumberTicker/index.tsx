import {useEffect,useMemo,useState} from 'react';
import {motion} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './NumberTicker.module.css';

const DIGIT_HEIGHT_EM=1.1;
const DIGITS=Array.from({length:10},(_,n)=>n);
const EASE_OUT:[number,number,number,number]=[0.16,1,0.3,1];

/**
 * Number ticker for metrics (ADR-0049). Each digit rolls into place once the ticker enters
 * view, staggered left to right; a screen reader gets the plain formatted number, the rolling
 * glyphs are aria-hidden. Reduced motion, off-screen or a hidden tab skip the roll and show
 * the final digits directly (useMotionGate).
 */
export function NumberTicker({value,pad,prefix,suffix,locale,className}:{value:number;pad?:number;prefix?:string;suffix?:string;locale?:boolean;className?:string}){
 const gate=useMotionGate<HTMLSpanElement>();
 const [armed,setArmed]=useState(false);
 useEffect(()=>{if(gate.visible)setArmed(true);},[gate.visible]);
 const rounded=Math.round(value);
 const text=useMemo(()=>{
  const formatted=locale?rounded.toLocaleString():String(rounded);
  return pad?formatted.padStart(pad,'0'):formatted;
 },[rounded,pad,locale]);
 const readable=(prefix??'')+text+(suffix??'');
 const chars=text.split('');
 return <span ref={gate.ref} className={[css.ticker,className].filter(Boolean).join(' ')} data-slot="number-ticker">
  <span className="sr-only">{readable}</span>
  <span aria-hidden="true" className={css.glyphs}>
   {prefix&&<span>{prefix}</span>}
   {chars.map((char,i)=>/\d/.test(char)
    ?<Digit key={chars.length-1-i} digit={Number(char)} armed={armed} reduced={gate.reduced} delay={(chars.length-1-i)*0.04}/>
    :<span key={'sep-'+i}>{char}</span>)}
   {suffix&&<span>{suffix}</span>}
  </span>
 </span>;
}

function Digit({digit,armed,reduced,delay}:{digit:number;armed:boolean;reduced:boolean;delay:number}){
 return <span className={css.digit}>
  <motion.span className={css.column} initial={{y:'0em'}} animate={{y:(-(armed?digit:0)*DIGIT_HEIGHT_EM)+'em'}}
   transition={reduced?{duration:0}:{duration:0.7,delay,ease:EASE_OUT}}>
   {DIGITS.map(n=><span key={n} className={css.glyph}>{n}</span>)}
  </motion.span>
 </span>;
}
