import {useEffect,useRef,useState,type ReactNode} from 'react';
import {Collapsible} from '@base-ui/react/collapsible';
import {ArrowRight,ArrowUpRight,CaretRight} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {FilmBackdrop} from './FilmBackdrop';
import {IntroFigure} from './IntroFigure';
import {DemoDialog} from './DemoDialog';
import {InstructionReader} from './InstructionReader';
import {RouteRule} from './RouteRule';
import {ScopePyramid} from './ScopePyramid';
import {WaitlistForm,EmailAction} from './WaitlistForm';
import {LandingFooter} from './Footer';
import {ScrollCue} from './ScrollCue';
import {useSectionProgress,useTrackProgress} from './scroll';
import {github} from './instruction';
import css from './landing.module.css';

function Question({id,title,children}:{id:string;title:string;children:ReactNode}){
 const [open,setOpen]=useState(()=>window.location.hash==='#'+id);
 const [pointerMotion,setPointerMotion]=useState(false);
 useEffect(()=>{
  function reveal(){if(window.location.hash==='#'+id){setPointerMotion(false);setOpen(true);}}
  function revealFromLink(event:MouseEvent){if(event.target instanceof Element&&event.target.closest('a[href="#'+id+'"]')){setPointerMotion(false);setOpen(true);}}
  window.addEventListener('hashchange',reveal);document.addEventListener('click',revealFromLink);
  return()=>{window.removeEventListener('hashchange',reveal);document.removeEventListener('click',revealFromLink);};
 },[id]);
 return <Collapsible.Root id={id} className={css.question} open={open} onOpenChange={setOpen} data-pointer-motion={pointerMotion} data-slot="collapsible">
  <h3><Collapsible.Trigger className={css.questionTrigger} onPointerDown={()=>setPointerMotion(true)} onKeyDown={()=>setPointerMotion(false)}><span>{title}</span><CaretRight aria-hidden="true"/></Collapsible.Trigger></h3>
  <Collapsible.Panel keepMounted className={css.questionPanel}><div>{children}</div></Collapsible.Panel>
 </Collapsible.Root>;
}

const roles=[
 {
  role:'Platform teams',
  promise:'One command installs the adapter for your harness and wires the hook.',
  detail:'Works across a monorepo and more than one coding tool; the repository ships adapters for tools such as Claude Code, Codex and Copilot, and their capabilities differ.',
 },
 {
  role:'Rule owners and tech leads',
  promise:'Every pull request that touches a rule gets a report before merge: what changed, what collides, what an agent would now see.',
  detail:'You also get usage numbers per rule: how often it was shown, how often the agent opened the full text, whether people said it helped.',
 },
 {
  role:'Developers',
  promise:'The agent starts with the rules for the folder it is in.',
  detail:'Nothing to paste into a prompt, nothing to remember. At most four cards, general first, and the full text only when it is needed.',
 },
];

export default function Landing(){
 const page=useRef<HTMLDivElement>(null);
 const field=useRef<HTMLDivElement>(null);
 const hero=useRef<HTMLElement>(null);
 const whyTrack=useRef<HTMLDivElement>(null);
 const why=useRef<HTMLElement>(null);
 const how=useRef<HTMLElement>(null);
 const valueTrack=useRef<HTMLDivElement>(null);
 const value=useRef<HTMLElement>(null);
 const nav=useRef<HTMLElement>(null);
 useSectionProgress(page,field);
 useSectionProgress(hero);
 useTrackProgress(whyTrack,why);
 useSectionProgress(how);
 useTrackProgress(valueTrack,value);
 const [demoOpen,setDemoOpen]=useState(false);
 const [emailAction]=useState(()=>{const p=new URLSearchParams(window.location.search);return p.has('confirm')?{action:'confirm' as const,token:p.get('confirm')!}:p.has('unsubscribe')?{action:'unsubscribe' as const,token:p.get('unsubscribe')!}:null;});
 useEffect(()=>{document.title='Guidefold | Team instructions for coding agents';if(emailAction)window.history.replaceState(null,'','/');},[emailAction]);
 // The pinned panels stick just below the nav; the nav's own height varies
 // with viewport width because its links wrap to extra rows, so the two
 // panels' `top` offset tracks the nav's real measured height rather than a
 // fixed token that would drift out of sync and let content pin under it.
 useEffect(()=>{
  const element=nav.current;
  if(!element||typeof ResizeObserver==='undefined')return;
  const root=document.documentElement;
  const measure=()=>root.style.setProperty('--landing-nav-live-height',element.getBoundingClientRect().height+'px');
  measure();
  const observer=new ResizeObserver(measure);
  observer.observe(element);
  return()=>{observer.disconnect();root.style.removeProperty('--landing-nav-live-height');};
 },[]);

 return <div ref={page} className={css.page}>
  <div ref={field} className={css.field} aria-hidden="true"><div className={css.topo}/><div className={css.survey}/></div>
  <FilmBackdrop/>
  {!emailAction&&<ScrollCue/>}
  <a className={css.skip} href="#main">Skip to content</a>
  <header ref={nav} className={css.nav}>
   <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-web.webp" width="38" height="38" alt=""/>Guidefold</a>
   <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="/docs/">Docs</a><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a></nav>
   <a data-slot="button" className={buttonVariants({variant:'outline',className:css.navAction})} href={emailAction?'/':'#waitlist'}>Join the waitlist</a>
  </header>
  <main id="main" tabIndex={-1}>{emailAction?<EmailAction {...emailAction}/>:<>

   <section ref={hero} className={css.hero} aria-labelledby="hero-title">
    <div className={css.heroScrim} aria-hidden="true"/>
    <div className={css.heroCopy}>
     <p className={css.eyebrow}>Skill retrieval for large organisations</p>
     <h1 id="hero-title">Thirty thousand skills. Nobody knows which four the agent should read.</h1>
     <p className={css.lede}>Every team writes its own, in its own repo and its own folders. They duplicate each other, nobody manages the set, and the knowledge never climbs from one service up to the organisation. Guidefold does that climb for you and serves the result to your agent.</p>
     <div id="demo" className={css.heroActions}>
      <a data-slot="button" className={buttonVariants({className:css.action})} href="#waitlist">Join the waitlist <ArrowRight aria-hidden="true"/></a>
      <DemoDialog onOpenChange={setDemoOpen}/>
     </div>
     <p className={css.trust}>Open source today. The hosted service is planned.</p>
    </div>
   </section>

   <div ref={whyTrack} className={css.track}>
    <section ref={why} id="why" className={[css.why,css.panel].join(' ')} aria-labelledby="why-title">
     <div className={[css.plane,css.planeWhy].join(' ')} aria-hidden="true"/>
     <span className={css.keyline} aria-hidden="true"/>
     <div className={css.copy}>
      <h2 id="why-title">Let's not make every team rediscover this from scratch</h2>
      <p className={css.answer}>At organisation scale, skills stop being documents and start being a data problem.</p>
      <dl className={css.beats}>
       <div><dt>Duplication</dt><dd>The same rule written five times, five ways, in five repositories. Each copy drifts. None of them is wrong enough for anyone to delete.</dd></div>
       <div><dt>No management</dt><dd>Nobody can see the whole set. Nobody can say which skills exist, who owns them, or what an agent will actually be shown when it opens a folder.</dd></div>
       <div><dt>No way up</dt><dd>One team figures out how to deploy safely. The next team hits the same incident and writes it again from zero, because there is no path for a local lesson to reach the rest of the organisation.</dd></div>
      </dl>
      <p className={css.trust}>Where a rule was written shouldn't decide where it can be used.</p>
     </div>
    </section>
   </div>

   <section ref={how} id="how-it-works" className={css.how} aria-labelledby="how-title">
    <div className={[css.plane,css.planeHow].join(' ')} aria-hidden="true"/>
    <div className={css.howIntro}>
     <h2 id="how-title">What Guidefold does about it</h2>
     <p className={css.answer}>It builds the pyramid, from the specific up to the general, and then automates the three things you would otherwise do by hand.</p>
    </div>
    <div className={css.howFigure}><IntroFigure/><InstructionReader/></div>
    <div className={css.howDetail}>
     <dl className={css.beats}>
      <div><dt>Search and USE</dt><dd>Every skill is extracted into a short abstract and placed at a level of your organisation. Retrieval ranks the abstracts that level can see with field-aware integer BM25F, scored per field rather than over one blob of text, and returns at most four cards, general first. USE then pins an exact revision and returns the full body, unchanged.</dd></div>
      <div><dt>Wired into your harness</dt><dd>A hook plugs the service into the coding tool your team already uses, so the right skills arrive on their own. Nothing to paste into a prompt, nothing to remember.</dd></div>
      <div><dt>Automatic CI</dt><dd>Every pull request that touches a skill gets checked on the way in: what changed, what now collides, what an agent would see afterwards. The pyramid stays true instead of rotting.</dd></div>
     </dl>
     <RouteRule/>
     <ScopePyramid/>
     <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version <ArrowUpRight aria-hidden="true"/></a>
     <details className={css.integrationDetail}>
      <summary>View the integration diagram <CaretRight aria-hidden="true"/></summary>
      <figure><img src="/assets/harness-integration.png" alt="Guidefold integration: coding tools request relevant instruction cards, then load selected instructions from the retrieval service." loading="lazy" width="1536" height="1024"/><figcaption>Task and repository location guide instruction selection.</figcaption></figure>
     </details>
    </div>
   </section>

   <div ref={valueTrack} className={css.track}>
    <section ref={value} id="value" className={[css.value,css.panel].join(' ')} aria-labelledby="value-title">
     <div className={[css.plane,css.planeValue].join(' ')} aria-hidden="true"/>
     <div className={css.copy}>
      <h2 id="value-title">What your team gets</h2>
      <p className={css.answer}>Nobody has to remember anything. The platform team keeps the rules in one place, the owner sees what changed before an agent ever reads it, and the developer just works.</p>
     </div>
     <div className={css.roles}>{roles.map(item=><article key={item.role} className={css.roleCard}>
      <p className={css.roleLabel}>{item.role}</p>
      <p className={css.rolePromise}>{item.promise}</p>
      <p className={css.roleDetail}>{item.detail}</p>
     </article>)}</div>
    </section>
   </div>

   <section className={css.availability} aria-label="Product availability">
    <div className={css.availabilityStatements}>
     <p><strong>Open source today.</strong> The CLI and the retrieval service, yours to run.</p>
     <p><strong>Hosting is planned.</strong> Not ready yet. We will tell you when it is.</p>
    </div>
    <div className={css.availabilityLinks}>
     <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version <ArrowUpRight aria-hidden="true"/></a>
     <a className={css.textLink} href="/docs/">Read the docs</a>
    </div>
   </section>

   <section className={css.waitlist} aria-labelledby="waitlist-title">
    <div className={css.waitlistCopy}><h2 id="waitlist-title">Want to know when hosting is ready?</h2><p>One email, on the day it opens. That is the whole list.</p></div>
    <WaitlistForm/>
   </section>

   <section className={css.questions} aria-labelledby="questions-title">
    <h2 id="questions-title">Things you are probably wondering</h2>
    <div className={css.questionList}>
     <Question id="question-1" title="Can I use it today?"><p>The CLI and the retrieval service are open source, so yes, if you run them yourself. Hosting is planned and not open. Joining the list gets you one email about availability, not an account and not a launch date.</p></Question>
     <Question id="question-2" title="What will hosting cost?"><p>The planned subscription is $99 per organisation per month, excluding taxes. With your own model key and CI, you pay those providers directly.</p><p>The planned managed-AI option adds a separate prepaid budget: $9 of provider usage costs $10. There is no unlimited AI allowance. Enterprise SSO is not included; hosted runner pricing and quotas will be specified before purchase.</p></Question>
     <Question id="question-3" title="Does it work with the tool my team already uses?"><p>The repository includes adapters for tools such as Claude Code, Codex and Copilot. Tool capabilities differ. Check the <a href={github+'#coding-harness-to-instruction-delivery'}>integration documentation</a> for the current support and limitations.</p></Question>
     <Question id="privacy" title="How is my email used?"><p>We store your email and consent in Guidefold’s database for hosted availability updates. Resend handles confirmation email delivery. We do not add you to unrelated mailing lists.</p><p>Confirm your address using the link we send. You can unsubscribe using the link in your email or ask <a href="mailto:hello@cloudfloo.io">hello@cloudfloo.io</a> to remove your signup. Unconfirmed signups are scheduled for deletion after 30 days. Confirmed and unsubscribed records are scheduled for deletion 365 days after signup. Unsubscribing removes your email immediately; a deduplication hash is retained until deletion to prevent repeat signup from restarting mail.</p><p>The demo connects to YouTube only when played. Its cover illustration is served by Guidefold. Email confirmation links do not load the demo.</p></Question>
    </div>
   </section>

  </>}</main>
  <LandingFooter emailAction={Boolean(emailAction)}/>
 </div>;
}
