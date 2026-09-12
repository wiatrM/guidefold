import {Component,useEffect,lazy,Suspense,useState,type ReactNode} from 'react';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {Menu} from '@base-ui/react/menu';
import {Dialog} from '@base-ui/react/dialog';
import {Avatar} from '@base-ui/react/avatar';
import {AnimatePresence,motion,useReducedMotion} from 'motion/react';
import clsx from 'clsx';
import {ArrowSquareIn,Books,TreeStructure,FileText,GitPullRequest,ChartBar,Buildings,SidebarSimple,List,X,SignOut,CaretRight} from '@phosphor-icons/react';
import {BrandMark,ActionButton,RouteState} from './Shared';
import {useAccess,useAccessController} from './api/access';
import {loginHref,safeReturn} from './routes/loginTarget';
import type {DataSource} from './data/source';
import type {ApiRouteContext,Params,View} from './domain';
const ApiImportRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiImportRoute})));
const ApiOrganizationRoute=lazy(()=>import('./routes/OnboardingRoutes').then(m=>({default:m.ApiOrganizationRoute})));
const ApiLibraryRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiLibraryRoute})));
const ApiMapRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiMapRoute})));
const ApiSkillRoute=lazy(()=>import('./routes/CatalogRoutes').then(m=>({default:m.ApiSkillRoute})));
const ApiProposalsRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiProposalsRoute})));
const ApiUsageRoute=lazy(()=>import('./routes/ReviewRoutes').then(m=>({default:m.ApiUsageRoute})));
const LoginRoute=lazy(()=>import('./routes/LoginRoute').then(m=>({default:m.LoginRoute})));
const ToastHost=lazy(()=>import('./ToastHost'));
import css from './App.module.css';
import {TreeNav} from './components/spectrumui/tree-nav';

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
const navGroups:{label:string;items:View[]}[]=[
 {label:'Workspace',items:['import']},
 {label:'Knowledge',items:['library','map']},
 {label:'Review',items:['proposals','usage']},
 {label:'Manage',items:['organization']}
];
const groupFor=(view:View)=>navGroups.find(group=>group.items.includes(view))?.label??'Knowledge';
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
function NavLabel({children,collapsed}:{children:string;collapsed:boolean}){
 const reduce=useReducedMotion();
 return <AnimatePresence initial={false}>{!collapsed&&<motion.span className={css.navLabel} initial={{opacity:0,transform:reduce?'none':'translateX(-4px)'}} animate={{opacity:1,transform:'translateX(0)'}} exit={{opacity:0,transform:reduce?'none':'translateX(-4px)'}} transition={{duration:0.16,ease:[0.23,1,0.32,1]}}>{children}</motion.span>}</AnimatePresence>;
}
function AnimatedTitle({children}:{children:string}){
 const reduce=useReducedMotion();
 return <motion.h1 data-slot="animated-text" initial={{opacity:0,transform:reduce?'none':'translateY(4px)'}} animate={{opacity:1,transform:'translateY(0)'}} transition={{duration:reduce?0.08:0.18,ease:[0.23,1,0.32,1]}}>{children}</motion.h1>;
}
function UserAvatar({initials}:{initials:string}){
 return <Avatar.Root className={css.avatar} data-slot="avatar"><Avatar.Fallback>{initials}</Avatar.Fallback></Avatar.Root>;
}
function RouterAnchor({href,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>&{href:string}){return <Link to={href} {...props}/>;}
function NavLinks({view,href,collapsed=false,onNavigate}:{view:View;href:(target:View,changes?:Params)=>string;collapsed?:boolean;onNavigate?:()=>void}){
 return <nav className={css.navigation} aria-label="Main navigation">{navGroups.map(group=>{
  const items=group.items.map(v=>{const Icon=viewInfo[v].icon;return {label:viewInfo[v].label,href:href(v,{tab:null,step:null,from:null,return_tab:null}),icon:<Icon weight="regular" aria-hidden="true"/>};});
  return <div className={css.navGroup} key={group.label}>{!collapsed&&<p className={css.navGroupLabel}>{group.label}</p>}<TreeNav items={items} compact={collapsed} activeHref={group.items.includes(view)?href(view,{tab:null,step:null,from:null,return_tab:null}):undefined} linkComponent={RouterAnchor} onSelect={()=>onNavigate?.()}/></div>;
 })}</nav>;
}
function AccountMenu({name,email,role,profileHref,onLogout}:{name:string;email:string;role:string;profileHref:string;onLogout:()=>Promise<void>}){
 const [signingOut,setSigningOut]=useState(false);
 const [logoutError,setLogoutError]=useState('');
 const initials=name.split(/\s+/).filter(Boolean).slice(0,2).map(part=>part[0]?.toUpperCase()).join('')||email.slice(0,1).toUpperCase();
 const signOut=async()=>{if(signingOut)return;setSigningOut(true);setLogoutError('');try{await onLogout();}catch{setLogoutError('Sign out failed. Try again.');void import('sonner').then(({toast})=>toast.error('Sign out failed'));setSigningOut(false);}};
 return <Menu.Root><Menu.Trigger className={css.accountTrigger} aria-label="Open profile menu"><UserAvatar initials={initials}/><span className={css.accountText}><strong>{name}</strong><small>{role}</small></span><CaretRight className={css.accountCaret} aria-hidden="true"/></Menu.Trigger><Menu.Portal><Menu.Positioner className={css.menuPositioner} sideOffset={8}><Menu.Popup className={css.accountMenu}><div className={css.accountSummary}><UserAvatar initials={initials}/><span><strong>{name}</strong><small>{email}</small></span></div><Menu.Separator className={css.menuSeparator}/><Menu.Item className={css.menuItem} render={<Link to={profileHref}/>}>Profile and organization</Menu.Item><Menu.Item className={clsx(css.menuItem,css.signOutItem)} disabled={signingOut} onClick={()=>{void signOut();}}><SignOut aria-hidden="true"/>{signingOut?'Signing out':'Sign out'}</Menu.Item>{logoutError&&<p className={css.menuError} role="status">{logoutError}</p>}</Menu.Popup></Menu.Positioner></Menu.Portal></Menu.Root>;
}
/** Shared chrome; every value that differs by view is supplied by the caller. */
function Shell({view,href,railContext,topbar,account,pageFoot,children}:{view:View;href:(target:View,changes?:Params)=>string;railContext:ReactNode;topbar:ReactNode;account:ReactNode;pageFoot:string;children:ReactNode}){
 const [collapsed,setCollapsed]=useState(false);
 const [mobileOpen,setMobileOpen]=useState(false);
 return <div className={css.shell} data-collapsed={collapsed}><a className={css.skip} href="#main">Skip to content</a><aside className={css.rail}><div className={css.brandRow}><Link to={href('library')} className={css.brandLink} aria-label="Guidefold library"><BrandMark/></Link><button className={css.collapseButton} type="button" aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} aria-expanded={!collapsed} onClick={()=>setCollapsed(value=>!value)}><SidebarSimple aria-hidden="true"/></button></div><div className={css.railContext}>{railContext}</div><div className={css.desktopNavigation}><NavLinks view={view} href={href} collapsed={collapsed}/></div><div className={css.accountSlot}>{account}</div></aside><header className={css.mobileHeader}><Link to={href('library')} className={css.mobileBrand} aria-label="Guidefold library"><BrandMark/></Link><Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}><Dialog.Trigger className={css.mobileMenuButton}><List aria-hidden="true"/>Menu</Dialog.Trigger><Dialog.Portal><Dialog.Backdrop className={css.sheetBackdrop}/><Dialog.Popup className={css.sheet}><div className={css.sheetHeader}><Dialog.Title>Navigate Guidefold</Dialog.Title><Dialog.Close className={css.sheetClose} aria-label="Close navigation"><X aria-hidden="true"/></Dialog.Close></div><div className={css.sheetContext}>{railContext}</div><NavLinks view={view} href={href} onNavigate={()=>setMobileOpen(false)}/><div className={css.sheetAccount}>{account}</div></Dialog.Popup></Dialog.Portal></Dialog.Root></header><div className={css.workspace}><header className={css.topbar}>{topbar}</header><main id="main" className={css.main} tabIndex={-1}><header key={view} className={css.pageHeading}><div><div className={css.breadcrumb}><span>{groupFor(view)}</span><CaretRight aria-hidden="true"/><strong>{viewInfo[view].label}</strong></div><AnimatedTitle>{viewInfo[view].title}</AnimatedTitle><p>{viewInfo[view].description}</p></div></header>
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
 useEffect(()=>{document.title=viewInfo[view].label+' | Guidefold';},[view]);
 // A route change moves the reading position and the keyboard focus together; #main is tabIndex -1.
 useEffect(()=>{window.scrollTo(0,0);document.getElementById('main')?.focus();},[location.pathname]);
 const href=(target:View,changes:Params={})=>{const next=new URLSearchParams(location.search);if(org)next.set('org',org);if(repo)next.set('repo',repo);Object.entries(changes).forEach(([k,v])=>v===null||v===undefined?next.delete(k):next.set(k,String(v)));const query=next.toString();return '/'+target+(query?'?'+query:'');};
 // A refused or revoked session is not a view state: every management route is private, so the
 // request leaves the shell for the full-width login page carrying where it was going (IA 3,
 // "Login jest stanem wejscia"). Import used to keep its own inline sign-in step; it does not.
 if(access.status==='denied')return <Navigate to={loginHref(location.pathname+location.search)} replace/>;
 if(!views.includes(name as View))return <Navigate to="/import" replace/>;
 const masked=foreign||access.status!=='confirmed';
 const ctx:ApiRouteContext={source,access,me,org,repo,role:membership?.role??null,params,view,href,go:(target,changes)=>navigate(href(target,changes)),recheckAccess:controller?(()=>controller.check(true)):undefined};
 const Content=apiRoute[view];
 return <Shell view={view} href={href}
  railContext={<><span>Workspace</span><strong>{masked?'Access unavailable':org}</strong><small>{masked?'Sign in or check access':repo??'No repository selected'}</small></>}
  topbar={<><span>{masked?'Workspace unavailable':membership?.name??'No organization'}</span>{!masked&&repo&&<code>{repo}</code>}</>}
  account={me?<AccountMenu name={me.user.name||me.user.email} email={me.user.email} role={membership?.role==='owner'?'Owner':'Member'} profileHref={href('organization',{tab:'members'})} onLogout={async()=>{await source.logout('logout:'+me.user.id);controller?.reportDenied();navigate('/login',{replace:true});}}/>:<Link className={css.signInLink} to={loginHref(location.pathname+location.search)}>Sign in</Link>}
  pageFoot="Hosted API. Publication, Git handoff and adapter delivery are separate steps and are not implied by anything on this page.">
 {foreign?<RouteState state="restricted" title="Organization unavailable" description="Your account is not a member of the organization named in this address. An organization in the URL is not authorization." action={<ActionButton href={href('import',{org:null,repo:null,step:'organization'})}>Choose an organization</ActionButton>}/>
 :access.status==='checking'?<RouteState state="loading" title="Confirming access" description="Checking membership before anything is shown."/>
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
 return <Suspense fallback={<RouteState state="loading" title="Loading sign-in" description="Preparing the sign-in page."/>}><LoginRoute source={source} returnTo={target}/></Suspense>;
}

export default function App({source}:{source:DataSource}){
 const location=useLocation();
 const toaster=<Suspense fallback={null}><ToastHost/></Suspense>;
 const path=location.pathname.replace(/^\//,'').replace(/\/$/,'');
 if(path==='__components')return <><Suspense fallback={<p>Loading component gallery</p>}><ComponentGallery/></Suspense>{toaster}</>;
 if(path==='login')return <><LoginEntry source={source}/>{toaster}</>;
 return <><ApiApp source={source}/>{toaster}</>;
}
