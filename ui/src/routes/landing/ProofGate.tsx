import {Reveal} from './Reveal';
import evidence from '../../data/research-evidence.json';
import css from './proofgate.module.css';

/**
 * ProofGate, DESIGN.md 3.4. Type on film, not glass: columns 1-5 carry the copy, columns
 * 7-12 carry the two proof lines as a two-row stack with a hairline between them. The
 * figures are sentences rather than digits, so they set at `--landing-metric-unit`
 * weight and P4 never applies (DESIGN.md 4.1: a figure written as a sentence never
 * counts). One `--glow-system` sits under the block; it is the page's second and last
 * glow (the first is the retrieval instrument).
 *
 * copy.md section 4 is verbatim for the headline, subline and body. The two proof
 * lines read their figures from `evidence.proof_gate` rather than hard-coding them, so a
 * data refresh never requires a text edit here. Per copy.md section 5, when the mirror
 * is absent the section runs on its prose alone: no proof lines, no placeholder figure.
 */
const gate = evidence.proof_gate;

export function ProofGate(){
 return <section id="proof-gate" className={css.section} aria-labelledby="proof-gate-title">
  <div className={css.glow} aria-hidden="true"/>
  <div className={css.copy}>
   <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Safety boundary'}</Reveal>
   <Reveal pattern="p1" as="h2" index={1} id="proof-gate-title" className={css.heading}>{'Seventy-six harmful rules. Seventy-six refusals.'}</Reveal>
   <Reveal pattern="p1" as="p" index={2} className={css.subline}>{'The flat control loaded all 76. Guidefold answered ASK every single time.'}</Reveal>
   <Reveal pattern="p1" as="p" index={3} className={css.body}>{'Delivery requires a source proof: hash, revision, scope. Conflicting, stale and out-of-scope rules become an ASK, never a silent load and never a silent fallback, and every delivery traces back to the revision it came from.'}</Reveal>
  </div>
  {gate&&<div className={css.figures}>
   <Reveal pattern="p1" as="div" className={css.figure}>
    <p className={css.figureText}>
     {'ASK for all '}{gate.matrix.harmful_mutations}{' harmful mutations, LOAD for all '}{gate.matrix.safe_cases}{' safe cases. One-sided Wilson 95% upper bound for harmful delivery: '}{gate.matrix.wilson_upper_bound_pct}{'%.'}
    </p>
    <p className={css.qualifier}>{gate.microcopy}</p>
   </Reveal>
   <Reveal pattern="p1" as="div" className={css.figure}>
    <p className={css.figureText}>
     {'The same '}{gate.http_path.targets}{' safe targets came through the production '}{gate.http_path.handler}{' HTTP handler with '}
     <code>{'reason='+gate.http_path.reason}</code>
     {', source hash and range verified by the service.'}
    </p>
    <p className={css.qualifier}>{gate.microcopy}</p>
   </Reveal>
  </div>}
 </section>;
}
