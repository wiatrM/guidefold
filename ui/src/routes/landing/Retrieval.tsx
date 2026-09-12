import {Reveal,RevealGroup} from './Reveal';
import {DeviceFrame} from './DeviceFrame';
import {InstructionReader} from './InstructionReader';
import {ValuePanel} from './ValuePanel';
import css from './retrieval.module.css';

/**
 * Chapter 3, SPEC v3 screen 5. One instrument that reads like a story: what the developer
 * typed on the left, what the service did on the right, and the four cards it handed back
 * underneath. No "Query"/"Candidates" labels, no replay control, no mechanism clip — the
 * owner's note on the previous version was that you could not see what was asked or what
 * happened, so the panel now says both in plain words.
 *
 * Every mono detail below is real output of the shipped CLI against `examples/monorepo`,
 * recorded in DESIGN.md with the exact commands. The four named cards are the Meridian
 * fixture's own rules at the four levels of that repository's hierarchy, and each line
 * beneath a name is the opening clause of that SKILL.md's own `description`.
 */
const STEPS=[
 {name:'Found the scope',
  says:'This folder belongs to atlas › identity › turnstile.',
  detail:'scope: atlas.identity.turnstile'},
 {name:'Searched the rules in reach',
  says:'27 rules apply somewhere on that path; Guidefold scored them for this task.',
  detail:'SEARCH · 27 candidates · 4 selected'},
 {name:'Checked the proof',
  says:'Each chosen rule still matches the file it came from, at the revision it came from.',
  detail:'USE · source hash and revision verified · LOAD'},
 {name:'Handed the agent four cards',
  says:'General first, local last. Full text loads only when the agent asks.',
  detail:null},
] as const;

const CARDS=[
 {level:'Organisation',name:'security-baseline',
  says:'The org-wide security baseline every component must satisfy.'},
 {level:'Platform',name:'atlas-api-conventions',
  says:'HTTP API design rules for every atlas service.'},
 {level:'Team',name:'rbac-policies',
  says:'Authoring and testing the atlas RBAC policy bundle in OPA Rego.'},
 {level:'Service',name:'postgres-auth',
  says:'Add or change authorization checks in the turnstile service.'},
] as const;

export function Retrieval(){
 return <section id="how-it-works" className={css.section} aria-labelledby="retrieval-title">
  <div className={css.copy}>
   <Reveal pattern="p1" as="p" className={css.eyebrow}>{'3 · Fetch what fits'}</Reveal>
   <Reveal pattern="p1" as="h2" index={1} id="retrieval-title" className={css.heading}>
    {'Thirty thousand rules. Four reach the agent.'}
   </Reveal>
   <Reveal pattern="p1" as="p" index={2} className={css.lede}>
    {'At the start of a task, Guidefold walks your hierarchy and hands the agent the four rules that fit that folder and that job.'}
   </Reveal>
  </div>

  <div className={css.instrument}>
   <div className={css.asked}>
    <p className={css.zoneLabel}>{'What the developer typed'}</p>
    <p className={css.prompt}><span className={css.dollar} aria-hidden="true">{'$ '}</span>{'rotate the service token'}</p>
    <p className={css.promptWhere}>{'in platforms/atlas/identity/turnstile/'}</p>
   </div>

   <div className={css.did}>
    <p className={css.zoneLabel}>{'What Guidefold did'}</p>
    <RevealGroup pattern="p1" as="ol" className={css.steps}>
     {STEPS.map(step=>
      <li key={step.name} className={css.step}>
       <p className={css.stepName}>{step.name}</p>
       <p className={css.stepSays}>{step.says}</p>
       {step.detail&&<p className={css.stepDetail}>{step.detail}</p>}
      </li>)}
    </RevealGroup>
   </div>

   <ul className={css.cards}>
    {CARDS.map(card=>
     <li key={card.name} className={css.card} data-delivered-card="" data-proof="complete">
      <p className={css.cardHead}>
       <span className={css.cardLevel}>{card.level}</span>
       <span className={css.cardDot} aria-hidden="true">{' · '}</span>
       <span className={css.cardName}>{card.name}</span>
      </p>
      <p className={css.cardSays}>{card.says}</p>
      <p className={css.cardProof}><span className={css.proofDot} aria-hidden="true"/>{'Proof complete'}</p>
     </li>)}
   </ul>
  </div>
  <p className={css.instrumentCaption}>{'Sample data, the example repository in this project.'}</p>

  <div className={css.copy}>
   <ValuePanel>{"What you get: every task starts with the right conventions already in the agent's context, so fewer wrong pull requests and no hunting for the rule."}</ValuePanel>
  </div>

  <div className={css.screen}>
   <DeviceFrame src="/assets/landing/app/usage.webp"
    alt="The Guidefold usage view: a review queue and five delivery scorecards showing how often each rule was exposed, loaded and applied."
    caption="Afterwards, the portal shows which rule helped, sample data"/>
  </div>

  <details className={css.reader}>
   <summary className={css.readerSummary}>{'Read the full rule the agent loaded'}</summary>
   <div className={css.readerBody}><InstructionReader/></div>
  </details>
 </section>;
}
