import {Reveal} from './Reveal';
import {DeviceFrame} from './DeviceFrame';
import {ValuePanel} from './ValuePanel';
import css from './portal.module.css';

/**
 * Chapter 2, SPEC v3 screen 4: the organisation's brain. One headline, one sentence, one
 * real screen of the review view, one value line. The screen is the Proposals route of
 * the hosted UI captured against the Meridian fixture, which is the only place on the
 * page where a visitor sees an owner actually approving a rule.
 */
export function Portal(){
 return <section id="portal" className={css.section} aria-labelledby="portal-title">
  <div className={css.copy}>
   <Reveal pattern="p1" as="p" className={css.eyebrow}>{'2 · Share up'}</Reveal>
   <Reveal pattern="p1" as="h2" index={1} id="portal-title" className={css.heading}>
    {"Your organisation's brain, reviewed by owners."}
   </Reveal>
   <Reveal pattern="p1" as="p" index={2} className={css.lede}>
    {'CI proposes the rule one level up. An owner approves it in the portal, and every team beneath gets it.'}
   </Reveal>
   <ValuePanel>{"What you get: a living handbook of your organisation that writes itself from the teams' work, and one place to see and approve what every agent will follow."}</ValuePanel>
  </div>

  <div className={css.screen}>
   <DeviceFrame src="/assets/landing/app/proposals.webp"
    alt="The Guidefold proposals view: a source skill beside the candidate CI generated from it, with the scope, the owner and the target revision."
    caption="Proposals view, sample data"/>
  </div>
 </section>;
}
