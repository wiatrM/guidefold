import {Why} from './Why';
import {Extraction} from './Extraction';
import {Portal} from './Portal';
import {Retrieval} from './Retrieval';
import {UnderTheHood} from './UnderTheHood';
import {Proof} from './Proof';
import {Questions} from './Questions';
import {WaitlistForm} from './WaitlistForm';
import {Reveal,RevealGroup} from './Reveal';
import {github} from './instruction';
import css from './landing.module.css';

/**
 * The eight screens after the hero, in reading order, which is also DOM order, tab order
 * and visual order at every breakpoint. They are one module because they are one chunk:
 * `index.tsx` loads them after the hero rather than with it.
 *
 * Why they are separated at all: the page's LCP element is hero copy that only React can
 * paint, so every byte the route imports statically lands on the critical path. These
 * screens carry `motion` (Extraction's scroll sampler, the number ticker) and @base-ui
 * (the reader's tabs, the FAQ's collapsibles), which rollup co-chunks into bytes the hero
 * never executes. Everything that paints above the fold — hero, film, header, footer —
 * stays in the route chunk and is unaffected.
 *
 * Nothing here is deferred *visually*: the boundary is below the fold at both measured
 * widths, so the arriving screens extend the page downward rather than displace anything
 * on screen, and the measured CLS stays 0.000. The demo dialog keeps its own, narrower
 * boundary; this one does not replace it.
 */
export default function BelowHero(){
 return <>
  <Why/>
  <Extraction/>
  <Portal/>
  <Retrieval/>
  <UnderTheHood/>
  <Proof/>

  <section id="waitlist" className={css.waitlist} aria-labelledby="waitlist-title">
   <div className={css.waitlistGrid}>
    <div className={css.waitlistCopy}>
    <Reveal pattern="p1" as="h2" id="waitlist-title" className={css.waitlistHeading}>{'Be first on hosted Guidefold.'}</Reveal>
    <p>{'One email when it is ready. Nothing else.'}</p>
    {/* Both statements are protected copy, moved here verbatim from the former
      * availability band, each with its detail sentence in its own inline element so it
      * stays independently addressable. */}
    <RevealGroup pattern="p1" as="div" className={css.availabilityStatements}>
     <p><strong>Open source today.</strong> <span>CLI and retrieval service.</span></p>
     <p><strong>Paid hosting is planned.</strong> <span>Sign up for availability updates.</span></p>
    </RevealGroup>
    <div className={css.availabilityLinks}>
     <a className={css.textLink} href={github+'#quickstart'}>Try the open-source version</a>
     <a className={css.textLink} href="/docs/">Read the docs</a>
    </div>
    </div>
    <WaitlistForm/>
   </div>
  </section>

  <Questions/>
 </>;
}
