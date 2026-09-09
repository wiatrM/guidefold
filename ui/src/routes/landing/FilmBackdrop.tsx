import {useEffect,useRef,useState} from 'react';
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
 */
const DURATION_FALLBACK = 10;
const FRAME = 1 / 24;

export function FilmBackdrop(){
 const media = useRef<HTMLVideoElement>(null);
 const target = useRef(0);
 const current = useRef(0);
 const raf = useRef(0);
 const [allowed,setAllowed] = useState(false);
 const [decoded,setDecoded] = useState(false);
 const [failed,setFailed] = useState(false);
 const [ready,setReady] = useState(false);

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

 useDocumentProgress((progress)=>{target.current=progress;},mounted&&ready);

 // One eased writer, started only once the film can actually seek.
 useEffect(()=>{
  if(!mounted||!ready)return;
  const node = media.current;
  if(!node)return;
  const step = ()=>{
   const duration = Number.isFinite(node.duration)&&node.duration>0 ? node.duration : DURATION_FALLBACK;
   const wanted = target.current * duration;
   current.current += (wanted-current.current) * 0.14;
   if(Math.abs(current.current-node.currentTime) > FRAME && !node.seeking){
    try{node.currentTime = current.current;}catch{setFailed(true);}
   }
   raf.current = requestAnimationFrame(step);
  };
  raf.current = requestAnimationFrame(step);
  return ()=>cancelAnimationFrame(raf.current);
 },[mounted,ready]);

 useEffect(()=>{
  const root = document.documentElement;
  if(mounted&&ready)root.dataset.film='on';
  else delete root.dataset.film;
  return ()=>{delete root.dataset.film;};
 },[mounted,ready]);

 return <div className={css.film} aria-hidden="true">
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
   onLoadedData={()=>setReady(true)}
   onError={()=>setFailed(true)}
  >
   <source src="/assets/landing/hero-flight.mp4" type="video/mp4"/>
   <source src="/assets/landing/hero-flight.webm" type="video/webm"/>
  </video>}
  <div className={css.filmScrim}/>
 </div>;
}
