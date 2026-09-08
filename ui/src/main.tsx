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
import {meridian} from './data/meridian';
import {createFixtureDataSource} from './data/fixtureSource';
import {createApiRuntime} from './data/apiSource';

/** API mode when VITE_GUIDEFOLD_API is configured or `?mode=api` is present; `?mode=fixture` wins. */
const requested=new URLSearchParams(window.location.search).get('mode');
const useApi=requested==='api'||(requested!=='fixture'&&Boolean(import.meta.env.VITE_GUIDEFOLD_API));
const root=ReactDOM.createRoot(document.getElementById('root')!);
if(useApi){
 const {source,access}=createApiRuntime();
 root.render(<BrowserRouter><IconContext.Provider value={{weight:'regular'}}><AccessProvider controller={access}><App source={source}/></AccessProvider></IconContext.Provider></BrowserRouter>);
}else{
 root.render(<BrowserRouter><IconContext.Provider value={{weight:'regular'}}><App data={meridian} source={createFixtureDataSource(meridian)}/></IconContext.Provider></BrowserRouter>);
}
