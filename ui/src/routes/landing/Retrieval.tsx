import {Reveal} from './Reveal';
import {IntroFigure} from './IntroFigure';
import {InstructionReader} from './InstructionReader';
import css from './retrieval.module.css';

/**
 * The Meridian fixture's own skill count for `examples/monorepo/`, not an invented figure:
 * `find examples/monorepo -iname SKILL.md | wc -l` on 2026-09-11. Labelled as the fixture's
 * count in the instrument itself, never presented as the marketing 30k-skill scale.
 */
const FIXTURE_SKILL_COUNT = 27;

/**
 * The four delivered cards, general first: the real ancestor chain in `examples/monorepo/`
 * for the query scope below (`_root` -> `atlas` -> `atlas.identity` -> `atlas.identity.turnstile`),
 * read from each SKILL.md's own `description` and `metadata.scope`. `postgres-auth` is the
 * "local rule that sharpens" the general ones, and it is the same fixture skill `InstructionReader`
 * shows in full beneath the instrument.
 */
const DELIVERED_CARDS=[
 {name:'security-baseline',scope:'_root',note:'Org-wide baseline: registries, image signing, secrets, TLS.'},
 {name:'atlas-api-conventions',scope:'atlas',note:'HTTP API rules for every atlas service.'},
 {name:'rbac-policies',scope:'atlas.identity',note:'Role model and OPA policy authoring for atlas.'},
 {name:'postgres-auth',scope:'atlas.identity.turnstile',note:'Turnstile auth: bearer tokens, principal lookup, RBAC.'},
] as const;

/**
 * Retrieval, DESIGN.md 3.3 as amended by conflict-table row 1: no proof figures here, only
 * the microcopy line naming the 30k design target and the Q6 validation plan. The instrument
 * is one glass panel, one `Reveal pattern="p3"` entrance for the whole thing, read left to
 * right in three zones. `IntroFigure` and `InstructionReader` re-home here unchanged, as the
 * "full text only when the agent asks for it" step.
 */
export function Retrieval(){
 return <section id="how-it-works" className={css.section} aria-labelledby="retrieval-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'What the agent gets'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="retrieval-title" className={css.heading}>{'Thirty thousand rules. Four reach the agent.'}</Reveal>
  <Reveal pattern="p1" as="p" index={2} className={css.subline}>
   {'Ranked by the task and by the place in the repository, in real time, every prompt.'}
  </Reveal>
  <Reveal pattern="p1" as="p" index={3} className={css.body}>
   {'General cards first, then the local rule that sharpens them, and full text only when the agent asks for it. Your context window carries four cards instead of a filing cabinet.'}
  </Reveal>

  <Reveal pattern="p3" as="div" className={css.instrument}>
   <div className={css.zone}>
    <p className={css.zoneLabel}>Query</p>
    <p className={css.queryTask}>{'task: rotate the service token'}</p>
    <p className={css.queryPath}>{'platforms/atlas/identity/turnstile/'}</p>
   </div>
   <div className={css.zone}>
    <p className={css.zoneLabel}>Candidates</p>
    <p className={css.candidateCount}>{FIXTURE_SKILL_COUNT}</p>
    <p className={css.candidateNote}>{'skills, Meridian fixture'}</p>
   </div>
   <div className={css.zone}>
    <p className={css.zoneLabel}>Delivered, general first</p>
    <ul className={css.cards}>
     {DELIVERED_CARDS.map(card=>
      <li key={card.name} className={css.card} data-delivered-card="" data-proof="complete">
       <p className={css.cardName}>{card.name}</p>
       <p className={css.cardScope}>{card.scope}</p>
       <p className={css.cardNote}>{card.note}</p>
       <p className={css.cardProof}><span className={css.proofDot} aria-hidden="true"/>{'Proof complete'}</p>
      </li>)}
    </ul>
   </div>
  </Reveal>

  <p className={css.microcopy}>
   {'Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.'}
  </p>

  <div className={css.fullText}>
   <IntroFigure/>
   <InstructionReader/>
  </div>

  <a className={css.textLink} href="https://github.com/wiatrM/guidefold#quickstart" target="_blank" rel="noreferrer">
   {'Try the open-source version'}
  </a>
 </section>;
}
