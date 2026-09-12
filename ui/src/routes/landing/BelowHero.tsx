import {Extraction} from './Extraction';
import {Retrieval} from './Retrieval';
import {ProofGate} from './ProofGate';
import {Telemetry} from './Telemetry';
import {ResearchEvidence} from './ResearchEvidence';
import {Availability} from './Availability';
import {Questions} from './Questions';
import {WaitlistForm} from './WaitlistForm';
import {Reveal} from './Reveal';
import css from './landing.module.css';

/**
 * The eight sections after the hero, in reading order, which is also DOM order, tab order
 * and visual order at every breakpoint. They are one module because they are one chunk:
 * `index.tsx` loads them after the hero rather than with it.
 *
 * Why they are separated at all: the page's LCP element is hero copy that only React can
 * paint, so every byte the route imports statically lands on the critical path. These
 * sections carry `motion` (Extraction's scroll sampler, the bento's whileInView, the
 * number ticker) and @base-ui (the reader's tabs, the FAQ's collapsibles), which rollup
 * co-chunks into 50.72 kB gzip that the hero never executes. Everything that paints above
 * the fold — hero, film, header, footer — stays in the route chunk and is unaffected.
 *
 * Nothing here is deferred *visually*: the boundary is below the fold at both measured
 * widths, so the arriving sections extend the page downward rather than displace anything
 * on screen, and the measured CLS stays 0.0000. The recharts bar chart and the demo dialog
 * keep their own, narrower boundaries; this one does not replace them.
 */
export default function BelowHero(){
 return <>
  <Extraction/>
  <Retrieval/>
  <ProofGate/>
  <Telemetry/>
  <ResearchEvidence/>
  <Availability/>

  <section id="waitlist" className={css.waitlist} aria-labelledby="waitlist-title">
   <div className={css.waitlistCopy}>
    <Reveal pattern="p1" as="h2" id="waitlist-title" className={css.waitlistHeading}>{'Be first on hosted Guidefold.'}</Reveal>
    <p>{'One email when it is ready. Nothing else.'}</p>
   </div>
   <WaitlistForm/>
  </section>

  <Questions/>
 </>;
}
