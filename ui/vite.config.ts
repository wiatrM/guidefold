import {defineConfig,type Plugin,type HtmlTagDescriptor} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import {fileURLToPath, URL} from 'node:url';
/** Dev proxy: the management API and the retrieval contract run on 127.0.0.1:8765.
 * Both the target and the dev port are overridable, because tools/dev/stack.py already takes
 * --api-port and this file could not follow it: a second stack on the same machine proxied its
 * UI to the first stack's API and showed somebody else's data under your own branch. */
const devApi=process.env.GUIDEFOLD_DEV_API??'http://127.0.0.1:8765';
const devPort=Number(process.env.GUIDEFOLD_DEV_UI_PORT??4331);
const api={target:devApi,changeOrigin:false,secure:false};

/**
 * The landing route is `/` and is code-split (main.tsx lazy-imports it), so the browser
 * cannot discover its chunks until the entry chunk has downloaded *and* executed. On an
 * emulated 4G profile that costs a second serial transfer wave, and the LCP element is
 * hero copy that only React can paint, so the whole wave sits on the critical path.
 *
 * Declaring the route's chunks in the head moves them into the first wave. The list is
 * read from the bundle rather than written by hand, so a rename or a re-chunk cannot
 * leave a stale hashed filename behind. The route's stylesheet is preloaded `as="style"`
 * rather than linked: Vite's own preload helper appends the `<link rel="stylesheet">`
 * when the chunk runs, and without the warm cache that append becomes a fresh round trip
 * gating the module's execution, which is most of what this plugin just bought.
 *
 * The cost is that a visitor whose first URL is a management route fetches the landing
 * chunks they will not run. `/` is the public entry point, so the trade is made for it.
 */
function preloadLandingRoute():Plugin{
 let base='/';
 return {
  name:'guidefold-preload-landing-route',
  apply:'build',
  configResolved(config){base=config.base;},
  transformIndexHtml:{
   order:'post',
   handler(_html,ctx){
    const bundle=ctx.bundle;
    if(!bundle)return;
    const chunks=Object.values(bundle).filter(item=>item.type==='chunk');
    const entry=chunks.find(chunk=>chunk.isEntry);
    const landing=chunks.find(chunk=>chunk.facadeModuleId?.replace(/\\/g,'/').endsWith('/routes/landing/index.tsx'));
    if(!landing)return;
    const js=new Set<string>();
    const css=new Set<string>();
    const walk=(fileName:string)=>{
     // The entry chunk and everything it already pulls are in the document's own script
     // tag and stylesheet link; only what the route adds on top belongs here.
     if(js.has(fileName)||fileName===entry?.fileName)return;
     const chunk=bundle[fileName];
     if(!chunk||chunk.type!=='chunk')return;
     js.add(fileName);
     for(const file of chunk.viteMetadata?.importedCss??[])css.add(file);
     for(const dep of chunk.imports)walk(dep);
    };
    walk(landing.fileName);
    const tags:HtmlTagDescriptor[]=[
     ...[...js].map(file=>({tag:'link',attrs:{rel:'modulepreload',crossorigin:'',href:base+file},injectTo:'head' as const})),
     ...[...css].map(file=>({tag:'link',attrs:{rel:'preload',as:'style',href:base+file},injectTo:'head' as const})),
    ];
    return tags;
   },
  },
 };
}

export default defineConfig({plugins:[react(),tailwindcss(),preloadLandingRoute()],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},server:{host:'127.0.0.1',port:devPort,strictPort:true,proxy:{'/api':api,'/v1':api}},preview:{host:'127.0.0.1',port:devPort,strictPort:true}});
