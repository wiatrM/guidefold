import ReactDOM from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
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
import {AccessProvider} from './api/access';
import {createApiRuntime} from './data/apiSource';
import {lazy,Suspense,useState} from 'react';
const Landing=lazy(()=>import('./routes/landing'));
const SpectrumPreview=lazy(()=>import('./components/spectrumui/preview'));
const App=lazy(()=>import('./app'));

/** The hosted management API is the only data source. `VITE_GUIDEFOLD_API` names another
 * origin; without it `/api` and `/v1` are read same-origin (the dev server proxies them). */
// Public marketing must not start the membership/session polling controller.
function Entry(){
 if(import.meta.env.DEV&&window.location.pathname==='/__spectrum')return <Suspense fallback={<p>Loading component preview…</p>}><SpectrumPreview/></Suspense>;
 if(window.location.pathname==='/')return <Suspense fallback={<main><h1>Guidefold</h1><p>Team instructions for coding agents. Loading the hosted waitlist…</p></main>}><Landing/></Suspense>;
 return <Management/>;
}
function Management(){const [{source,access}]=useState(createApiRuntime);return <AccessProvider controller={access}><Suspense fallback={<main><h1>Guidefold</h1><p>Loading your workspace…</p></main>}><App source={source}/></Suspense></AccessProvider>;}
ReactDOM.createRoot(document.getElementById('root')!).render(
 <BrowserRouter><IconContext.Provider value={{weight:'regular'}}><Entry/></IconContext.Provider></BrowserRouter>,
);
