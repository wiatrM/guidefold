import {useEffect,useRef,type RefObject} from 'react';

/**
 * The whole page's scroll motion: one rAF, one passive scroll listener, one resize
 * listener and one IntersectionObserver, shared by every registered section.
 *
 * p = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1)
 *
 * `--p` is written straight onto the element, never through React state, and defaults
 * to `.5` in tokens.css so the page is already a correct static composition before the
 * first frame, with JavaScript off, and under reduced motion or Save-Data, where the
 * sampler is never installed at all. `data-p-ready` marks the elements the sampler is
 * actually driving, so CSS can keep a separate resting state for anything whose
 * `--p = .5` evaluation would read as unfinished (the HOW route rule).
 */
/**
 * Source element (the one whose geometry defines progress) to the element the value is
 * written on. They differ when the measured element has many descendants: writing a
 * custom property invalidates style for the whole subtree, so the page's own progress is
 * written onto the fixed background layer, which is the only subtree that consumes it.
 */
const registered=new Map<HTMLElement,HTMLElement>();
const visible=new Set<HTMLElement>();
/** Readers of whole-document progress, driven by the same frame as the section writes. */
const readers=new Set<(progress:number)=>void>();
let observer:IntersectionObserver|null=null;
let frame=0;
let listening=false;

function motionAllowed(){
 if(typeof window==='undefined')return false;
 if(typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return false;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
 return connection?.saveData!==true;
}

function write(element:HTMLElement){
 const height=window.innerHeight||1;
 const rect=element.getBoundingClientRect();
 const p=Math.min(1,Math.max(0,(height-rect.top)/(height+rect.height)));
 (registered.get(element)??element).style.setProperty('--p',p.toFixed(4));
}
function documentProgress(){
 const scrollable=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);
 return Math.min(1,Math.max(0,window.scrollY/scrollable));
}
function sample(){
 frame=0;
 for(const element of visible)write(element);
 if(readers.size){
  const progress=documentProgress();
  for(const reader of readers)reader(progress);
 }
}
function schedule(){if(!frame)frame=requestAnimationFrame(sample);}

function listen(){
 if(listening)return;
 listening=true;
 window.addEventListener('scroll',schedule,{passive:true});
 window.addEventListener('resize',schedule,{passive:true});
}
function stop(){
 if(!listening||readers.size)return;
 listening=false;
 window.removeEventListener('scroll',schedule);
 window.removeEventListener('resize',schedule);
 if(frame){cancelAnimationFrame(frame);frame=0;}
}
function ensureObserver(){
 if(observer||typeof IntersectionObserver==='undefined')return observer;
 observer=new IntersectionObserver(entries=>{
  for(const entry of entries){
   const element=entry.target as HTMLElement;
   const target=registered.get(element)??element;
   if(entry.isIntersecting){visible.add(element);target.dataset.inView='true';}
   // A section that has left the viewport keeps its own clamped resting value,
   // written once, so it never falls back to an ancestor's progress.
   else{visible.delete(element);delete target.dataset.inView;write(element);}
  }
  if(visible.size)schedule();
 },{rootMargin:'0px'});
 return observer;
}

/**
 * Registers an element with the shared sampler. Writes `--p`; returns nothing.
 * `targetRef` receives the value when it should land somewhere other than the measured
 * element, keeping style invalidation off a large subtree.
 */
export function useSectionProgress(ref:RefObject<HTMLElement|null>,targetRef?:RefObject<HTMLElement|null>){
 useEffect(()=>{
  const element=ref.current;
  if(!element||!motionAllowed())return;
  const target=targetRef?.current??element;
  const active=ensureObserver();
  registered.set(element,target);
  target.dataset.pReady='true';
  listen();
  if(active)active.observe(element);
  else{visible.add(element);}
  write(element);
  schedule();
  return()=>{
   active?.unobserve(element);
   registered.delete(element);
   visible.delete(element);
   delete target.dataset.pReady;
   delete target.dataset.inView;
   target.style.removeProperty('--p');
   if(!registered.size){
    stop();
    observer?.disconnect();
    observer=null;
   }
  };
 },[ref,targetRef]);
}

/**
 * Subscribes to whole-document scroll progress, 0 at the top and 1 at the bottom, on the
 * same frame as the section writes. Used by the film backdrop, which turns progress into
 * a playhead position rather than a transform.
 */
export function useDocumentProgress(onProgress:(progress:number)=>void,enabled:boolean){
 const latest=useRef(onProgress);
 latest.current=onProgress;
 useEffect(()=>{
  if(!enabled||!motionAllowed())return;
  const reader=(progress:number)=>latest.current(progress);
  readers.add(reader);
  listen();
  schedule();
  return()=>{
   readers.delete(reader);
   if(!registered.size&&!readers.size){
    stop();
    observer?.disconnect();
    observer=null;
   }
  };
 },[enabled]);
}
