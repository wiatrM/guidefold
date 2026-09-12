import {Reveal,RevealGroup} from './Reveal';
import {DeviceFrame} from './DeviceFrame';
import {ValuePanel} from './ValuePanel';
import css from './underthehood.module.css';

/**
 * Under the hood, SPEC v3 screen 6. The owner's instruction: a visitor must learn that
 * Guidefold is a separate search server with a database of the organisation's rules, and
 * what SEARCH, USE and ASK actually are. Three panels, one verb each, in the product's
 * own words — no diagram, no chips, no numbers. The numbers live in the proof band.
 */
const CALLS=[
 {verb:'SEARCH',
  title:'The agent asks for the rules of this folder and this task.',
  says:'The service walks your hierarchy, scores every rule in reach and returns at most four short cards.'},
 {verb:'USE',
  title:'The agent asks to load one rule in full.',
  says:'The service checks that the rule still matches its source file at the right revision, then delivers it.'},
 {verb:'ASK',
  title:'The service refuses when something is off.',
  says:'A stale, conflicting or out-of-scope rule never loads silently; the agent stops and asks a human.'},
] as const;

export function UnderTheHood(){
 return <section id="under-the-hood" className={css.section} aria-labelledby="hood-title">
  <div className={css.grid}>
   <div className={css.copy}>
    <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Under the hood'}</Reveal>
    <Reveal pattern="p1" as="h2" index={1} id="hood-title" className={css.heading}>
     {'A search server for your rules, next to your Git.'}
    </Reveal>
    <Reveal pattern="p1" as="p" index={2} className={css.lede}>
     {'Guidefold is a separate service with a database of every rule in your organisation. Git stays the source of truth; the service is the fast index your agents call.'}
    </Reveal>
   </div>

   <RevealGroup pattern="p3" as="div" className={css.calls}>
    {CALLS.map(call=>
     <div key={call.verb} className={css.call}>
      <p className={css.verb}>{call.verb}</p>
      <p className={css.callTitle}>{call.title}</p>
      <p className={css.callSays}>{call.says}</p>
     </div>)}
   </RevealGroup>

   <div className={css.copy}>
    <p className={css.footnote}>
     {'It runs in CI to tidy and lift rules, and at every agent session start to fetch them. The organisation portal is the UI on top of the same service.'}
    </p>
    <ValuePanel>{'What you get: agents that never load a stale or wrong rule, and a service you can run yourself today or let us host.'}</ValuePanel>
   </div>

   <div className={css.screen}>
    <DeviceFrame src="/assets/landing/app/library.webp"
     alt="The Guidefold rule library: filters for scope, owner, layer and status above the rules of one scope, one of them expanded to its source path."
     caption="The rule database with your hierarchy, sample data"/>
   </div>
 </div>
 </section>;
}
