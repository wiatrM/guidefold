import {lazy,Suspense,useEffect,useState} from 'react';
import {useMotionGate} from '../useMotionGate';
import {supportsWebGL} from '../webgl';
import css from './ShaderField.module.css';

const MeshGradientCanvas=lazy(()=>import('./MeshGradientCanvas').then(m=>({default:m.MeshGradientCanvas})));

/**
 * Shader background for page chrome and empty states (ADR-0049 §4). The WebGL chunk is
 * lazy-loaded: it is requested only once this element has actually entered the viewport, so a
 * route's first paint never waits on it. Once mounted it keeps running — paused (speed 0, not
 * unmounted) off-screen or while the tab is hidden, and under reduced motion it renders one
 * still frame the same way. Where WebGL is unavailable it never mounts at all; a flat CSS
 * gradient carries the same page chrome instead.
 */
export function ShaderField({className}:{className?:string}){
 const gate=useMotionGate<HTMLDivElement>();
 const [webgl,setWebgl]=useState<boolean|null>(null);
 useEffect(()=>{
  if(gate.visible&&webgl===null)setWebgl(supportsWebGL());
 },[gate.visible,webgl]);
 const showShader=gate.visible&&webgl===true;
 return <div ref={gate.ref} aria-hidden="true" data-slot="shader-field" className={[css.field,className].filter(Boolean).join(' ')}>
  {showShader
   ?<Suspense fallback={<div className={css.fallback}/>}><MeshGradientCanvas active={gate.active}/></Suspense>
   :<div className={css.fallback}/>}
 </div>;
}
