import {useEffect,useState} from 'react';
import {MeshGradient} from '@paper-design/shaders-react';
import {readTokenColor} from '../webgl';
import css from './ShaderField.module.css';

/**
 * The actual WebGL chunk (ADR-0049 §4), split into its own module so ShaderField's dynamic
 * import only pulls this — and @paper-design/shaders-react with it — once the field is
 * visible. Colours are read from the design tokens at mount rather than hardcoded, since the
 * library takes literal colour strings, not var() references. `active=false` sets speed to 0,
 * freezing the current frame instead of unmounting the canvas.
 */
export function MeshGradientCanvas({active}:{active:boolean}){
 const [colors,setColors]=useState<string[]|null>(null);
 useEffect(()=>{
  setColors([
   readTokenColor('--survey-teal','#3fb8b1'),
   readTokenColor('--safety-orange','#ff7a3d'),
   readTokenColor('--graphite-900','#0c1014'),
  ]);
 },[]);
 if(!colors)return null;
 return <MeshGradient className={css.canvas} colors={colors} speed={active?0.25:0} distortion={0.6} swirl={0.3}
  maxPixelCount={2073600} minPixelRatio={1}/>;
}
