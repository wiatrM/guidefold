import {lazy,Suspense,useEffect,useState} from 'react';
import {ArrowDown,ArrowRight,Play} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {Reveal,RevealLines} from './Reveal';
import {DeviceFrame} from './DeviceFrame';
import shared from './landing.module.css';
import css from './hero.module.css';

function noop(){}

/**
 * The dialog is the whole `@base-ui/react/dialog` surface, and a static import of it put
 * 45 kB gzip in the first wave of a page whose LCP element is hero copy React has not
 * painted yet. Deferring it to the click keeps those bytes off the critical path.
 *
 * The placeholder is the same button with the same accessible name and the same classes,
 * and it is also the Suspense fallback, so "Play demo" is a real control in the DOM from
 * first paint to open dialog with nothing removed in between. Pointer and keyboard both
 * start the fetch before the click lands, so the usual path never sees the fallback.
 */
const DemoDialog=lazy(()=>import('./DemoDialog').then(module=>({default:module.DemoDialog})));
function warmDemoDialog(){void import('./DemoDialog');}

function PlayDemoButton({onClick}:{onClick?:()=>void}){
 return <button type="button" className={buttonVariants({variant:'outline',className:shared.actionQuiet})}
  onPointerEnter={warmDemoDialog} onFocus={warmDemoDialog} onClick={onClick}>
  <Play weight="fill" aria-hidden="true"/>Play demo
 </button>;
}

function DemoAction(){
 const [armed,setArmed]=useState(false);
 return armed
  ?<Suspense fallback={<PlayDemoButton/>}><DemoDialog defaultOpen onOpenChange={noop}/></Suspense>
  :<PlayDemoButton onClick={()=>setArmed(true)}/>;
}

/**
 * The hero, SPEC v3 screen 1: one headline, one sentence, two actions, one trust line and
 * one real screen of the product. Nothing else — no proof rail, no tier glyph, no demo
 * stage, no scroll-cue sentence. The arrow-down link to the first chapter is the only
 * chrome that survived, and it carries its destination in its accessible name.
 *
 * `data-hero-mounted` on the document element is the loader's "the page is really here"
 * signal; index.html's inline script waits for it and for `document.fonts.ready` before
 * it fades the overlay out. It is written from an effect, so it is set after React has
 * committed the hero rather than while it is rendering it.
 *
 * DOM order is tab order is visual order at every breakpoint, so the grid places by
 * column span alone and there is no CSS `order` anywhere.
 */
export function Hero(){
 useEffect(()=>{
  document.documentElement.dataset.heroMounted='true';
  return()=>{delete document.documentElement.dataset.heroMounted;};
 },[]);

 return <section id="hero" className={css.hero} aria-labelledby="hero-title">
  <div className={css.heroScrim} aria-hidden="true"/>

  <div className={css.heroCopy}>
   <RevealLines as="h1" id="hero-title" className={css.title}
    lines={["Your coding agent doesn't","know your team's rules.","Now it does."]}
    label="Your coding agent doesn't know your team's rules. Now it does."/>
   <Reveal pattern="p1" as="p" index={1} className={css.subline}>
    {"Your agents stop guessing your conventions. Rules live next to the code, CI lifts the good ones into your organisation's brain, and every agent gets exactly what fits the task."}
   </Reveal>
   <div id="demo" className={css.heroActions}>
    <a data-slot="button" className={buttonVariants({className:shared.action})} href="#waitlist">Join the waitlist <ArrowRight aria-hidden="true"/></a>
    <DemoAction/>
   </div>
   <p className={css.trust}>Open source today. The hosted service is planned.</p>
   <a className={css.scrollCue} href="#extraction" aria-label="Scroll to the extraction section">
    <ArrowDown weight="bold" aria-hidden="true"/>
   </a>
  </div>

  <div className={css.heroScreen}>
   <DeviceFrame eager src="/assets/landing/app/proposals.webp"
    alt="The Guidefold organisation portal: a rule proposed by CI beside the source it came from, waiting for an owner's approval."
    caption="The organisation portal, sample data"/>
  </div>
 </section>;
}
