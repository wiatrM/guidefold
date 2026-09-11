import {Children,cloneElement,isValidElement,useEffect,useRef,useState,
 type ElementType,type ReactElement,type ReactNode,type RefObject} from 'react';
import css from './reveal.module.css';

/**
 * The page's entrance layer: DESIGN.md 4.1 patterns P1 Lift, P2 Rule draw and P3 Panel
 * settle. P4 Count is the number ticker and is wired in its own chapter; it never runs
 * inside the LCP window, so it is deliberately absent from this file.
 *
 * Base-state discipline: every element's resting state is its final state. The entrance
 * CSS applies only to elements carrying `data-reveal-ready="true"`, which is set in an
 * effect after the observer is installed. A missed callback, a thrown error, reverse
 * scroll, a refresh mid-page or JavaScript off leaves all content visible.
 *
 * Entry is `once`: on intersection the element is marked and unobserved. Leaving the
 * viewport never resets it. DESIGN.md 4.1 marks all three patterns `once`; the reversible
 * effects in 4.2 are scroll-linked and live in scroll.ts, not here.
 *
 * These are CSS transitions driven by data attributes rather than `motion` components, so
 * every value stays in tokens.css and no per-element JavaScript runs during the entrance.
 */
export type RevealPattern='p1'|'p2'|'p3';

/** P1 and P2 fire when the element crosses 22% from the bottom. DESIGN.md 4.1. */
const ENTRANCE_MARGIN='0px 0px -22% 0px';
/** P3 panels wait until 30% of the panel is visible. DESIGN.md 4.1. */
const PANEL_THRESHOLD=0.3;
/** Never more than five staggered items; slot 4 and above share `--stagger-cap`. */
const LAST_SLOT=4;

/** The exact predicate scroll.ts uses, so the whole page enhances or degrades together. */
function motionAllowed(){
 if(typeof window==='undefined')return false;
 if(typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return false;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
 return connection?.saveData!==true;
}

/**
 * One observer per distinct configuration, shared by every element on the page, never one
 * per component. P1 and P2 share the 22% margin, P3 shares the 30% threshold, so the page
 * carries two; `useRevealed` adds at most one per distinct threshold it is asked for.
 */
type Pool={observer:IntersectionObserver;targets:Map<Element,()=>void>};
const pools=new Map<string,Pool>();

function release(key:string){
 const pool=pools.get(key);
 if(!pool)return;
 pool.observer.disconnect();
 pools.delete(key);
}

/**
 * Registers one element for a single entrance. Returns the unregister function; calling it
 * disconnects the shared observer once its last element is gone. Where the platform has no
 * IntersectionObserver the element enters immediately, which is still the final state.
 */
function register(element:Element,key:string,init:IntersectionObserverInit,enter:()=>void){
 if(typeof IntersectionObserver==='undefined'){enter();return()=>{};}
 let pool=pools.get(key);
 if(!pool){
  const targets=new Map<Element,()=>void>();
  const observer=new IntersectionObserver(entries=>{
   for(const entry of entries){
    // `once`: an element that has left the viewport keeps its entered state.
    if(!entry.isIntersecting)continue;
    const onEnter=targets.get(entry.target);
    if(!onEnter)continue;
    targets.delete(entry.target);
    observer.unobserve(entry.target);
    onEnter();
   }
   if(!targets.size)release(key);
  },init);
  pool={observer,targets};
  pools.set(key,pool);
 }
 pool.targets.set(element,enter);
 pool.observer.observe(element);
 return()=>{
  const live=pools.get(key);
  if(!live)return;
  live.targets.delete(element);
  live.observer.unobserve(element);
  if(!live.targets.size)release(key);
 };
}

function entranceConfig(pattern:RevealPattern){
 return pattern==='p3'
  ?{key:'threshold:'+PANEL_THRESHOLD,init:{threshold:PANEL_THRESHOLD}}
  :{key:'margin:'+ENTRANCE_MARGIN,init:{rootMargin:ENTRANCE_MARGIN}};
}

/**
 * Marks the root (or, with a selector, the nodes it names) ready and then entered. The
 * flags are written straight onto the DOM rather than through React state, so a callback
 * outside React's batching never schedules a render.
 */
function useEntrance(ref:RefObject<HTMLElement|null>,pattern:RevealPattern,selector?:string){
 useEffect(()=>{
  const root=ref.current;
  if(!root||!motionAllowed())return;
  const nodes=selector?[...root.querySelectorAll<HTMLElement>(selector)]:[root];
  if(!nodes.length)return;
  const {key,init}=entranceConfig(pattern);
  const unregister=register(root,key,init,()=>{
   for(const node of nodes)node.dataset.revealEntered='true';
  });
  for(const node of nodes)node.dataset.revealReady='true';
  return()=>{
   unregister();
   for(const node of nodes){delete node.dataset.revealReady;delete node.dataset.revealEntered;}
  };
 },[ref,pattern,selector]);
}

function slot(index:number){return String(Math.min(Math.max(index,0),LAST_SLOT));}

export function Reveal({pattern,as,index=0,className,id,children}:{
 pattern:RevealPattern;
 as?:keyof React.JSX.IntrinsicElements;
 index?:number;
 className?:string;
 id?:string;
 children:ReactNode;
}){
 const ref=useRef<HTMLElement|null>(null);
 useEntrance(ref,pattern);
 const As=(as??'div') as ElementType;
 return <As ref={ref} id={id} data-reveal-slot={slot(index)}
  className={[css.reveal,css[pattern],className].filter(Boolean).join(' ')}>{children}</As>;
}

/** What a cloned group child must be able to receive. */
type SlotProps={className?:string;ref?:RefObject<HTMLElement|null>;'data-reveal-slot'?:string};

/**
 * One staggered slot of a group. The pattern class and the slot land on the child itself
 * rather than on a wrapper, because the canonical P3 group is the evidence bento, whose
 * tiles carry their own grid placement (DESIGN.md 3.6: "a tall tile, columns 1-5, two
 * rows"). A wrapper would become the grid item and the placement would be lost. A child
 * that is not an element renders untouched and simply does not animate.
 */
function RevealSlot({pattern,index,children}:{pattern:RevealPattern;index:number;children:ReactNode}){
 const ref=useRef<HTMLElement|null>(null);
 useEntrance(ref,pattern);
 if(!isValidElement(children))return <>{children}</>;
 const child=children as ReactElement<SlotProps>;
 return cloneElement(child,{
  ref,
  'data-reveal-slot':slot(index),
  className:[css.reveal,css[pattern],child.props.className].filter(Boolean).join(' '),
 });
}

export function RevealGroup({pattern,as,className,children}:{
 pattern:RevealPattern;
 as?:keyof React.JSX.IntrinsicElements;
 className?:string;
 children:ReactNode;
}){
 const As=(as??'div') as ElementType;
 return <As className={className}>
  {Children.map(children,(child,i)=><RevealSlot pattern={pattern} index={i}>{child}</RevealSlot>)}
 </As>;
}

/**
 * The hero headline treatment: DESIGN.md 4.1 P1's per-line clip-path mask, chosen over
 * per-character orbit in 7 decision 4 because three animated nodes next to the LCP element
 * is a cost the page can pay and forty is not. The heading is observed once; the mask and
 * the stagger live on the line spans. `aria-label` keeps the accessible name equal to the
 * whole sentence, so a screen reader reads it once rather than line by line.
 */
export function RevealLines({as,id,className,lines,label}:{
 as?:keyof React.JSX.IntrinsicElements;
 id?:string;
 className?:string;
 lines:readonly string[];
 label?:string;
}){
 const ref=useRef<HTMLElement|null>(null);
 useEntrance(ref,'p1','[data-reveal-line]');
 const As=(as??'h1') as ElementType;
 return <As ref={ref} id={id} className={className} aria-label={label??lines.join(' ')}>
  {lines.map((line,i)=>
   <span key={line+String(i)} data-reveal-line="" data-reveal-slot={slot(i)} className={css.p1Line}>{line}</span>)}
 </As>;
}

/**
 * Whether an element has crossed its trigger, for the one case a data attribute cannot
 * serve: a component that must change what it renders on entry rather than how it looks.
 * Reduced motion and Save-Data report `true` immediately, which is the final state.
 */
export function useRevealed(ref:RefObject<HTMLElement|null>,threshold=PANEL_THRESHOLD):boolean{
 const [revealed,setRevealed]=useState(false);
 useEffect(()=>{
  const element=ref.current;
  if(!element)return;
  if(!motionAllowed()){setRevealed(true);return;}
  return register(element,'threshold:'+threshold,{threshold},()=>setRevealed(true));
 },[ref,threshold]);
 return revealed;
}
