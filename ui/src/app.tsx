import {Component,useEffect,useSyncExternalStore,lazy,Suspense,type ReactNode} from 'react';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {ArrowSquareIn,Books,TreeStructure,FileText,GitPullRequest,ChartBar,Buildings,GitBranch} from '@phosphor-icons/react';
import {BrandMark,StateBadge,ActionButton,RouteState} from './Shared';
import {useAccess,useAccessController} from './api/access';
import type {FixtureAdapter} from './data';
import type {DataSource} from './data/source';
import type {ApiRouteContext,DataState,Params,RouteContext,Session,View} from './domain';
const LibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.LibraryRoute})));
const MapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.MapRoute})));
const SkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.SkillRoute})));
const ImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ImportRoute})));
const OrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.OrganizationRoute})));
const ApiImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiImportRoute})));
const ApiOrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiOrganizationRoute})));
const ApiLibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiLibraryRoute})));
const ApiMapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiMapRoute})));
const ApiSkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiSkillRoute})));
const ApiProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiProposalsRoute})));
const ApiUsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiUsageRoute})));
const ProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ProposalsRoute})));
const UsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.UsageRoute})));
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
const empty:Record<View,{title:string;description:string;action:string;view:View;params?:Params}>={
 import:{title:'No repository imported',description:'Begin with a fixture sign-in, then inspect the local source manifest.',action:'Start fixture sign-in',view:'import',params:{step:'login'}},
 library:{title:'No skills available',description:'Import existing instructions to make their source and scope available.',action:'Open Import',view:'import',params:{step:'preview'}},
 map:{title:'No map available',description:'There are no imported objects in this scenario.',action:'Open Import',view:'import',params:{step:'preview'}},
 skill:{title:'No skill selected',description:'Choose an instruction from the library to inspect its source.',action:'Open Library',view:'library',params:{skill:null}},
 proposals:{title:'No proposals to review',description:'An absence of candidates is a valid result. Existing source instructions remain available.',action:'Browse sources',view:'library'},
 usage:{title:'No observations',description:'No adapter events or outcome assessments are available. Usefulness is Unknown.',action:'Inspect integration setup',view:'organization',params:{tab:'integrations'}},
 organization:{title:'No organization selected',description:'Create the local fixture organization to inspect its repository.',action:'Start fixture sign-in',view:'import',params:{step:'login'}}
};
/** Every U4 view reads the hosted API in API mode (F11–F18). */
const apiRoute:Record<View,(props:{ctx:ApiRouteContext})=>ReactNode>={import:ApiImportRoute,library:ApiLibraryRoute,map:ApiMapRoute,skill:ApiSkillRoute,proposals:ApiProposalsRoute,usage:ApiUsageRoute,organization:ApiOrganizationRoute};
/** Route-local failure UI; the persisted public fixture draft survives a module reload. */
class RouteErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){
  return this.state.failed
   ? <RouteState state="error" title="Could not load this view" description="The view could not be prepared. No operation or publication is confirmed. Reload to retry; saved fixture changes remain in this browser session." action={<ActionButton onClick={()=>window.location.reload()}>Reload view</ActionButton>}/>
   : this.props.children;
 }
}
function NavLinks({view,href}:{view:View;href:(target:View,changes?:Params)=>string}){
 return <nav className={css.navigation} aria-label="Main navigation">{views.map(v=>{const Icon=viewInfo[v].icon;return <Link key={v} to={href(v,{tab:null,step:null,from:null,return_tab:null})} aria-current={v===view?'page':undefined}><Icon aria-hidden="true"/><span>{viewInfo[v].label}</span></Link>;})}</nav>;
}
/** Shared chrome for both compositions; every value that differs is supplied by the caller. */
function Shell({view,href,pathname,railContext,railFoot,topbar,eyebrow,pageFoot,children}:{view:View;href:(target:View,changes?:Params)=>string;pathname:string;railContext:ReactNode;railFoot:ReactNode;topbar:ReactNode;eyebrow:string;pageFoot:string;children:ReactNode}){
 return <div className={css.shell}><a className={css.skip} href="#main">Skip to content</a><aside className={css.rail}><BrandMark/><p className={css.edition}>Skill operations</p><div className={css.railContext}>{railContext}</div><div className={css.desktopNavigation}><NavLinks view={view} href={href}/></div><details key={pathname} className={css.mobileNavigation}><summary>Navigate · {viewInfo[view].label}</summary><NavLinks view={view} href={href}/></details>{railFoot}</aside><div className={css.workspace}><header className={css.topbar}>{topbar}</header><main id="main" className={css.main} tabIndex={-1}><header className={css.pageHeading}><div><span className={css.eyebrow}>{eyebrow}</span><h1>{viewInfo[view].title}</h1><p>{viewInfo[view].description}</p></div></header>
 {children}
 <footer className={css.pageFoot}>{pageFoot}</footer></main></div></div>;
}

/** Fixture-only application composition. The entrypoint supplies the public data adapter. */
function FixtureApp({data,source}:{data:FixtureAdapter;source:DataSource}){
 const {fixture,visibleSkills}=data;
 const location=useLocation(),navigate=useNavigate();
 const memory=useSyncExternalStore(source.drafts.subscribe,source.drafts.get,source.drafts.get) as Session;
 const params=new URLSearchParams(location.search);
 const name=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 const view=views.includes(name as View)?name as View:'import';
 const foreign=(params.has('org')&&params.get('org')!==fixture.org)||(params.has('repo')&&params.get('repo')!==fixture.repo);
 const state:DataState=foreign?'restricted':(['empty','loading','partial','error','degraded','restricted'].includes(params.get('state')||'')?params.get('state') as DataState:'ready');
 const member=params.get('role')==='member',restricted=state==='restricted';
 const href=(target:View,changes:Params={})=>{const next=new URLSearchParams(location.search);next.set('org',fixture.org);next.set('repo',fixture.repo);Object.entries(changes).forEach(([k,v])=>v===null||v===undefined?next.delete(k):next.set(k,String(v)));return '/'+target+'?'+next.toString();};
 const save=(patch:Partial<Session>)=>{if(state!=='ready'||(member&&Object.keys(patch).some(k=>k!=='feedback')))return;source.drafts.save(patch);};
 useEffect(()=>{document.title=viewInfo[view].label+' · Guidefold'+(restricted?'':' · Meridian fixture');if(restricted)source.drafts.clear();},[view,restricted,source]);
 useEffect(()=>{window.scrollTo(0,0);},[location.pathname]);
 if(!views.includes(name as View))return <Navigate to={memory.imported?'/proposals':'/import'} replace/>;
 const ctx:RouteContext={data,source,mode:'fixture',params,state,view,member,canWrite:state==='ready'&&!member,canFeedback:state==='ready',memory,save,href,go:(target,changes)=>navigate(href(target,changes))};
 const route={import:ImportRoute,library:LibraryRoute,map:MapRoute,skill:SkillRoute,proposals:ProposalsRoute,usage:UsageRoute,organization:OrganizationRoute}[view];
 const Content=route;
 const inactive=['empty','loading','error','restricted'].includes(state);
 const e=empty[view];
 return <Shell view={view} href={href} pathname={location.pathname}
  railContext={restricted?'Access unavailable':<><span>Organization / repository</span><strong>meridian / monorepo</strong><span className={css.mobileCommit}>Source commit <code>{fixture.commit.slice(0,12)}</code></span></>}
  railFoot={!restricted&&<footer className={css.railFoot}><GitBranch aria-hidden="true"/><div>Fixture source revision<code>{fixture.commit.slice(0,12)}</code><small>{fixture.skills.length} source files</small></div></footer>}
  topbar={<><span>{restricted?'Local fixture':fixture.label}</span><StateBadge>Local simulation</StateBadge>{!restricted&&<span className={css.role}>{member?'Member':'Owner'} · fixture role</span>}</>}
  eyebrow={restricted?'Access':fixture.repo+' / '+viewInfo[view].label}
  pageFoot="Public fixture scenario. Authentication, backend, Git review and adapter delivery are not connected. No repository writes occur.">
 {inactive?(state==='restricted'?<RouteState state={state} title="Organization access unavailable" description="This fixture scenario does not expose organization content. A role or organization in the URL is not production authorization." action={<ActionButton href={href('import',{state:null,org:fixture.org,repo:fixture.repo,role:null,step:'login'})}>Restart fixture sign-in</ActionButton>}/>:state==='loading'?<RouteState state={state} title="Loading view" description="Waiting for the requested snapshot. No results are available yet."/>:state==='error'?<RouteState state={state} title={view==='proposals'?'Decision not saved':'Could not load this view'} description="This is a fixture error scenario. No operation or publication is confirmed. Retry to return to the local snapshot." action={<ActionButton href={href(view,{state:null})}>Retry view</ActionButton>}/>:<RouteState state={state} title={e.title} description={e.description} action={<ActionButton href={href(e.view,{...e.params,state:null})} tone="system">{e.action}</ActionButton>}/>):<>{state==='partial'&&<div className={css.notice} role="status"><StateBadge tone="warning">Partial</StateBadge><p>{visibleSkills(state).length} of {fixture.skills.length} source files in this fixture snapshot. Omitted bodies are unavailable; completeness is not established.</p></div>}{state==='degraded'&&<div className={css.notice} role="status"><StateBadge tone="warning">Degraded</StateBadge><p>Saved fixture snapshot · read only. Connection is unavailable in this scenario.</p></div>}{member&&<p className={css.memberNotice}>Member scenario: read and feedback are available. Import, decisions and organization changes require owner.</p>}<RouteErrorBoundary key={location.pathname}><Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><Content ctx={ctx}/></Suspense></RouteErrorBoundary></>}
 </Shell>;
}

/** Hosted composition. Organisation and repository come from /me and the URL, never from a fixture. */
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
  railFoot={null}
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

export default function App({data,source}:{data?:FixtureAdapter;source:DataSource}){
 const location=useLocation();
 if(location.pathname.replace(/^\//,'').replace(/\/$/,'')==='__components')return <Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>;
 return source.mode==='api'||!data?<ApiApp source={source}/>:<FixtureApp data={data} source={source}/>;
}
