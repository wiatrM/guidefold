import {lazy,Suspense,useEffect,useState} from 'react';
import {ArrowUpRight} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {FilmBackdrop} from './FilmBackdrop';
import {Hero} from './Hero';
import {EmailAction} from './WaitlistForm';
import {LandingFooter} from './Footer';
import {github} from './instruction';
import css from './landing.module.css';

/**
 * The eight screens after the hero, fetched as their own chunk so the hero — which holds
 * the LCP element, and which nothing can paint before React runs — does not wait on
 * `motion`, @base-ui and the number ticker. See BelowHero.tsx for what moved and why.
 */
const BelowHero=lazy(()=>import('./BelowHero'));

/**
 * The landing route: the page shell, the header and the nine sections of SPEC v3 in
 * reading order, which is also DOM order, tab order and visual order at every breakpoint:
 * hero, why, extraction, portal, how-it-works, under-the-hood, proof, waitlist, questions,
 * then the footer outside `<main>`.
 *
 * `?confirm=` / `?unsubscribe=` renders `EmailAction` instead of those sections, drops
 * the token from the URL, and never mounts the film (DESIGN.md 3.8) — hence the gate on
 * `FilmBackdrop`, which otherwise sits outside `<main>` and would mount on that branch.
 * It also never requests the sections below the hero.
 */
export default function Landing(){
 const [emailAction]=useState(()=>{const p=new URLSearchParams(window.location.search);return p.has('confirm')?{action:'confirm' as const,token:p.get('confirm')!}:p.has('unsubscribe')?{action:'unsubscribe' as const,token:p.get('unsubscribe')!}:null;});
 useEffect(()=>{document.title='Guidefold | Team instructions for coding agents';if(emailAction)window.history.replaceState(null,'','/');},[emailAction]);

 return <div className={css.page}>
  {!emailAction&&<FilmBackdrop/>}
  <a className={css.skip} href="#main">Skip to content</a>
  <div className={css.shell}><header className={css.nav}>
   <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-loader.webp" width="38" height="38" alt=""/>Guidefold</a>
   <nav aria-label="Main navigation"><a href="#extraction">How it works</a><a href="/docs/">Docs</a><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a></nav>
   <a data-slot="button" className={buttonVariants({variant:'outline',className:css.navAction})} href={emailAction?'/':'#waitlist'}>Join the waitlist</a>
  </header></div>
  <main id="main" tabIndex={-1}>{emailAction?<EmailAction {...emailAction}/>:<>

   <Hero/>
   {/* One viewport of reserved height, and no more. v3's hero is shorter than v2's, so
     * with no fallback at all the footer painted at y=612 on a throttled load and was
     * pushed off screen when the chunk arrived: one 0.32 layout shift, the only one on the
     * page. A fallback the height of the viewport keeps the footer below the fold until
     * the screens arrive, and the growth that replaces it happens off screen. Measured
     * CLS 0.000 at 1440 and 390 on emulated 4G. */}
   <Suspense fallback={<div className={css.belowHeroReserve}/>}><BelowHero/></Suspense>

  </>}</main>
  <LandingFooter emailAction={Boolean(emailAction)}/>
 </div>;
}
