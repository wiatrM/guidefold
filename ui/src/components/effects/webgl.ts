/**
 * Feature-detects WebGL without mounting the shader itself, so ShaderField can fall back to a
 * static CSS treatment instead of a blank canvas (ADR-0049 §4). Cheap and synchronous; the
 * probe canvas is never attached to the document.
 */
export function supportsWebGL():boolean{
 if(typeof document==='undefined')return false;
 try{
  const canvas=document.createElement('canvas');
  const gl=canvas.getContext('webgl2')||canvas.getContext('webgl')||canvas.getContext('experimental-webgl');
  return !!gl;
 }catch{
  return false;
 }
}

/** Reads a design token's resolved colour from the document root, for a library (the paper
 * shaders) that needs literal colour strings rather than var() references. Falls back to a
 * neutral graphite so a missing token never throws. */
export function readTokenColor(name:string,fallback='#0c1014'):string{
 if(typeof window==='undefined')return fallback;
 const value=getComputedStyle(document.documentElement).getPropertyValue(name).trim();
 return value||fallback;
}
