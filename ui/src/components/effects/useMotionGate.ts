import {useEffect,useRef,useState,useSyncExternalStore} from 'react';

function subscribeReducedMotion(update:()=>void){
 if(typeof window.matchMedia!=='function')return ()=>{};
 const query=window.matchMedia('(prefers-reduced-motion: reduce)');
 query.addEventListener('change',update);
 return ()=>query.removeEventListener('change',update);
}
/**
 * Reads prefers-reduced-motion live, the same guard pattern as
 * components/spectrumui/use-beam-motion.ts. Framer/motion's own useReducedMotion caches the
 * query result once per module load, which is correct in a browser tab but makes the
 * reduced-motion path untestable across cases in one Vitest file; this re-reads matchMedia on
 * every render, so a test can mock it per case (ADR-0049).
 */
function useReducedMotionLive(){
 return useSyncExternalStore(subscribeReducedMotion,()=>typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches,()=>false);
}

/**
 * Gates decorative motion for the effects kit (ADR-0049): off under prefers-reduced-motion,
 * off while the element is outside the viewport, and off while the tab is hidden. Shared by
 * every animated effect so a page full of beams, shaders and orbits does not spend a frame
 * budget on what nobody can see. `ref` goes on the element to observe.
 */
export function useMotionGate<T extends Element=HTMLDivElement>(enabled=true){
 const reduced=useReducedMotionLive();
 const [visible,setVisible]=useState(false);
 const [hidden,setHidden]=useState(typeof document!=='undefined'&&document.hidden);
 const ref=useRef<T>(null);
 useEffect(()=>{
  const node=ref.current;
  if(!node||typeof IntersectionObserver!=='function'){setVisible(true);return;}
  const observer=new IntersectionObserver(([entry])=>setVisible(!!entry?.isIntersecting),{threshold:0.1});
  observer.observe(node);
  return ()=>observer.disconnect();
 },[]);
 useEffect(()=>{
  const onVisibility=()=>setHidden(document.hidden);
  document.addEventListener('visibilitychange',onVisibility);
  return ()=>document.removeEventListener('visibilitychange',onVisibility);
 },[]);
 return {ref,reduced,visible,active:enabled&&!reduced&&visible&&!hidden};
}
