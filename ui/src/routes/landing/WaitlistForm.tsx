import {useEffect,useRef,useState,type FormEvent} from 'react';
import {Button} from '../../components/ui/button';
import {ArrowRight,Check} from '@phosphor-icons/react';
import {submitWaitlist,WaitlistError,type WaitlistAction} from '../../data/waitlist';
import css from './landing.module.css';

type State='idle'|'sending'|'saved'|'error';

export function message(error:unknown){
 if(error instanceof WaitlistError){
  if(error.kind==='limited')return 'Too many attempts. Please try again in an hour.';
  if(error.kind==='invalid')return 'Please check your email and consent, then try again.';
  if(error.kind==='expired')return 'This link is invalid or expired. Contact hello@cloudfloo.io for help.';
 }
 return 'We could not confirm the request. Please try again. Your input is still here.';
}

/** Behaviour, ids, aria wiring, honeypot, 12s abort and every string are unchanged;
 * only the surface and the submit control were restyled. */
export function WaitlistForm(){
 const [email,setEmail]=useState(''),[consent,setConsent]=useState(false),[website,setWebsite]=useState('');
 const [state,setState]=useState<State>('idle'),[error,setError]=useState('');
 const active=useRef<AbortController|null>(null),result=useRef<HTMLDivElement>(null);
 useEffect(()=>()=>active.current?.abort(),[]);
 useEffect(()=>{if(state==='saved')result.current?.focus();},[state]);
 async function submit(event:FormEvent){
  event.preventDefault();if(active.current)return;
  const controller=new AbortController();active.current=controller;setState('sending');setError('');
  const timeout=setTimeout(()=>controller.abort(),12000);
  try{await submitWaitlist('join',{email:email.trim(),consent,website},controller.signal);setState('saved');setEmail('');}
  catch(e){setError(message(e));setState('error');}
  finally{clearTimeout(timeout);active.current=null;}
 }
 if(state==='saved')return <div ref={result} tabIndex={-1} role="status" aria-label="Waitlist confirmation" className={css.success}><Check aria-hidden="true"/><div><strong>Check your inbox to confirm.</strong><p>New signups receive one confirmation email. Repeat requests do not send another message. Already confirmed? You’re all set.</p><p>Missing the email? Contact <a href="mailto:hello@cloudfloo.io">hello@cloudfloo.io</a>.</p></div></div>;
 return <form id="waitlist-form" onSubmit={submit} className={css.form} aria-busy={state==='sending'}>
  <p className={css.signupNote}><strong>Paid hosting is planned.</strong> <span>Sign up for availability updates.</span></p>
  <label htmlFor="waitlist-email">Your email</label>
  <div className={css.formRow}>
   <input id="waitlist-email" name="email" type="email" autoComplete="email" inputMode="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com" aria-describedby={error?'waitlist-error waitlist-consent':'waitlist-consent'} aria-invalid={state==='error'||undefined}/>
   <Button className={css.action} type="submit" disabled={state==='sending'}>{state==='sending'?'Saving…':<>Join the waitlist<ArrowRight aria-hidden="true"/></>}</Button>
  </div>
  <div className={css.honeypot} aria-hidden="true"><label htmlFor="waitlist-website">Website</label><input id="waitlist-website" name="website" autoComplete="off" tabIndex={-1} value={website} onChange={e=>setWebsite(e.target.value)}/></div>
  <label className={css.consent} id="waitlist-consent"><input type="checkbox" name="consent" required checked={consent} onChange={e=>setConsent(e.target.checked)}/><span>Email me about hosted Guidefold. Unsubscribe anytime. <a href="#privacy">Privacy</a></span></label>
  {error&&<p role="alert" id="waitlist-error" className={css.error}>{error}</p>}
 </form>;
}

export function EmailAction({action,token}:{action:Exclude<WaitlistAction,'join'>;token:string}){
 const [state,setState]=useState<State>('idle'),[error,setError]=useState('');
 const active=useRef<AbortController|null>(null);
 useEffect(()=>()=>active.current?.abort(),[]);
 async function submit(){
  if(active.current)return;const controller=new AbortController();active.current=controller;setState('sending');
  const timeout=setTimeout(()=>controller.abort(),12000);
  try{await submitWaitlist(action,{token},controller.signal);setState('saved');}
  catch(e){setError(message(e));setState('error');}
  finally{clearTimeout(timeout);active.current=null;}
 }
 return <section className={css.emailAction} aria-labelledby="email-action-title">
  <h1 id="email-action-title">{action==='confirm'?'Confirm your email':'Leave the waitlist'}</h1>
  {state==='saved'
   ?<p role="status">{action==='confirm'?'You’re on the hosted Guidefold waitlist. We’ll email you about availability.':'You’ve been unsubscribed from the Guidefold waitlist.'}</p>
   :<><p>{action==='confirm'?'Confirm that you want updates about hosted Guidefold.':'Stop receiving hosted Guidefold updates.'}</p>
     <Button className={css.action} disabled={state==='sending'} onClick={()=>void submit()}>{state==='sending'?'Saving…':action==='confirm'?'Confirm email':'Unsubscribe'}</Button>
     {state==='error'&&<p role="alert" className={css.error}>{error}</p>}</>}
  <a href="/">Back to Guidefold</a>
 </section>;
}
