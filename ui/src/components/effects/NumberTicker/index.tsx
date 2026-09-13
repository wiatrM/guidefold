import {useEffect,useLayoutEffect,useMemo,useState} from 'react';
import {motion} from 'motion/react';
import {useMotionGate} from '../useMotionGate';
import css from './NumberTicker.module.css';

const DIGIT_HEIGHT_EM=1.1;
const DIGITS=Array.from({length:10},(_,n)=>n);
const EASE_OUT:[number,number,number,number]=[0.16,1,0.3,1];
// useLayoutEffect warns during server rendering; the roll decision only matters in a browser.
const useIsoLayoutEffect=typeof window==='undefined'?useEffect:useLayoutEffect;

/**
 * Number ticker for metrics (ADR-0049). The final value is what renders by default: on the
 * server, in print, before the element is scrolled into view, under reduced motion and where
 * IntersectionObserver does not exist. A roll from 0 happens only once the element is actually
 * in the viewport with motion allowed, so no capture or unscrolled reader ever sees a count that
 * is not the real one. A screen reader always gets the plain formatted number; the rolling glyphs
 * are aria-hidden.
 */
export function NumberTicker({value,pad,prefix,suffix,locale,className}:{value:number;pad?:number;prefix?:string;suffix?:string;locale?:boolean;className?:string}){
 const gate=useMotionGate<HTMLSpanElement>();
 const [roll,setRoll]=useState(false);
 const observable=typeof IntersectionObserver==='function';
 // Already on screen at mount: decide before the first paint, so the reader sees 0 → value rather
 // than value → 0 → value.
 useIsoLayoutEffect(()=>{
  const node=gate.ref.current;
  if(!node||!observable||gate.reduced||typeof document==='undefined'||document.hidden)return;
  const rect=node.getBoundingClientRect();
  if(rect.bottom>0&&rect.top<window.innerHeight&&rect.width>0)setRoll(true);
 },[]);
 // Scrolled into view later: roll once, the first time the observer reports it visible.
 useEffect(()=>{if(observable&&gate.active)setRoll(true);},[observable,gate.active]);
 const rounded=Math.round(value);
 const text=useMemo(()=>{
  const formatted=locale?rounded.toLocaleString():String(rounded);
  return pad?formatted.padStart(pad,'0'):formatted;
 },[rounded,pad,locale]);
 const readable=(prefix??'')+text+(suffix??'');
 const chars=text.split('');
 const animate=roll&&!gate.reduced;
 return <span ref={gate.ref} className={[css.ticker,className].filter(Boolean).join(' ')} data-slot="number-ticker" data-rolling={animate||undefined}>
  <span className="sr-only">{readable}</span>
  <span aria-hidden="true" className={css.glyphs}>
   {prefix&&<span>{prefix}</span>}
   {chars.map((char,i)=>/\d/.test(char)
    ?<Digit key={chars.length-1-i} digit={Number(char)} roll={animate} delay={(chars.length-1-i)*0.04}/>
    :<span key={'sep-'+i}>{char}</span>)}
   {suffix&&<span>{suffix}</span>}
  </span>
 </span>;
}

function Digit({digit,roll,delay}:{digit:number;roll:boolean;delay:number}){
 const target=(-digit*DIGIT_HEIGHT_EM)+'em';
 // `key` remounts the column when a roll starts, so it begins at 0 exactly once; until then the
 // column sits on its final digit with no initial animation at all.
 return <span className={css.digit}>
  <motion.span key={roll?'roll':'still'} className={css.column} data-digit={digit}
   initial={roll?{y:'0em'}:{y:target}} animate={{y:target}}
   transition={roll?{duration:0.7,delay,ease:EASE_OUT}:{duration:0}}>
   {DIGITS.map(n=><span key={n} className={css.glyph}>{n}</span>)}
  </motion.span>
 </span>;
}
