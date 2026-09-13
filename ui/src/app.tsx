import {Component,useEffect,useLayoutEffect,lazy,Suspense,type ReactNode} from 'react';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {motion,useReducedMotion} from 'motion/react';
import {ArrowSquareInIcon,BooksIcon,SquaresFourIcon,TreeStructureIcon,FileTextIcon,GitPullRequestIcon,ChartBarIcon,BuildingsIcon,CaretRightIcon,LightningIcon} from '@phosphor-icons/react';
import {ActionButton,BrandMark,RouteState,IconTile} from './Shared';
import {SidebarProvider} from '@/components/ui/sidebar';
import {AppSidebar} from './components/ui/shadcn-space/blocks/dashboard-shell-01/app-sidebar';
import {SiteHeader} from './components/ui/shadcn-space/blocks/dashboard-shell-01/site-header';
import {UserDropdown} from './components/ui/shadcn-space/blocks/dashboard-shell-01/user-dropdown';
import type {NavGroup} from './components/ui/shadcn-space/blocks/dashboard-shell-01/nav-main';
import {Breadcrumb,BreadcrumbList,BreadcrumbItem,BreadcrumbPage,BreadcrumbSeparator} from '@/components/ui/breadcrumb';
import {useAccess,useAccessController} from './api/access';
import {loginHref,safeReturn} from './routes/loginTarget';
import type {DataSource} from './data/source';
import type {ApiRouteContext,Params,View} from './domain';
const ApiHomeRoute=lazy(()=>import('./routes/HomeRoute').then(m=>({default:m.ApiHomeRoute})));
const ApiImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiImportRoute})));
const ApiInvitationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiInvitationRoute})));
const ApiOrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiOrganizationRoute})));
const DemoRoute=lazy(()=>import('./routes/DemoRoute').then(m=>({default:m.DemoRoute})));
const ApiLibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiLibraryRoute})));
const ApiMapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiMapRoute})));
const ApiSkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiSkillRoute})));
const ApiProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiProposalsRoute})));
const ApiUsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiUsageRoute})));
const ApiLiveAgentRoute=lazy(()=>import('./routes/LiveAgentRoute').then(m=>({default:m.ApiLiveAgentRoute})));
const LoginRoute=lazy(()=>import('./routes/LoginRoute').then(m=>({default:m.LoginRoute})));
const ToastHost=lazy(()=>import('./ToastHost'));
import css from './App.module.css';

const ComponentGallery=lazy(()=>import('./Gallery').then(m=>({default:m.ComponentGallery})));
const viewInfo:Record<View,{label:string;title:string;description:string;icon:typeof BooksIcon}>={
 home:{label:'Overview',title:'Overview',description:'What waits for you, how the library is doing and what the last window of telemetry says.',icon:SquaresFourIcon},
 import:{label:'Import',title:'Import repository skills',description:'Inspect source files before adding them to your library.',icon:ArrowSquareInIcon},
 library:{label:'Library',title:'Skill library',description:'Find an instruction and check its source, scope and revision.',icon:BooksIcon},
 map:{label:'Map',title:'Repository knowledge map',description:'Trace source paths, ownership scopes and declared skill relationships.',icon:TreeStructureIcon},
 skill:{label:'Skill',title:'Skill revision',description:'Read the instruction and the evidence that defines its scope.',icon:FileTextIcon},
 proposals:{label:'Proposals',title:'Review a skill revision',description:'Compare the source and candidate before a decision and Git handoff.',icon:GitPullRequestIcon},
 usage:{label:'Usage & quality',title:'Usage & quality',description:'Distinguish publication, delivery and evidence of usefulness.',icon:ChartBarIcon},
 organization:{label:'Organization',title:'Organization',description:'Inspect membership and the connection between a repository and its harness.',icon:BuildingsIcon},
 live:{label:'Live Agent',title:'Live Agent',description:'Start a run and watch its per-repository progress and outcome.',icon:LightningIcon}
};
const views=Object.keys(viewInfo) as View[];
const navGroups:{label:string;items:View[]}[]=[
 {label:'Workspace',items:['home','import','live']},
 {label:'Knowledge',items:['library','map']},
 {label:'Review',items:['proposals','usage']},
 {label:'Manage',items:['organization']}
];
const groupFor=(view:View)=>navGroups.find(group=>group.items.includes(view))?.label??'Knowledge';
/** Every U4 view reads the hosted API (F11–F18). */
const apiRoute:Record<View,(props:{ctx:ApiRouteContext})=>ReactNode>={home:ApiHomeRoute,import:ApiImportRoute,library:ApiLibraryRoute,map:ApiMapRoute,skill:ApiSkillRoute,proposals:ApiProposalsRoute,usage:ApiUsageRoute,organization:ApiOrganizationRoute,live:ApiLiveAgentRoute};
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
/** One orchestrated entrance per route: the tile settles first, then title and lede follow (frontend-design: a single reveal, never per-card fades). */
function PageHeader({view,group,actions}:{view:View;group:string;actions?:ReactNode}){
 const reduce=useReducedMotion();
 const Icon=viewInfo[view].icon;
 const rise=(delay:number)=>({initial:reduce?false:{opacity:0,transform:'translateY(6px)'},animate:{opacity:1,transform:'translateY(0)'},transition:{duration:reduce?0:0.28,delay:reduce?0:delay,ease:[0.16,1,0.3,1] as const}});
 return <header key={view} className={css.pageHeading} data-slot="page-header">
  <IconTile icon={<Icon weight="duotone"/>} size="lg" className={css.pageTile}/>
  <div className={css.pageText}>
   <Breadcrumb className={css.breadcrumb}><BreadcrumbList className="m-0 list-none gap-1 p-0 text-[length:var(--font-size-small)] text-stone-300"><BreadcrumbItem>{group}</BreadcrumbItem><BreadcrumbSeparator><CaretRightIcon aria-hidden="true"/></BreadcrumbSeparator><BreadcrumbItem><BreadcrumbPage className="font-medium text-stone-100">{viewInfo[view].label}</BreadcrumbPage></BreadcrumbItem></BreadcrumbList></Breadcrumb>
   <motion.h1 data-slot="animated-text" {...rise(0.04)}>{viewInfo[view].title}</motion.h1>
   <motion.p {...rise(0.1)}>{viewInfo[view].description}</motion.p>
  </div>
  {actions&&<div className={css.pageActions}>{actions}</div>}
 </header>;
}
/** Shared chrome; every value that differs by view is supplied by the caller. `.console`
 * carries the shadcn dark-neutral theme tokens (tokens.css); the landing route never gets
 * this class, so it keeps the orange-branded `:root` values (docs/reports/ui/console-shadcn-20260912.md §9). */
function Shell({view,href,railContext,workspace,repo,masked,account,pageFoot,children}:{view:View;href:(target:View,changes?:Params)=>string;railContext:ReactNode;workspace:string;repo:string|null;masked:boolean;account:ReactNode;pageFoot:string;children:ReactNode}){
 const reduce=useReducedMotion();
 const groups:NavGroup[]=navGroups.map(group=>({label:group.label,items:group.items.map(v=>({label:viewInfo[v].label,href:href(v,{tab:null,step:null,from:null,return_tab:null}),icon:viewInfo[v].icon,active:v===view}))}));
 // Base UI portals (menu, sheet, tooltip popups) mount at document.body, outside this
 // subtree, so the `.console` class on the wrapper alone would not reach them; body also
 // gets it while the shell is mounted so a popup keeps the dark-neutral pairing instead of
 // falling back to the landing's orange `:root` tokens (docs/reports/ui/console-shadcn-20260912.md §9).
 // useLayoutEffect, not useEffect: it must land before the browser's first paint, or a popup
 // opened in the same tick as mount (e2e clicked through fast) can briefly portal into an
 // unthemed body and fail axe color-contrast on the mismatched pairing.
 useLayoutEffect(()=>{document.body.classList.add('console');return()=>{document.body.classList.remove('console');};},[]);
 return <SidebarProvider className={css.shell+' console'}>
  <a className={css.skip} href="#main">Skip to content</a>
  <AppSidebar brand={<Link to={href('library')} className={css.brandLink} aria-label="Guidefold library"><BrandMark/></Link>} groups={groups} railContext={railContext} account={account}/>
  <div className={css.workspace}>
   <header className={css.topbar}><SiteHeader workspace={workspace} repo={repo} masked={masked}/></header>
   <main id="main" className={css.main} tabIndex={-1}><PageHeader view={view} group={groupFor(view)}/>
    <motion.div key={view} className={css.pageBody} initial={reduce?false:{opacity:0,transform:'translateY(8px)'}} animate={{opacity:1,transform:'translateY(0)'}} transition={{duration:reduce?0:0.32,delay:reduce?0:0.14,ease:[0.16,1,0.3,1]}}>{children}</motion.div>
    <footer className={css.pageFoot}>{pageFoot}</footer></main>
  </div>
 </SidebarProvider>;
}

/** Hosted composition. Organisation and repository come from /me and the URL. */
function ApiApp({source}:{source:DataSource}){
 const location=useLocation(),navigate=useNavigate();
 const access=useAccess(),controller=useAccessController();
 const params=new URLSearchParams(location.search);
 const name=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 const view=views.includes(name as View)?name as View:'home';
 const requestedOrg=params.get('org'),repo=params.get('repo');
 const me=access.me;
 const invitationToken=location.pathname.match(/^\/invitations\/([^/]+)\/accept\/?$/)?.[1] ?? null;
 const membership=me?(requestedOrg?me.orgs.find(o=>o.slug===requestedOrg||o.org_id===requestedOrg)??null:me.orgs[0]??null):null;
 const foreign=Boolean(requestedOrg&&me&&!membership);
 const org=membership?.slug??null;
 // Applied while rendering, not in an effect: effects run children first, so an effect here would
 // void the request the new organisation had already started instead of the previous one's.
 // The call returns immediately when the context is unchanged, so a re-render costs nothing.
 source.setContext?.({user:me?.user.id??null,org:membership?.org_id??null,repo,policy:null});
 useEffect(()=>{document.title=viewInfo[view].label+' | Guidefold';},[view]);
 // A route change moves the reading position and the keyboard focus together; #main is tabIndex -1.
 useEffect(()=>{window.scrollTo(0,0);document.getElementById('main')?.focus();},[location.pathname]);
 // `github_connected` (below) is this client's own one-shot signal for the address the GitHub
 // callback redirect lands on, never a real navigation target: every `href` this builder produces
 // would otherwise carry it forward (it starts from the current query string) into the sidebar,
 // the tab links and anything bookmarked or shared from this page, replaying "you're back from
 // GitHub" on an address nobody returned from.
 const href=(target:View,changes:Params={})=>{const next=new URLSearchParams(location.search);next.delete('github_connected');if(org)next.set('org',org);if(repo)next.set('repo',repo);Object.entries(changes).forEach(([k,v])=>v===null||v===undefined?next.delete(k):next.set(k,String(v)));const query=next.toString();return '/'+target+(query?'?'+query:'');};
 // `GET /api/v1/github/installations/callback` (contract §4.7, ADR-0034) 302s a successful
 // install link to exactly this literal path (`identity/github_link.go`'s `returnTo`) — one this
 // SPA never generates and does not recognise as a view name, so unhandled it fell through to the
 // unknown-view redirect below and silently dropped the owner on /home with no organisation, no
 // tab and no sign anything happened. The callback's *failures* answer raw JSON directly
 // (`mgmt.Fail`/`mgmt.Invalid`, never a redirect — `mgmt.Router.render` always writes the JSON
 // envelope, confirmed reading both) and never reach this router at all, so reaching this path is
 // itself the success signal: `github_connected=1` here is not a guess at what the server meant,
 // it is this client's own name for "the only way to arrive here at all".
 const githubInstallReturn=location.pathname.match(/^\/orgs\/([^/]+)\/settings\/github\/?$/)?.[1] ?? null;
 if(githubInstallReturn)return <Navigate to={'/organization?tab=integrations&org='+encodeURIComponent(githubInstallReturn)+'&github_connected=1'} replace/>;
 // An invitation link must render for a visitor who has no session yet, so it is checked before
 // the denied/unknown-view redirects below would otherwise bounce an anonymous click to /login.
 if(invitationToken)return <Shell view="import" href={href}
  railContext="Invitation"
  workspace="Invitation" repo={null} masked={false}
  account={me?<UserDropdown name={me.user.name||me.user.email} email={me.user.email} role="Member" profileHref={href('organization',{tab:'members'})} onLogout={async()=>{await source.logout('logout:'+me.user.id);controller?.reportDenied();navigate('/import?step=login',{replace:true});}}/>:<Link className={css.signInLink} to={href('import',{step:'login'})}>Sign in</Link>}
  pageFoot="Invitation links are one-time capabilities. Membership changes are confirmed by the API.">
  <RouteErrorBoundary key={location.pathname}><Suspense fallback={<RouteState state="loading" title="Loading invitation" description="Preparing the invitation screen."/>}><ApiInvitationRoute
   source={source} access={access} me={me} token={decodeURIComponent(invitationToken)} onRecheck={() => controller?.check(true) ?? Promise.resolve()}
   onAccepted={orgID => navigate('/import?step=organization&org=' + encodeURIComponent(orgID))}/></Suspense></RouteErrorBoundary>
 </Shell>;
 // A session that does not exist is not a view state: every management route is private, so the
 // request leaves the shell for the full-width login page carrying where it was going (IA 3,
 // "Login jest stanem wejscia"). Import used to keep its own inline sign-in step; it does not.
 // A 403 on a resource is the opposite case and must NOT redirect: the session is live, so the
 // login page would send the operator straight back to the forbidden address and round again.
 // `denied` (an actual 401/403 on /me) is the only settled "no session" result access.ts ever
 // reports; access.ts's own contract keeps the session on a bare network failure ("A network
 // failure without a denial keeps the session but never reveals unconfirmed data"), and `offline`
 // is exactly that ambiguous case — a lapsed reconfirmation and a request that never had a
 // session look identical to this controller (fresh mount, `me` null either way) until /me
 // actually answers. So only `denied` may leave the shell for /login; `offline` falls through to
 // the masked "Access not reconfirmed" state below like any other unconfirmed status, on every
 // view including Import (IA §6; e2e/states.spec.ts "degraded" exercises exactly this).
 if(access.status==='denied'&&access.denial!=='forbidden')return <Navigate to={loginHref(location.pathname+location.search)} replace/>;
 if(!views.includes(name as View))return <Navigate to="/home" replace/>;
 const masked=foreign||access.status!=='confirmed';
 const ctx:ApiRouteContext={source,access,me,org,repo,role:membership?.role??null,params,view,href,go:(target,changes)=>navigate(href(target,changes)),recheckAccess:controller?(()=>controller.check(true)):undefined};
 const Content=apiRoute[view];
 // Where a forbidden address sends the operator back to: their own first organisation, with the
 // refused organisation and repository dropped from the address so the next read is a different
 // one. `reset()` clears the denial so the heartbeat may confirm membership again.
 const ownHref='/import'+(me?.orgs[0]?'?org='+encodeURIComponent(me.orgs[0].slug)+'&step=preview':'?step=organization');
 // Signing in again really does start again: the session is ended, the held identity and the
 // denial go with it, and the login page is opened with no return target, because the address
 // that was refused is the one place this must not send the operator back to.
 // The address is left FIRST, before the network round trip: `source.logout` is awaited, and
 // while it is in flight the access heartbeat is free to run again (forget() already cleared the
 // denial that was gating it). If that heartbeat's `/me` comes back refused before this function
 // resumes, the shell's own unauthenticated redirect would otherwise fire first and compute
 // `loginHref` from the still-current `/library?...` address — reintroducing the exact
 // refused-address return target this flow exists to avoid. Capturing `id` first (rather than
 // reading `me.user.id` after the navigate) keeps the logout call scoped to the identity that was
 // actually signed in, since `forget()` drops `me` before the request goes out.
 const signInAgain=async()=>{
  const id=me?.user.id;
  controller?.forget();
  navigate('/login',{replace:true});
  try{if(id)await source.logout('logout:'+id);}catch{/* The local session is dropped either way. */}
 };
 return <Shell view={view} href={href}
  railContext={<div className={css.railContext}><span>Workspace</span><strong>{masked?'Access unavailable':org}</strong><small>{masked?'Sign in or check access':repo??'No repository selected'}</small></div>}
  workspace={masked?'Workspace unavailable':membership?.name??'No organization'} repo={repo} masked={masked}
  account={me?<UserDropdown name={me.user.name||me.user.email} email={me.user.email} role={membership?.role==='owner'?'Owner':'Member'} profileHref={href('organization',{tab:'members'})} onLogout={async()=>{await source.logout('logout:'+me.user.id);controller?.reportDenied();navigate('/login',{replace:true});}}/>:<Link className={css.signInLink} to={loginHref(location.pathname+location.search)}>Sign in</Link>}
  pageFoot="Hosted API. Publication, Git handoff and adapter delivery are separate steps and are not implied by anything on this page.">
 {access.status==='denied'?<RouteState state="restricted" title="Not available to your account" description="This organization or repository refused the request while you are signed in. Nothing about its content is shown, and cached data and drafts for it were dropped. Your account itself is unchanged." action={<><ActionButton onClick={()=>{controller?.reset();navigate(ownHref,{replace:true});}}>{me?.orgs.length?'Open your organization':'Choose an organization'}</ActionButton><ActionButton tone="system" onClick={()=>{void signInAgain();}}>Sign in again</ActionButton></>}/>
 :foreign?<RouteState state="restricted" title="Organization unavailable" description="Your account is not a member of the organization named in this address. An organization in the URL is not authorization." action={<><ActionButton href={href('import',{org:null,repo:null,step:'organization'})}>Choose an organization</ActionButton><ActionButton tone="system" onClick={()=>{void signInAgain();}}>Sign in again</ActionButton></>}/>
 :access.status==='checking'?<RouteState state="loading" title="Confirming access" description="Checking membership before anything is shown."/>
 // `offline` lands here too, whether it is a lapsed reconfirmation or a first check that failed
 // before ever confirming anything: the manual re-check offered here is the only way forward
 // either way, never a redirect (see the `denied` branch above).
 :access.status!=='confirmed'?<RouteState state="restricted" title="Access not reconfirmed" description="Membership was last confirmed more than 45 seconds ago, so organization data stays hidden. This is not a statement about your permissions." action={<ActionButton onClick={()=>{void controller?.check(true);}}>Check access now</ActionButton>}/>
 // Keyed by organisation and repository: a switch remounts the view, so no row, tree branch or
 // filter prepared for the previous organisation survives into the next one.
 :<RouteErrorBoundary key={location.pathname}><Suspense fallback={<RouteState state="loading" title="Loading view" description="Preparing the requested view."/>}><Content key={(org??'-')+'/'+(repo??'-')} ctx={ctx}/></Suspense></RouteErrorBoundary>}
 </Shell>;
}

/** `/login`. Outside the shell and outside `View`: login is an entry state, not a destination
 * in the rail (IA 3). A caller who already has a confirmed session is sent on to the target it
 * carries, which is what the browser Back button produces after a successful sign-in. */
function LoginEntry({source}:{source:DataSource}){
 const location=useLocation();
 const access=useAccess();
 const target=safeReturn(new URLSearchParams(location.search).get('return'));
 if(access.status==='confirmed')return <Navigate to={target} replace/>;
 // A sign-in form is only honest once the session is known to be absent. While the first /me is
 // in flight, or whenever an identity is already held, this is the neutral loading shell: opening
 // /login from a bookmark or the Back button with a live session used to flash the providers and
 // fire their request before the redirect (review, important 2).
 if(access.status==='checking'||access.me)return <main id="main" tabIndex={-1}><RouteState state="loading" title="Checking your session" description="Reading the current session before anything is offered."/></main>;
 return <Suspense fallback={<main id="main" tabIndex={-1}><RouteState state="loading" title="Loading sign-in" description="Preparing the sign-in page."/></main>}><LoginRoute source={source} returnTo={target}/></Suspense>;
}

export default function App({source}:{source:DataSource}){
 const location=useLocation();
 const toaster=<Suspense fallback={null}><ToastHost/></Suspense>;
 const path=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 if(path==='__components')return <><Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>{toaster}</>;
 if(path==='login')return <><LoginEntry source={source}/>{toaster}</>;
 // Its own top-level branch, not a check inside ApiApp: ApiApp calls useAccess/useAccessController
 // and other hooks unconditionally, and an early return above those would change the Hook order
 // between /demo and every other address for what React treats as the same component instance.
 if(path==='demo')return <><Suspense fallback={<RouteState state="loading" title="Loading demo" description="Preparing the isolated sample repository."/>}><DemoRoute/></Suspense>{toaster}</>;
 return <><ApiApp source={source}/>{toaster}</>;
}
