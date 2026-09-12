import ReactDOM from 'react-dom/client';
import {IconContext} from '@phosphor-icons/react';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-500.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/instrument-sans/latin-500.css';
import '@fontsource/instrument-sans/latin-600.css';
import '@fontsource/instrument-sans/latin-700.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import './tokens/tokens.css';
import './global.css';
import './registry.css';
document.documentElement.classList.add('dark');
import {lazy,Suspense} from 'react';
const Landing=lazy(()=>import('./routes/landing'));
const SpectrumPreview=lazy(()=>import('./components/spectrumui/preview'));
/** Router, session controller and API runtime; off the public route's critical path. */
const Management=lazy(()=>import('./management'));

/** The hosted management API is the only data source. `VITE_GUIDEFOLD_API` names another
 * origin; without it `/api` and `/v1` are read same-origin (the dev server proxies them). */
// Public marketing must not start the membership/session polling controller.
function Entry(){
 if(import.meta.env.DEV&&window.location.pathname==='/__spectrum')return <Suspense fallback={<p>Loading component preview…</p>}><SpectrumPreview/></Suspense>;
 if(window.location.pathname==='/')return <Suspense fallback={<main><h1>Guidefold</h1><p>Team instructions for coding agents. Loading the hosted waitlist…</p></main>}><Landing/></Suspense>;
 return <Suspense fallback={<main><h1>Guidefold</h1><p>Loading your workspace…</p></main>}><Management/></Suspense>;
}
ReactDOM.createRoot(document.getElementById('root')!).render(
 <IconContext.Provider value={{weight:'regular'}}><Entry/></IconContext.Provider>,
);
