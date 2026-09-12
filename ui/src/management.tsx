import {lazy,Suspense,useEffect,useState} from 'react';
import {BrowserRouter} from 'react-router-dom';
import {AccessProvider} from './api/access';
import {createApiRuntime} from './data/apiSource';

const App=lazy(()=>import('./app'));

/**
 * Everything the management app needs before it can render: the router, the session
 * controller and the API runtime. It lives behind its own dynamic import so the public
 * landing route never downloads any of it — `main.tsx` used to mount `BrowserRouter` and
 * statically import `createApiRuntime`, which put react-router and the API adapter in the
 * entry chunk on the critical path of a page that uses neither (DESIGN.md 5, LCP).
 *
 * `App` stays a separate dynamic import: qa/check-route-split.mjs asserts that
 * `/assets/app-*.js` is absent on `/` and present on a management route.
 */
export default function Management(){
 const [{source,access}]=useState(createApiRuntime);
 // index.html's loader waits for this flag (or the landing hero's); without it every
 // management route sat behind the 4 s CSS fallback.
 useEffect(()=>{document.documentElement.dataset.appMounted='true';return()=>{delete document.documentElement.dataset.appMounted;};},[]);
 return <BrowserRouter><AccessProvider controller={access}>
  <Suspense fallback={<main><h1>Guidefold</h1><p>Loading your workspace…</p></main>}><App source={source}/></Suspense>
 </AccessProvider></BrowserRouter>;
}
