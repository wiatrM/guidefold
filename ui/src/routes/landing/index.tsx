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
 * The eight sections after the hero, fetched as their own chunk so the hero copy — which
 * is the LCP element, and which nothing can paint before React runs — does not wait on
 * `motion`, @base-ui and the Spectrum bento. See BelowHero.tsx for what moved and why.
 */
const BelowHero=lazy(()=>import('./BelowHero'));

/**
 * The landing route: the page shell, the header and the nine sections in reading order,
 * which is also DOM order, tab order and visual order at every breakpoint.
 *
 * `?confirm=` / `?unsubscribe=` renders `EmailAction` instead of all nine sections, drops
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
  <header className={css.nav}>
   <a className={css.brand} href="/" aria-label="Guidefold home"><img src="/assets/guidefold-mark-web.webp" width="38" height="38" alt=""/>Guidefold</a>
   <nav aria-label="Main navigation"><a href="#extraction">How it works</a><a href="/docs/">Docs</a><a href={github}>GitHub <ArrowUpRight aria-hidden="true"/></a></nav>
   <a data-slot="button" className={buttonVariants({variant:'outline',className:css.navAction})} href={emailAction?'/':'#waitlist'}>Join the waitlist</a>
  </header>
  <main id="main" tabIndex={-1}>{emailAction?<EmailAction {...emailAction}/>:<>

   <Hero/>
   {/* No fallback box: a placeholder sized for eight sections would be a layout shift
     * waiting to happen, and the boundary is below the fold at every measured width. */}
   <Suspense fallback={null}><BelowHero/></Suspense>

  </>}</main>
  <LandingFooter emailAction={Boolean(emailAction)}/>
 </div>;
}
