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
import App from './app';
import {AccessProvider} from './api/access';
import {createApiRuntime} from './data/apiSource';

/** The hosted management API is the only data source. `VITE_GUIDEFOLD_API` names another
 * origin; without it `/api` and `/v1` are read same-origin (the dev server proxies them). */
const {source,access}=createApiRuntime();
ReactDOM.createRoot(document.getElementById('root')!).render(
 <BrowserRouter><IconContext.Provider value={{weight:'regular'}}><AccessProvider controller={access}><App source={source}/></AccessProvider></IconContext.Provider></BrowserRouter>,
);
