import {useEffect,useRef,useState,type ReactNode} from 'react';
import {Collapsible} from '@base-ui/react/collapsible';
import {ArrowDown,ArrowRight,ArrowUpRight,CaretRight} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {Card,CardContent,CardHeader,CardTitle} from '../../components/ui/card';
import {FilmBackdrop} from './FilmBackdrop';
import {IntroFigure} from './IntroFigure';
import {DemoDialog} from './DemoDialog';
import {InstructionReader} from './InstructionReader';
import {RouteRule} from './RouteRule';
import {ScopePyramid} from './ScopePyramid';
import {WaitlistForm,EmailAction} from './WaitlistForm';
import {LandingFooter} from './Footer';
import {ResearchEvidence} from './ResearchEvidence';
import {useSectionProgress} from './scroll';
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
 const why=useRef<HTMLElement>(null);
 const how=useRef<HTMLElement>(null);
 const value=useRef<HTMLElement>(null);
 useSectionProgress(page,field);
 useSectionProgress(hero);
 useSectionProgress(why);
 useSectionProgress(how);
 useSectionProgress(value);
 const [demoOpen,setDemoOpen]=useState(false);
 const [emailAction]=useState(()=>{const p=new URLSearchParams(window.location.search);return p.has('confirm')?{action:'confirm' as const,token:p.get('confirm')!}:p.has('unsubscribe')?{action:'unsubscribe' as const,token:p.get('unsubscribe')!}:null;});
 useEffect(()=>{document.title='Guidefold | Team instructions for coding agents';if(emailAction)window.history.replaceState(null,'','/');},[emailAction]);

 return <div ref={page} className={css.page}>
  <div ref={field} className={css.field} aria-hidden="true"><div className={css.topo}/><div className={css.survey}/></div>
  <FilmBackdrop/>
  <a className={css.skip} href="#main">Skip to content</a>
  <header className={css.nav}>
   <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-web.webp" width="38" height="38" alt=""/>Guidefold</a>
   <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="/docs/">Docs</a><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a></nav>
   <a data-slot="button" className={buttonVariants({variant:'outline',className:css.navAction})} href={emailAction?'/':'#waitlist'}>Join the waitlist</a>
  </header>
  <main id="main" tabIndex={-1}>{emailAction?<EmailAction {...emailAction}/>:<>

   <section ref={hero} className={css.hero} aria-labelledby="hero-title">
    <div className={css.heroScrim} aria-hidden="true"/>
    <div className={css.heroCopy}>
     <p className={css.eyebrow}>Instruction library for coding agents</p>
     <h1 id="hero-title">Team rules. Right where agents work.</h1>
     <p className={css.lede}>Rules stay next to the code. Guidefold copies the reusable part up the organisation pyramid, then gives each agent the few rules it needs.</p>
     <div id="demo" className={css.heroActions}>
      <a data-slot="button" className={buttonVariants({className:css.action})} href="#waitlist">Join the waitlist <ArrowRight aria-hidden="true"/></a>
      <DemoDialog onOpenChange={setDemoOpen}/>
     </div>
     <p className={css.trust}>Open source today. The hosted service is planned.</p>
     <a className={css.textLink} href="#research-results">New research: +8.53 pp Recall@10 on SRA-Bench <ArrowRight aria-hidden="true"/></a>
     <a className={css.scrollCue} href="#why" aria-label="Scroll down to see why Guidefold exists">
      <span className={css.scrollCueIcon} aria-hidden="true"><ArrowDown weight="bold"/></span>
      <span>Scroll to see how it works</span>
     </a>
    </div>
   </section>

   <section ref={why} id="why" className={css.why} aria-labelledby="why-title">
    <div className={[css.plane,css.planeWhy].join(' ')} aria-hidden="true"/>
    <span className={css.keyline} aria-hidden="true"/>
    <div className={css.copy}>
     <h2 id="why-title">Why we built it</h2>
     <p className={css.answer}>A rule for the payments service shouldn't become advice for every task in the monorepo.</p>
     <p>Put everything into the agent's starting context and that distinction gets hard to keep. Write a separate instruction file for each coding tool and you have another set of copies going stale.</p>
     <p>Big organisations have many teams and many rules. An agent cannot read all of it at once, so it guesses, reads the wrong file, or reads nothing.</p>
    </div>
   </section>

   <section ref={how} id="how-it-works" className={css.how} aria-labelledby="how-title">
    <div className={[css.plane,css.planeHow].join(' ')} aria-hidden="true"/>
    <div className={css.howIntro}>
     <h2 id="how-title">How it works</h2>
     <p className={css.answer}>Rules live in Git next to the code they describe, and Guidefold hands the agent only the few that apply where it is working.</p>
    </div>
    <div className={css.howFigure}><IntroFigure/><InstructionReader/></div>
    <div className={css.howDetail}>
     <dl className={css.beats}>
      <div><dt>Beside the code</dt><dd>A rule is a folder with one <code>SKILL.md</code>, under <code>.agents/skills/</code> inside the scope it belongs to. Git is the only source of truth.</dd></div>
      <div><dt>Selected by task and place</dt><dd>A hook finds the scope of the current folder, ranks every rule that scope can see, and prints at most four short cards, general first.</dd></div>
      <div><dt>Loaded on demand</dt><dd>The agent reads the full text of the one or two it needs.</dd></div>
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

   <section ref={value} id="value" className={css.value} aria-labelledby="value-title">
    <div className={[css.plane,css.planeValue].join(' ')} aria-hidden="true"/>
    <div className={css.copy}>
     <h2 id="value-title">What your team gets</h2>
     <p className={css.answer}>Day to day: a platform team gets one place to keep the rules, an owner gets a review step before anything reaches an agent, and a developer gets the right instruction without asking for it.</p>
    </div>
    <div className={css.roles}>{roles.map(item=><Card key={item.role} className={css.roleCard}>
     <CardHeader className={css.roleHeader}><p className={css.roleLabel}>{item.role}</p><CardTitle className={css.rolePromise}>{item.promise}</CardTitle></CardHeader>
     <CardContent><p className={css.roleDetail}>{item.detail}</p></CardContent>
    </Card>)}</div>
   </section>

   <ResearchEvidence/>

   <section className={css.availability} aria-label="Product availability">
    <div className={css.availabilityStatements}>
     <p><strong>Open source today.</strong> CLI and retrieval service.</p>
     <p><strong>Paid hosting is planned.</strong> Sign up for availability updates.</p>
    </div>
    <div className={css.availabilityLinks}>
     <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version <ArrowUpRight aria-hidden="true"/></a>
     <a className={css.textLink} href="/docs/">Read the docs</a>
    </div>
   </section>

   <section className={css.waitlist} aria-labelledby="waitlist-title">
    <div className={css.waitlistCopy}><h2 id="waitlist-title">Get availability updates</h2><p>One email when hosted Guidefold is ready. Nothing else.</p></div>
    <WaitlistForm/>
   </section>

   <section className={css.questions} aria-labelledby="questions-title">
    <h2 id="questions-title">Before you join</h2>
    <div className={css.questionList}>
     <Question id="question-1" title="Is Guidefold available now?"><p>The CLI and retrieval service are open source. Paid hosting is planned. Joining the waitlist gets you availability updates, not a hosted account or a guaranteed launch date.</p></Question>
     <Question id="question-2" title="What will hosting cost?"><p>The planned subscription is $99 per organisation per month, excluding taxes. With your own model key and CI, you pay those providers directly.</p><p>The planned managed-AI option adds a separate prepaid budget: $9 of provider usage costs $10. There is no unlimited AI allowance. Enterprise SSO is not included; hosted runner pricing and quotas will be specified before purchase.</p></Question>
     <Question id="question-3" title="Which coding tools can I use?"><p>The repository includes adapters for tools such as Claude Code, Codex and Copilot. Tool capabilities differ. Check the <a href={github+'#coding-harness-to-instruction-delivery'}>integration documentation</a> for the current support and limitations.</p></Question>
     <Question id="privacy" title="How is my email used?"><p>We store your email and consent in Guidefold’s database for hosted availability updates. Resend handles confirmation email delivery. We do not add you to unrelated mailing lists.</p><p>Confirm your address using the link we send. You can unsubscribe using the link in your email or ask <a href="mailto:hello@cloudfloo.io">hello@cloudfloo.io</a> to remove your signup. Unconfirmed signups are scheduled for deletion after 30 days. Confirmed and unsubscribed records are scheduled for deletion 365 days after signup. Unsubscribing removes your email immediately; a deduplication hash is retained until deletion to prevent repeat signup from restarting mail.</p><p>The demo connects to YouTube only when played. Its cover illustration is served by Guidefold. Email confirmation links do not load the demo.</p></Question>
    </div>
   </section>

  </>}</main>
  <LandingFooter emailAction={Boolean(emailAction)}/>
 </div>;
}
