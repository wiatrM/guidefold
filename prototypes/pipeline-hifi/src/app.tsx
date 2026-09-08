import {useEffect,useRef,useState,lazy,Suspense} from 'react';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {ArrowSquareIn,Books,TreeStructure,FileText,GitPullRequest,ChartBar,Buildings,GitBranch} from '@phosphor-icons/react';
import {BrandMark,StateBadge,ActionButton,RouteState} from './Shared';
import {fixture,visibleSkills} from './data';
import type {DataState,Params,RouteContext,Session,View} from './domain';
const LibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.LibraryRoute})));
const MapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.MapRoute})));
const SkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.SkillRoute})));
const ImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ImportRoute})));
const OrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.OrganizationRoute})));
const ProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ProposalsRoute})));
const UsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.UsageRoute})));
import css from './App.module.css';

const ComponentGallery=lazy(()=>import('./Gallery').then(m=>({default:m.ComponentGallery})));
const sessionKey='guidefold-hifi-meridian-v1';
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
function readSession():Session{try{const value=JSON.parse(sessionStorage.getItem(sessionKey)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch{return {};}}
export default function App(){
 const location=useLocation(),navigate=useNavigate();
 const [memory,setMemory]=useState<Session>(readSession),memoryRef=useRef(memory);
 const params=new URLSearchParams(location.search);
 const name=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 const view=views.includes(name as View)?name as View:'import';
 const foreign=(params.has('org')&&params.get('org')!==fixture.org)||(params.has('repo')&&params.get('repo')!==fixture.repo);
 const state:DataState=foreign?'restricted':(['empty','loading','partial','error','degraded','restricted'].includes(params.get('state')||'')?params.get('state') as DataState:'ready');
 const member=params.get('role')==='member',restricted=state==='restricted';
 const href=(target:View,changes:Params={})=>{const next=new URLSearchParams(location.search);next.set('org',fixture.org);next.set('repo',fixture.repo);Object.entries(changes).forEach(([k,v])=>v===null||v===undefined?next.delete(k):next.set(k,String(v)));return '/'+target+'?'+next.toString();};
 const save=(patch:Partial<Session>)=>{if(state!=='ready'||(member&&Object.keys(patch).some(k=>k!=='feedback')))return;const next={...memoryRef.current,...patch};memoryRef.current=next;setMemory(next);try{sessionStorage.setItem(sessionKey,JSON.stringify(next));}catch{}};
 useEffect(()=>{document.title=viewInfo[view].label+' · Guidefold'+(restricted?'':' · Meridian fixture');if(restricted){memoryRef.current={};setMemory({});try{sessionStorage.removeItem(sessionKey);}catch{}}},[view,restricted]);
 useEffect(()=>{window.scrollTo(0,0);},[location.pathname]);
 if(name==='__components')return <Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>;
 if(!views.includes(name as View))return <Navigate to={memory.imported?'/proposals':'/import'} replace/>;
 const ctx:RouteContext={params,state,view,member,canWrite:state==='ready'&&!member,canFeedback:state==='ready',memory,save,href,go:(target,changes)=>navigate(href(target,changes))};
 const route={import:ImportRoute,library:LibraryRoute,map:MapRoute,skill:SkillRoute,proposals:ProposalsRoute,usage:UsageRoute,organization:OrganizationRoute}[view];
 const Content=route;
 const inactive=['empty','loading','error','restricted'].includes(state);
 const e=empty[view];
 return <div className={css.shell}><a className={css.skip} href="#main">Skip to content</a><aside className={css.rail}><BrandMark/><p className={css.edition}>Skill operations</p><div className={css.railContext}>{restricted?'Access unavailable':<><span>Organization / repository</span><strong>meridian / monorepo</strong><span className={css.mobileCommit}>Source commit <code>{fixture.commit.slice(0,12)}</code></span></>}</div><div className={css.desktopNavigation}><nav className={css.navigation} aria-label="Main navigation">{views.map(v=>{const Icon=viewInfo[v].icon;return <Link key={v} to={href(v,{tab:null,step:null,from:null,return_tab:null})} aria-current={v===view?'page':undefined}><Icon aria-hidden="true"/><span>{viewInfo[v].label}</span></Link>;})}</nav></div><details key={location.pathname} className={css.mobileNavigation}><summary>Navigate · {viewInfo[view].label}</summary><nav className={css.navigation} aria-label="Main navigation">{views.map(v=>{const Icon=viewInfo[v].icon;return <Link key={v} to={href(v,{tab:null,step:null,from:null,return_tab:null})} aria-current={v===view?'page':undefined}><Icon aria-hidden="true"/><span>{viewInfo[v].label}</span></Link>;})}</nav></details>{!restricted&&<footer className={css.railFoot}><GitBranch aria-hidden="true"/><div>Fixture source revision<code>{fixture.commit.slice(0,12)}</code><small>{fixture.skills.length} source files</small></div></footer>}</aside><div className={css.workspace}><header className={css.topbar}><span>{restricted?'Local fixture':fixture.label}</span><StateBadge>Local simulation</StateBadge>{!restricted&&<span className={css.role}>{member?'Member':'Owner'} · fixture role</span>}</header><main id="main" className={css.main} tabIndex={-1}><header className={css.pageHeading}><div><span className={css.eyebrow}>{restricted?'Access':fixture.repo+' / '+viewInfo[view].label}</span><h1>{viewInfo[view].title}</h1><p>{viewInfo[view].description}</p></div></header>
 {inactive?(state==='restricted'?<RouteState state={state} title="Organization access unavailable" description="This fixture scenario does not expose organization content. A role or organization in the URL is not production authorization." action={<ActionButton href={href('import',{state:null,org:fixture.org,repo:fixture.repo,role:null,step:'login'})}>Restart fixture sign-in</ActionButton>}/>:state==='loading'?<RouteState state={state} title="Loading view" description="Waiting for the requested snapshot. No results are available yet."/>:state==='error'?<RouteState state={state} title={view==='proposals'?'Decision not saved':'Could not load this view'} description="This is a fixture error scenario. No operation or publication is confirmed. Retry to return to the local snapshot." action={<ActionButton href={href(view,{state:null})}>Retry view</ActionButton>}/>:<RouteState state={state} title={e.title} description={e.description} action={<ActionButton href={href(e.view,{...e.params,state:null})} tone="system">{e.action}</ActionButton>}/>):<>{state==='partial'&&<div className={css.notice} role="status"><StateBadge tone="warning">Partial</StateBadge><p>{visibleSkills(state).length} of {fixture.skills.length} source files in this fixture snapshot. Omitted bodies are unavailable; completeness is not established.</p></div>}{state==='degraded'&&<div className={css.notice} role="status"><StateBadge tone="warning">Degraded</StateBadge><p>Saved fixture snapshot · read only. Connection is unavailable in this scenario.</p></div>}{member&&<p className={css.memberNotice}>Member scenario: read and feedback are available. Import, decisions and organization changes require owner.</p>}<Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><Content ctx={ctx}/></Suspense></>}
 <footer className={css.pageFoot}>Public fixture scenario. Authentication, backend, Git review and adapter delivery are not connected. No repository writes occur.</footer></main></div></div>;
}
