import {Component,useEffect,lazy,Suspense,type ReactNode} from 'react';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {ArrowSquareIn,Books,TreeStructure,FileText,GitPullRequest,ChartBar,Buildings} from '@phosphor-icons/react';
import {BrandMark,ActionButton,RouteState} from './Shared';
import {useAccess,useAccessController} from './api/access';
import type {DataSource} from './data/source';
import type {ApiRouteContext,Params,View} from './domain';
const ApiImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiImportRoute})));
const ApiOrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiOrganizationRoute})));
const ApiLibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiLibraryRoute})));
const ApiMapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiMapRoute})));
const ApiSkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiSkillRoute})));
const ApiProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiProposalsRoute})));
const ApiUsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiUsageRoute})));
import css from './App.module.css';

const ComponentGallery=lazy(()=>import('./Gallery').then(m=>({default:m.ComponentGallery})));
const viewInfo:Record<View,{label:string;title:string;description:string;icon:typeof Books}>={
 import:{label:'Import',title:'Import repository skills',description:'Inspect source files before adding them to your library.',icon:ArrowSquareIn},
 library:{label:'Library',title:'Skill library',description:'Find an instruction and check its source, scope and revision.',icon:Books},
 map:{label:'Map',title:'Repository knowledge map',description:'Trace source paths, ownership scopes and declared skill relationships.',icon:TreeStructure},
 skill:{label:'Skill',title:'Skill revision',description:'Read the instruction and the evidence that defines its scope.',icon:FileText},
 proposals:{label:'Proposals',title:'Review a skill revision',description:'Compare the source and candidate before a decision and Git handoff.',icon:GitPullRequest},
 usage:{label:'Usage & quality',title:'Usage & quality',description:'Distinguish publication, delivery and evidence of usefulness.',icon:ChartBar},
 organization:{label:'Organization',title:'Organization',description:'Inspect membership and the connection between a repository and its harness.',icon:Buildings}
};
const views=Object.keys(viewInfo) as View[];
/** Every U4 view reads the hosted API (F11–F18). */
const apiRoute:Record<View,(props:{ctx:ApiRouteContext})=>ReactNode>={import:ApiImportRoute,library:ApiLibraryRoute,map:ApiMapRoute,skill:ApiSkillRoute,proposals:ApiProposalsRoute,usage:ApiUsageRoute,organization:ApiOrganizationRoute};
/** Route-local failure UI. Unsent drafts live in RAM, so a reload drops them; the copy says so. */
class RouteErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){
  return this.state.failed
   ? <RouteState state="error" title="Could not load this view" description="The view could not be prepared. No operation or publication is confirmed. Reload to retry; unsent text typed in this view is not kept." action={<ActionButton onClick={()=>window.location.reload()}>Reload view</ActionButton>}/>
   : this.props.children;
 }
}
function NavLinks({view,href}:{view:View;href:(target:View,changes?:Params)=>string}){
 return <nav className={css.navigation} aria-label="Main navigation">{views.map(v=>{const Icon=viewInfo[v].icon;return <Link key={v} to={href(v,{tab:null,step:null,from:null,return_tab:null})} aria-current={v===view?'page':undefined}><Icon aria-hidden="true"/><span>{viewInfo[v].label}</span></Link>;})}</nav>;
}
/** Shared chrome; every value that differs by view is supplied by the caller. */
function Shell({view,href,pathname,railContext,topbar,eyebrow,pageFoot,children}:{view:View;href:(target:View,changes?:Params)=>string;pathname:string;railContext:ReactNode;topbar:ReactNode;eyebrow:string;pageFoot:string;children:ReactNode}){
 return <div className={css.shell}><a className={css.skip} href="#main">Skip to content</a><aside className={css.rail}><BrandMark/><p className={css.edition}>Skill operations</p><div className={css.railContext}>{railContext}</div><div className={css.desktopNavigation}><NavLinks view={view} href={href}/></div><details key={pathname} className={css.mobileNavigation}><summary>Navigate · {viewInfo[view].label}</summary><NavLinks view={view} href={href}/></details></aside><div className={css.workspace}><header className={css.topbar}>{topbar}</header><main id="main" className={css.main} tabIndex={-1}><header className={css.pageHeading}><div><span className={css.eyebrow}>{eyebrow}</span><h1>{viewInfo[view].title}</h1><p>{viewInfo[view].description}</p></div></header>
 {children}
 <footer className={css.pageFoot}>{pageFoot}</footer></main></div></div>;
}

/** Hosted composition. Organisation and repository come from /me and the URL. */
function ApiApp({source}:{source:DataSource}){
 const location=useLocation(),navigate=useNavigate();
 const access=useAccess(),controller=useAccessController();
 const params=new URLSearchParams(location.search);
 const name=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 const view=views.includes(name as View)?name as View:'import';
 const requestedOrg=params.get('org'),repo=params.get('repo');
 const me=access.me;
 const membership=me?(requestedOrg?me.orgs.find(o=>o.slug===requestedOrg||o.org_id===requestedOrg)??null:me.orgs[0]??null):null;
 const foreign=Boolean(requestedOrg&&me&&!membership);
 const org=membership?.slug??null;
 // Applied while rendering, not in an effect: effects run children first, so an effect here would
 // void the request the new organisation had already started instead of the previous one's.
 // The call returns immediately when the context is unchanged, so a re-render costs nothing.
 source.setContext?.({user:me?.user.id??null,org:membership?.org_id??null,repo,policy:null});
 useEffect(()=>{document.title=viewInfo[view].label+' · Guidefold';},[view]);
 // A route change moves the reading position and the keyboard focus together; #main is tabIndex -1.
 useEffect(()=>{window.scrollTo(0,0);document.getElementById('main')?.focus();},[location.pathname]);
 const href=(target:View,changes:Params={})=>{const next=new URLSearchParams(location.search);if(org)next.set('org',org);if(repo)next.set('repo',repo);Object.entries(changes).forEach(([k,v])=>v===null||v===undefined?next.delete(k):next.set(k,String(v)));const query=next.toString();return '/'+target+(query?'?'+query:'');};
 if(!views.includes(name as View))return <Navigate to="/import" replace/>;
 const masked=foreign||access.status!=='confirmed';
 const ctx:ApiRouteContext={source,access,me,org,repo,role:membership?.role??null,params,view,href,go:(target,changes)=>navigate(href(target,changes)),recheckAccess:controller?(()=>controller.check(true)):undefined};
 const Content=apiRoute[view];
 return <Shell view={view} href={href} pathname={location.pathname}
  railContext={masked?'Access unavailable':<><span>Organization / repository</span><strong>{org} / {repo??'no repository selected'}</strong></>}
  topbar={<><span>{masked?'Guidefold':membership?.name??'No organization'}</span>{!masked&&<span className={css.role}>{membership?.role==='owner'?'Owner':'Member'} · organization role</span>}</>}
  eyebrow={masked?'Access':(repo?repo+' / ':'')+viewInfo[view].label}
  pageFoot="Hosted API. Publication, Git handoff and adapter delivery are separate steps and are not implied by anything on this page.">
 {foreign?<RouteState state="restricted" title="Organization unavailable" description="Your account is not a member of the organization named in this address. An organization in the URL is not authorization." action={<ActionButton href={href('import',{org:null,repo:null,step:'organization'})}>Choose an organization</ActionButton>}/>
 // Import stays reachable after a denial: it is where signing in again happens.
 :access.status==='denied'?(view==='import'?<RouteErrorBoundary key={location.pathname}><Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><ApiImportRoute ctx={ctx}/></Suspense></RouteErrorBoundary>:<RouteState state="restricted" title="Access unavailable" description="The session was refused or revoked. Cached data, drafts and in-flight requests were dropped. Sign in again to continue." action={<ActionButton href={href('import',{step:'login'})}>Sign in again</ActionButton>}/>)
 :access.status==='checking'?<RouteState state="loading" title="Confirming access" description="Checking membership before anything is shown."/>
 :access.status!=='confirmed'?<RouteState state="restricted" title="Access not reconfirmed" description="Membership was last confirmed more than 45 seconds ago, so organization data stays hidden. This is not a statement about your permissions." action={<ActionButton onClick={()=>{void controller?.check(true);}}>Check access now</ActionButton>}/>
 // Keyed by organisation and repository: a switch remounts the view, so no row, tree branch or
 // filter prepared for the previous organisation survives into the next one.
 :<RouteErrorBoundary key={location.pathname}><Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><Content key={(org??'-')+'/'+(repo??'-')} ctx={ctx}/></Suspense></RouteErrorBoundary>}
 </Shell>;
}

export default function App({source}:{source:DataSource}){
 const location=useLocation();
 if(location.pathname.replace(/^\//,'').replace(/\/$/,'')==='__components')return <Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>;
 return <ApiApp source={source}/>;
}
