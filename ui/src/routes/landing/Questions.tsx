import {useEffect,useState,type ReactNode} from 'react';
import {Collapsible} from '@base-ui/react/collapsible';
import {CaretRight} from '@phosphor-icons/react';
import {Reveal,RevealGroup} from './Reveal';
import {github} from './instruction';
import css from './questions.module.css';

/**
 * The four protected objections, moved here verbatim from the v1 route. Ids, closed-on-load
 * state, hash deep-linking and the consent-link click handler are unchanged; a later task
 * restyles the trigger row, the caret and the panel.
 */
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

export function Questions(){
 return <section id="questions" className={css.section} aria-labelledby="questions-title">
  <Reveal pattern="p1" as="h2" id="questions-title" className={css.heading}>{'Before you join'}</Reveal>
  <Reveal pattern="p1" as="p" index={1} className={css.subline}>{'Price, availability, coding tools, and what happens to your email.'}</Reveal>
  <RevealGroup pattern="p1" as="div" className={css.questionList}>
     <Question id="question-1" title="Is Guidefold available now?"><p>The CLI and retrieval service are open source. Paid hosting is planned. Joining the waitlist gets you availability updates, not a hosted account or a guaranteed launch date.</p></Question>
     <Question id="question-2" title="What will hosting cost?"><p>The planned subscription is $99 per organisation per month, excluding taxes. With your own model key and CI, you pay those providers directly.</p><p>The planned managed-AI option adds a separate prepaid budget: $9 of provider usage costs $10. There is no unlimited AI allowance. Enterprise SSO is not included; hosted runner pricing and quotas will be specified before purchase.</p></Question>
     <Question id="question-3" title="Which coding tools can I use?"><p>The repository includes adapters for tools such as Claude Code, Codex and Copilot. Tool capabilities differ. Check the <a href={github+'#coding-harness-to-instruction-delivery'}>integration documentation</a> for the current support and limitations.</p></Question>
     <Question id="privacy" title="How is my email used?"><p>We store your email and consent in Guidefold’s database for hosted availability updates. Resend handles confirmation email delivery. We do not add you to unrelated mailing lists.</p><p>Confirm your address using the link we send. You can unsubscribe using the link in your email or ask <a href="mailto:hello@cloudfloo.io">hello@cloudfloo.io</a> to remove your signup. Unconfirmed signups are scheduled for deletion after 30 days. Confirmed and unsubscribed records are scheduled for deletion 365 days after signup. Unsubscribing removes your email immediately; a deduplication hash is retained until deletion to prevent repeat signup from restarting mail.</p><p>The demo connects to YouTube only when played. Its cover illustration is served by Guidefold. Email confirmation links do not load the demo.</p></Question>
  </RevealGroup>
 </section>;
}
