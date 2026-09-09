import {useSyncExternalStore} from 'react';

function subscribe(update:()=>void) {
  if(typeof window.matchMedia!=='function')return ()=>{};
  const query=window.matchMedia('(prefers-reduced-motion: reduce)');
  query.addEventListener('change',update);
  document.addEventListener('visibilitychange',update);
  return ()=>{query.removeEventListener('change',update);document.removeEventListener('visibilitychange',update);};
}
export function useBeamMotion() {
  return useSyncExternalStore(subscribe,()=>typeof window.matchMedia==='function'&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches&&!document.hidden,()=>false);
}
