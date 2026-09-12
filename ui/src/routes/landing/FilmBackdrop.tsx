import {useCallback,useEffect,useRef,useState} from 'react';
import {useDocumentProgress} from './scroll';
import css from './landing.module.css';

/**
 * The film behind the whole page. One continuous camera flight through the map world,
 * with the playhead tied to scroll position rather than to a clock, so the visitor drives
 * it and it runs backwards exactly as it runs forwards.
 *
 * The field first and always: v3 removed the poster still, so the layer opens on the flat
 * graphite ground `.film` already paints and the film fades up over it once it can seek.
 * Every failure path — reduced motion, Save-Data, a decoder error, a file that is not on
 * disk, no `canplay` inside eight seconds — simply leaves that field on screen with no
 * layout shift and nothing to load. `data-film` on the page root tells the section planes
 * to step aside once the film is actually running, so two backgrounds never compete.
 *
 * Seeking is damped, rate limited and gated on the previous seek having presented; see
 * `SEEK_INTERVAL_MS` and `SEEK_STALL_MS` below for the measured reason.
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
/**
 * R1, the measured seek fix. Scrubbing used to write `currentTime` on every rAF tick that
 * cleared `!node.seeking`: ~66 writes a second into a decoder that was only presenting
 * 21-28 frames a second. Measured on this page, disabling those writes alone removed
 * 41-44 % of all main-thread busy time during a scroll pass and 80 % of paint time, and
 * the film's visible cadence did not change — every extra seek was thrown away.
 *
 * So a write now waits for the previous one to have *presented*, not merely to have
 * stopped seeking, and for a wall clock of `SEEK_INTERVAL_MS` to have passed. The two
 * bound the seek rate from both sides.
 */
const SEEK_INTERVAL_MS = 33;
/**
 * The escape hatch, and it is not optional. A seek that resolves to the frame already on
 * screen fires no `requestVideoFrameCallback` at all; so does a decoder stall or a tab the
 * browser has throttled. A naive in-flight flag would then never clear and the film would
 * freeze permanently — with the layer still mounted, no error fired and `data-film` still
 * `on`, which is worse than the judder and would pass every test in the suite. The flag is
 * therefore cleared by whichever of the frame callback and this timer fires first.
 */
const SEEK_STALL_MS = 100;
/** Below this the damper has arrived and the loop has nothing left to do until the next scroll. */
const SETTLED = FRAME / 4;

type FrameCallbackVideo = HTMLVideoElement & {
 requestVideoFrameCallback?(callback:()=>void):number;
 cancelVideoFrameCallback?(handle:number):void;
};

export type Anchor = {id:string;second:number;at:number};

/**
 * The ten sections of v3 in DOM order with the playhead second each one opens on. Seconds
 * are fixed; the scroll positions they sit at are measured. One beat is still literal and
 * is not re-assigned: the four-card fan at 4.4 belongs to `how-it-works`, which is the
 * chapter about four cards reaching the agent.
 *
 * v3 removed four sections (`proof-gate`, `telemetry`, `research-results`,
 * `availability`) and added three (`why`, `portal`, `under-the-hood`) plus the footer as
 * its own anchor, so the table is rebuilt rather than edited. The seconds of the sections
 * that stayed are unchanged where the shot still fits — hero 0, extraction 1.4,
 * how-it-works 4.4 — and the seconds freed by the removed sections are redistributed over
 * the new ones so the film still spans the whole page end to end. The tier-edge crossing
 * that used to open `proof-gate` at 5.85 now opens `under-the-hood`; that reassignment is
 * deliberate and recorded in DESIGN.md rather than left to read as a stale comment.
 */
export const FILM_ANCHORS:readonly Omit<Anchor,'at'>[] = [
 {id:'hero',second:0},               // table above the clouds, the drawn orange route, sunrise window
 {id:'why',second:0.7},              // the first push towards the terrain, horizon still wide
 {id:'extraction',second:1.4},       // the fall into the terrain: contour valley, teal rings, map sheet lifting
 {id:'portal',second:3.1},           // the sheet settling over the valley, tiers reading as one surface
 {id:'how-it-works',second:4.4},     // four cream cards standing in a fan around one lit orange marker (cut 4.2083)
 {id:'under-the-hood',second:5.85},  // the route crossing a plateau edge, teal rim light on the boundary
 {id:'proof',second:7.0},            // stacked plateaus held wide, cubes across the lower tiers
 {id:'waitlist',second:8.4},         // pull back begins, the terrain reads as a map again
 {id:'questions',second:9.1},        // the map rising into its folds
 {id:'footer',second:9.7},           // the folded map on the desk beside the wordmark
] as const;

/**
 * Puts an anchor table into the shape `playheadAt` scans: **ascending by `at`, with no two
 * anchors sharing an offset**. `measure()` reads the sections in DOM order and a document
 * normally lays them out in that order, but nothing in the DOM enforces it — a section
 * that has not laid out yet, a future `position` change, or two sections resolving to the
 * same offset would all feed the scan input it cannot handle, and it would quietly return
 * the wrong second rather than fail. So the guarantee is made here, once per measure,
 * instead of being assumed.
 *
 * Equal offsets keep the **last** entry of the run: a section sharing its offset with the
 * one before it owns the pixels below that point, so its beat is the one a reader at that
 * scroll position should be on. The earlier beat has zero scroll span and is unreachable
 * by construction, not by accident.
 */
export function normaliseAnchors(anchors:readonly Anchor[]):Anchor[]{
 const sorted=[...anchors].sort((a,b)=>a.at-b.at);
 const out:Anchor[]=[];
 for(const anchor of sorted){
  if(out.length&&out[out.length-1].at===anchor.at)out[out.length-1]=anchor;
  else out.push(anchor);
 }
 return out;
}

/**
 * Piecewise-linear interpolation over the measured anchors. Pure, monotonic while the
 * anchors are, and exact in reverse, which is what makes the scrub reversible: the same
 * scroll position always yields the same second, whichever direction it was reached from.
 * Outside the measured range it clamps to the end anchors rather than extrapolating.
 *
 * Expects the ascending, offset-unique table `normaliseAnchors` produces — it runs once
 * per frame, so it scans rather than sorts.
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
 const anchors=normaliseAnchors(FILM_ANCHORS
  .map(a=>{const el=document.getElementById(a.id);return el?{...a,at:Math.min(1,Math.max(0,(el.getBoundingClientRect().top+window.scrollY)/scrollable))}:null;})
  .filter((a):a is Anchor=>a!==null));
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
 /** Restarts the parked seek loop; null exactly while the loop is already running. */
 const wake = useRef<null|(()=>void)>(null);
 const anchorsRef = useRef<Anchor[]>([]);
 const [allowed,setAllowed] = useState(false);
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

 const mounted = allowed && !failed;

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

 useDocumentProgress((progress)=>{
  target.current=playheadAt(progress,anchorsRef.current);
  wake.current?.();
 },mounted&&ready);

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
  // `.film` is `position:fixed; inset:0`, so today this observer never reports a miss.
  // It is kept deliberately: it is the rule DESIGN.md 4.4 states, it costs one callback,
  // and it is what would catch a future layout that stops pinning the film to the viewport.
  const seen=element&&typeof IntersectionObserver!=='undefined'
   ?new IntersectionObserver(entries=>{for(const entry of entries)offscreen=!entry.isIntersecting;apply();},{rootMargin:'0px'})
   :null;
  if(element&&seen)seen.observe(element);
  /**
   * The demo dialog's open state is not reachable from here — `index.tsx` discards it and
   * is not this task's file — so the dialog is detected in the DOM. Base UI portals it as a
   * direct child of `document.body` (measured: the popup sits one level inside a `div`
   * appended to body), so `childList` **without** `subtree` is enough, and that is the whole
   * point: a subtree observer fired 85 times on one scroll pass against 1 for this one, and
   * would fire harder once the number ticker rolls per digit. The check is coalesced into a
   * frame so a burst of mutations costs one `querySelector`, which also lets React finish
   * committing the popup into the container it just appended.
   */
  let check=0;
  const dialogs=typeof MutationObserver!=='undefined'
   ?new MutationObserver(()=>{
     if(check)return;
     check=requestAnimationFrame(()=>{
      check=0;
      const open=document.querySelector('[role="dialog"]')!==null;
      if(open!==dialog){dialog=open;apply();}
     });
    })
   :null;
  dialogs?.observe(document.body,{childList:true});
  apply();
  return ()=>{
   document.removeEventListener('visibilitychange',onVisibility);
   if(check)cancelAnimationFrame(check);
   seen?.disconnect();
   dialogs?.disconnect();
  };
 },[mounted]);

 /**
  * One eased writer, started only once the film can actually seek, and stopped again the
  * moment the damper has arrived. Before R1 this rAF ran every frame forever once `ready`
  * — on a page at rest, with nothing to seek to, for as long as the tab was open.
  *
  * The restart lives in the scroll callback below rather than in a `lastScrollAt` clock in
  * `scroll.ts`: that module is shared by every registered section and the wake-up only
  * concerns this one consumer, so the simpler containment wins.
  */
 useEffect(()=>{
  if(!mounted||!ready)return;
  const node = media.current as FrameCallbackVideo|null;
  if(!node)return;
  if(paused){try{node.pause();}catch{/* a scrubbed film is never playing anyway */}return;}

  let pending=false;         // a seek is in flight and has not presented
  let lastWrite=0;           // wall clock of the last `currentTime` write
  let stall=0;               // the escape-hatch timer for that write
  let presented=0;           // the rVFC handle for that write
  let running=false;
  const settle=()=>{
   pending=false;
   if(stall){window.clearTimeout(stall);stall=0;}
   if(presented&&node.cancelVideoFrameCallback){node.cancelVideoFrameCallback(presented);presented=0;}
  };
  const onSeeked=()=>settle();
  node.addEventListener('seeked',onSeeked);

  const step = ()=>{
   const duration = Number.isFinite(node.duration)&&node.duration>0 ? node.duration : DURATION_FALLBACK;
   const wanted = Math.min(target.current,duration);
   current.current += (wanted-current.current) * 0.14;
   const now = performance.now();
   if(!pending && now-lastWrite >= SEEK_INTERVAL_MS && Math.abs(current.current-node.currentTime) > FRAME){
    lastWrite=now;
    pending=true;
    // `seeked` is the fallback where requestVideoFrameCallback does not exist; the timer
    // is the guard for the seek that presents nothing and fires neither.
    if(node.requestVideoFrameCallback)presented=node.requestVideoFrameCallback(()=>{presented=0;settle();});
    stall=window.setTimeout(settle,SEEK_STALL_MS);
    try{node.currentTime = current.current;}catch{settle();setFailed(true);}
   }
   if(!pending && Math.abs(wanted-current.current) < SETTLED){
    // Arrived. Park the loop and let the next scroll sample start it again.
    running=false;
    raf.current=0;
    return;
   }
   raf.current = requestAnimationFrame(step);
  };
  const start=()=>{if(running)return;running=true;raf.current=requestAnimationFrame(step);};
  wake.current=start;
  start();
  return ()=>{
   wake.current=null;
   running=false;
   settle();
   node.removeEventListener('seeked',onSeeked);
   if(raf.current)cancelAnimationFrame(raf.current);
   raf.current=0;
  };
 },[mounted,ready,paused]);

 useEffect(()=>{
  const root = document.documentElement;
  if(mounted&&ready)root.dataset.film='on';
  else delete root.dataset.film;
  return ()=>{delete root.dataset.film;};
 },[mounted,ready]);

 return <div ref={film} className={css.film} aria-hidden="true">
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
