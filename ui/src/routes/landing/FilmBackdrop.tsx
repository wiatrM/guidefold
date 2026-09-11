import {useCallback,useEffect,useRef,useState} from 'react';
import {useDocumentProgress} from './scroll';
import css from './landing.module.css';

/**
 * The film behind the whole page. One continuous camera flight through the map world,
 * with the playhead tied to scroll position rather than to a clock, so the visitor drives
 * it and it runs backwards exactly as it runs forwards.
 *
 * Poster first and always: the still is the LCP element, it is never removed, and every
 * failure path (reduced motion, Save-Data, a decoder error, a file that is not on disk,
 * no `canplay` inside eight seconds) simply leaves the poster in place with no layout
 * shift. `data-film` on the page root tells the section planes to step aside once the
 * film is actually running, so two backgrounds never compete.
 *
 * Seeking is damped and rate limited: the playhead eases toward the scroll target and is
 * only written when it has moved more than a frame, which keeps a scrub from queueing a
 * seek per rAF tick.
 *
 * The mapping from scroll to playhead is the anchor map (DESIGN.md 3.0): whole-document
 * progress is not stretched linearly over the duration, because the beats are not evenly
 * spaced in scroll. Each section contributes one measured anchor and the playhead is
 * interpolated piecewise-linearly between them, so a chapter that eats a lot of scroll
 * still gets only its own slice of film.
 */
const TERMINAL = 10.04;
const DURATION_FALLBACK = TERMINAL;
const FRAME = 1 / 24;

export type Anchor = {id:string;second:number;at:number};

/**
 * The nine sections in DOM order with the playhead second each one opens on
 * (DESIGN.md 3.0, "Implemented anchors"). Seconds are fixed; the scroll positions they
 * sit at are measured. Two beats are literal and must not be re-assigned: the four-card
 * fan belongs to `how-it-works`, the tier-edge crossing to `proof-gate`.
 *
 * Where a second differs from DESIGN.md's table it is because the film's own cut is the
 * truth and the design second was a target: an anchor is the cut plus ~0.09 s, which is
 * wider than the one-frame deadband the delta gate leaves behind, so the section opens on
 * its own shot rather than on the last frame of the previous one.
 */
export const FILM_ANCHORS:readonly Omit<Anchor,'at'>[] = [
 {id:'hero',second:0},               // table above the clouds, the drawn orange route, sunrise window
 {id:'extraction',second:1.4},       // the fall into the terrain: contour valley, teal rings, map sheet lifting
 {id:'how-it-works',second:4.3},     // four cream cards standing in a fan around one lit orange marker (cut 4.2083)
 {id:'proof-gate',second:5.75},      // the route crossing a plateau edge, teal rim light on the boundary
 {id:'telemetry',second:6.8},        // stacked plateaus held wide, cubes across the lower tiers
 {id:'research-results',second:7.8}, // upper plateau, sparse cubes, route arriving at the top tier
 {id:'availability',second:8.6},     // pull back begins, the terrain reads as a map again
 {id:'waitlist',second:9.1},         // the map rising into its folds
 {id:'questions',second:9.7},        // the folded map on the desk beside the wordmark
] as const;

/**
 * Piecewise-linear interpolation over the measured anchors. Pure, monotonic while the
 * anchors are, and exact in reverse, which is what makes the scrub reversible: the same
 * scroll position always yields the same second, whichever direction it was reached from.
 * Outside the measured range it clamps to the end anchors rather than extrapolating.
 */
export function playheadAt(progress:number,anchors:readonly Anchor[]):number{
 if(!anchors.length)return 0;
 if(progress<=anchors[0].at)return anchors[0].second;
 const last=anchors[anchors.length-1];
 if(progress>=last.at)return last.second;
 for(let i=1;i<anchors.length;i++){
  const a=anchors[i-1],b=anchors[i];
  if(progress<=b.at){
   const span=b.at-a.at;
   return span<=0?b.second:a.second+((progress-a.at)/span)*(b.second-a.second);
  }
 }
 return last.second;
}

/**
 * Builds the anchor table from the live section rects. Never from hardcoded scroll
 * fractions: a table of fractions would drift the moment copy length changed. A section
 * whose element is missing is dropped and the interpolation simply spans the gap.
 *
 * The nine anchors are beat *starts*, so the ninth would otherwise hold 9.7 for the whole
 * of the last section and the terminal frame would never play. One synthetic anchor at
 * progress 1 carries the terminal second, which is the film's real duration once metadata
 * has arrived (DESIGN.md 3.0: the last section holds the terminal frame exactly).
 */
function measure(terminal:number):Anchor[]{
 const scrollable=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);
 const anchors=FILM_ANCHORS
  .map(a=>{const el=document.getElementById(a.id);return el?{...a,at:Math.min(1,Math.max(0,(el.getBoundingClientRect().top+window.scrollY)/scrollable))}:null;})
  .filter((a):a is Anchor=>a!==null);
 if(!anchors.length)return anchors;
 const last=anchors[anchors.length-1];
 if(last.at>=1)last.second=terminal;
 else anchors.push({id:'terminal',second:terminal,at:1});
 return anchors;
}

export function FilmBackdrop(){
 const media = useRef<HTMLVideoElement>(null);
 const film = useRef<HTMLDivElement>(null);
 const target = useRef(0);
 const current = useRef(0);
 const raf = useRef(0);
 const anchorsRef = useRef<Anchor[]>([]);
 const [allowed,setAllowed] = useState(false);
 const [decoded,setDecoded] = useState(false);
 const [failed,setFailed] = useState(false);
 const [ready,setReady] = useState(false);
 const [paused,setPaused] = useState(false);

 useEffect(()=>{
  const query = typeof window.matchMedia==='function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  const connection = (navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
  const update = ()=>setAllowed(!query?.matches && connection?.saveData!==true);
  update();
  query?.addEventListener('change',update);
  return ()=>query?.removeEventListener('change',update);
 },[]);

 const mounted = allowed && decoded && !failed;

 // Fail closed: no `canplay` inside eight seconds is treated exactly like a decoder error.
 useEffect(()=>{
  if(!mounted||ready)return;
  const timer = window.setTimeout(()=>setFailed(true),8000);
  return ()=>window.clearTimeout(timer);
 },[mounted,ready]);

 /**
  * Rects are read here and only here, never inside the rAF step: DESIGN.md 5 forbids
  * `getBoundingClientRect` outside the batched sampler. Recomputed on resize, on rotation,
  * once the fonts have landed, when the film's own metadata arrives, and whenever the
  * document's own box changes size — the pinned chapter and the reveals both settle their
  * heights after first paint, and an anchor table measured before that is simply wrong.
  */
 const remeasure = useCallback(()=>{
  const node=media.current;
  const duration=node&&Number.isFinite(node.duration)&&node.duration>0?node.duration:DURATION_FALLBACK;
  anchorsRef.current=measure(duration);
 },[]);

 useEffect(()=>{
  if(!mounted)return;
  remeasure();
  let frame=0;
  const schedule=()=>{if(!frame)frame=requestAnimationFrame(()=>{frame=0;remeasure();});};
  window.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('orientationchange',schedule,{passive:true});
  let live=true;
  document.fonts?.ready.then(()=>{if(live)schedule();}).catch(()=>{});
  const observer=typeof ResizeObserver!=='undefined'?new ResizeObserver(schedule):null;
  observer?.observe(document.body);
  return ()=>{
   live=false;
   if(frame)cancelAnimationFrame(frame);
   window.removeEventListener('resize',schedule);
   window.removeEventListener('orientationchange',schedule);
   observer?.disconnect();
  };
 },[mounted,remeasure]);

 useDocumentProgress((progress)=>{target.current=playheadAt(progress,anchorsRef.current);},mounted&&ready);

 /**
  * DESIGN.md 4.4: the film stops costing anything while the tab is hidden, while the film
  * layer is off screen and while the demo dialog is open. The film is scrubbed and never
  * played, so the saving is in cancelling the rAF; `pause()` is the belt to that braces.
  */
 useEffect(()=>{
  if(!mounted)return;
  let hidden=document.visibilityState==='hidden';
  let offscreen=false;
  let dialog=document.querySelector('[role="dialog"]')!==null;
  const apply=()=>setPaused(hidden||offscreen||dialog);
  const onVisibility=()=>{hidden=document.visibilityState==='hidden';apply();};
  document.addEventListener('visibilitychange',onVisibility);
  const element=film.current;
  const seen=element&&typeof IntersectionObserver!=='undefined'
   ?new IntersectionObserver(entries=>{for(const entry of entries)offscreen=!entry.isIntersecting;apply();},{rootMargin:'0px'})
   :null;
  if(element&&seen)seen.observe(element);
  const dialogs=typeof MutationObserver!=='undefined'
   ?new MutationObserver(()=>{
     const open=document.querySelector('[role="dialog"]')!==null;
     if(open!==dialog){dialog=open;apply();}
    })
   :null;
  dialogs?.observe(document.body,{childList:true,subtree:true});
  apply();
  return ()=>{
   document.removeEventListener('visibilitychange',onVisibility);
   seen?.disconnect();
   dialogs?.disconnect();
  };
 },[mounted]);

 // One eased writer, started only once the film can actually seek.
 useEffect(()=>{
  if(!mounted||!ready)return;
  const node = media.current;
  if(!node)return;
  if(paused){try{node.pause();}catch{/* a scrubbed film is never playing anyway */}return;}
  const step = ()=>{
   const duration = Number.isFinite(node.duration)&&node.duration>0 ? node.duration : DURATION_FALLBACK;
   const wanted = Math.min(target.current,duration);
   current.current += (wanted-current.current) * 0.14;
   if(Math.abs(current.current-node.currentTime) > FRAME && !node.seeking){
    try{node.currentTime = current.current;}catch{setFailed(true);}
   }
   raf.current = requestAnimationFrame(step);
  };
  raf.current = requestAnimationFrame(step);
  return ()=>cancelAnimationFrame(raf.current);
 },[mounted,ready,paused]);

 useEffect(()=>{
  const root = document.documentElement;
  if(mounted&&ready)root.dataset.film='on';
  else delete root.dataset.film;
  return ()=>{delete root.dataset.film;};
 },[mounted,ready]);

 return <div ref={film} className={css.film} aria-hidden="true">
  <img
   className={css.filmPoster}
   src="/assets/landing/hero-poster.webp"
   alt=""
   width="1920"
   height="1080"
   fetchPriority="high"
   ref={node=>{if(node?.complete&&node.naturalWidth>0)setDecoded(true);}}
   onLoad={()=>setDecoded(true)}
   onError={event=>{event.currentTarget.hidden=true;}}
  />
  {mounted&&<video
   ref={media}
   className={css.filmVideo}
   data-ready={ready||undefined}
   muted
   playsInline
   preload="auto"
   onLoadedMetadata={remeasure}
   onLoadedData={()=>setReady(true)}
   onError={()=>setFailed(true)}
  >
   <source src="/assets/landing/hero-flight.mp4" type="video/mp4"/>
   <source src="/assets/landing/hero-flight.webm" type="video/webm"/>
  </video>}
  <div className={css.filmScrim}/>
 </div>;
}
