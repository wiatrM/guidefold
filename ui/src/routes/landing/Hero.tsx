import {lazy,Suspense,useState} from 'react';
import {ArrowDown,ArrowRight,Play} from '@phosphor-icons/react';
import {buttonVariants} from '../../components/ui/button';
import {Reveal,RevealLines} from './Reveal';
import evidence from '../../data/research-evidence.json';
import {formatDelta} from './format';
import shared from './landing.module.css';
import css from './hero.module.css';

function noop(){}

/**
 * The dialog itself is the whole `@base-ui/react/dialog` surface, and it used to be a
 * static import of the hero, which put it in the first wave of a page whose LCP element
 * is hero copy React has not painted yet: 62.34 kB gzip of shared chunk before the
 * headline, 45.30 kB of it this dialog. Deferring it to the click moves those bytes off
 * the critical path (DESIGN.md 5, LCP).
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
 // DemoDialog's onOpenChange has no consumer anywhere on this page; the callback is
 // required by its signature, so it is satisfied here and flagged for the task that
 // owns DemoDialog to make optional.
 return armed
  ?<Suspense fallback={<PlayDemoButton/>}><DemoDialog defaultOpen onOpenChange={noop}/></Suspense>
  :<PlayDemoButton onClick={()=>setArmed(true)}/>;
}

/**
 * The hero, DESIGN.md 3.1. The film poster behind it stays the LCP element: nothing
 * here paints above it, no font or script blocks it, and both proof figures are in the
 * base DOM at their final values. P4 Count is deliberately absent (DESIGN.md 4.1 keeps
 * it out of the LCP window); the only entrance on the rail is P3 on the container.
 *
 * DOM order is tab order is visual order at every breakpoint, so the grid places by
 * column span alone and there is no CSS `order` anywhere.
 *
 * The first cell is conditional on the mirrored evidence (copy.md 5): a one-item strip
 * is fine, an unsourced figure is not. Both cells keep their qualifier at every
 * breakpoint; an item that cannot carry its qualifier is dropped whole.
 */
export function Hero(){
 return <section id="hero" className={css.hero} aria-labelledby="hero-title">
  <div className={css.heroScrim} aria-hidden="true"/>

  <div className={css.heroCopy}>
   <RevealLines as="h1" id="hero-title" className={css.title}
    lines={['Your repos are already','writing the handbook.']}/>
   <Reveal pattern="p1" as="p" index={1} className={css.subline}>
    {'Guidefold promotes what generalises, then hands your agent the four rules that apply, each one proven.'}
   </Reveal>
   <Reveal pattern="p1" as="p" index={2} className={css.body}>
    {'Ranking runs across the whole hierarchy in real time, designed for a 30k-skill corpus. Every rule arrives with its source proof attached, and the ones that cannot prove themselves never arrive at all.'}
   </Reveal>
   <div id="demo" className={css.heroActions}>
    <a data-slot="button" className={buttonVariants({className:shared.action})} href="#waitlist">Join the waitlist <ArrowRight aria-hidden="true"/></a>
    <DemoAction/>
   </div>
   <p className={css.trust}>Open source today. The hosted service is planned.</p>
   <a className={css.textLink} href="#research-results">Read the numbers and how we got them</a>
   <a className={css.scrollCue} href="#extraction" aria-label="Scroll to the extraction section">
    <span className={css.scrollCueIcon} aria-hidden="true"><ArrowDown weight="bold"/></span>
    <span>How rules move up</span>
   </a>
  </div>

  <Reveal pattern="p3" as="div" className={css.proofRail}>
   {evidence.proof_gate&&<div className={css.cell}>
    {/* copy.md 6: a citable figure is rendered from the evidence mirror, never typed into
      * the markup. Same source ProofGate reads, so the two can never disagree. */}
    <p className={css.figure}>{`${evidence.proof_gate.matrix.harmful_mutations} of ${evidence.proof_gate.matrix.harmful_asked} harmful rules refused.`}</p>
    <p className={css.qualifier}>{evidence.proof_gate.microcopy}</p>
   </div>}
   <div className={css.cell}>
    {/* Same source and same formatter as the research headline and the results table, so
      * a refreshed mirror moves the hero with them (copy.md 6). */}
    <p className={css.figure}>{`${formatDelta(evidence.vs_flat.recall10.delta_pp)} pp Recall@10 on SRA-Bench.`}</p>
    <p className={css.qualifier}>{'Measured, exploratory offline retrieval. 10 September 2026.'}</p>
   </div>
  </Reveal>

  {/* The pyramid mechanic above the fold without a paragraph. Orange appears three times
    * on the whole page and never anywhere else: this route, the extraction diff row, and
    * the full stop in the footer wordmark. */}
  <div className={css.tierGlyph} aria-hidden="true">
   <svg viewBox="0 0 160 128" className={css.glyph} role="presentation" focusable="false">
    <rect className={css.tier4} x="0" y="100" width="160" height="18" rx="2"/>
    <rect className={css.tier3} x="18" y="72" width="124" height="18" rx="2"/>
    <rect className={css.tier2} x="36" y="44" width="88" height="18" rx="2"/>
    <rect className={css.tier1} x="54" y="16" width="52" height="18" rx="2"/>
    {/* One polyline, drawn as a staircase so it reads as a rule climbing the tiers
      * rather than a diagonal laid across them. */}
    <polyline className={css.route} points="140,109 110,109 110,81 86,81 86,53 66,53 66,25 56,25"/>
   </svg>
  </div>
 </section>;
}
