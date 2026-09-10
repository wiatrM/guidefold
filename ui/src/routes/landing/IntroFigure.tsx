import {useEffect,useRef,useState} from 'react';
import {ArrowClockwise} from '@phosphor-icons/react';
import css from './landing.module.css';

/**
 * The mechanism figure: a flat strip folds into the mark, then a route with two
 * waypoints draws itself. It plays once at 40% visibility and holds its final frame,
 * which is also its poster, so the resolved composition is what a visitor sees before
 * and after. Not scrubbed, not looped. Under reduced motion, Save-Data or any decoder
 * failure the poster stands alone in the same panel and the caption still carries the
 * meaning, so nothing but the motion is lost.
 */
export function IntroFigure(){
 const host=useRef<HTMLDivElement>(null);
 const media=useRef<HTMLVideoElement>(null);
 const [allowed,setAllowed]=useState(false);
 const [failed,setFailed]=useState(false);

 useEffect(()=>{
  const query=typeof window.matchMedia==='function'?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
  const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
  const update=()=>setAllowed(!query?.matches&&connection?.saveData!==true);
  update();
  query?.addEventListener('change',update);
  return()=>query?.removeEventListener('change',update);
 },[]);

 const shown=allowed&&!failed;
 useEffect(()=>{
  const node=host.current;
  if(!shown||!node||typeof IntersectionObserver==='undefined')return;
  const observer=new IntersectionObserver(([entry])=>{
   if(!entry.isIntersecting)return;
   observer.disconnect();
   void media.current?.play?.().catch(()=>setFailed(true));
  },{threshold:0.4});
  observer.observe(node);
  return()=>observer.disconnect();
 },[shown]);

 function replay(){
  const node=media.current;
  if(!node)return;
  node.currentTime=0;
  void node.play?.().catch(()=>setFailed(true));
 }

 return <figure className={css.introFigure}>
  <div ref={host} className={css.introFrame}>
   {shown
    ?<video
      ref={media}
      className={css.introVideo}
      poster="/assets/landing/intro-poster.webp"
      aria-hidden="true"
      muted
      playsInline
      preload="none"
      onError={()=>setFailed(true)}
     >
      <source src="/assets/landing/intro.webm" type="video/webm"/>
      <source src="/assets/landing/intro.mp4" type="video/mp4"/>
     </video>
    :<img className={css.introVideo} src="/assets/landing/intro-poster.webp" alt="" width="1920" height="1080" loading="lazy" onError={event=>{event.currentTarget.hidden=true;}}/>}
  </div>
  <figcaption className={css.introCaption}>
   <span>Find the scope. Show short cards. Load the full rule.</span>
   {shown&&<button type="button" className={css.replay} onClick={replay}><ArrowClockwise aria-hidden="true"/>Replay</button>}
  </figcaption>
 </figure>;
}
