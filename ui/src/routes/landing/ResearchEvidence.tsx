import {lazy,Suspense,useRef} from 'react';
import {useReducedMotion} from 'motion/react';
import evidence from '../../data/research-evidence.json';
import {Reveal,useRevealed} from './Reveal';
import {formatFigure as number,formatDelta as delta} from './format';
import {BentoCard} from '../../components/spectrumui/bento-card';
import {NumberTicker} from '../../components/spectrumui/number-ticker';
import css from './evidence.module.css';

const BarChart=lazy(()=>import('../../components/spectrumui/charts/bar-chart').then(m=>({default:m.BarChart})));
/** NumberTicker rounds `value` to an integer before formatting, so a two-decimal figure
 * is carried as hundredths and unscaled by `format` (DESIGN.md 4.1 P4). */
const centipp=(value:number)=>Math.round(value*100);
const formatPp=(value:number)=>(value/100).toFixed(2);
const labels:Record<string,string>={bigcodebench:'BigCodeBench',champ:'CHAMP',logicbench:'LogicBench',medcalcbench:'MedCalcBench',theoremqa:'TheoremQA',toolqa:'ToolQA'};
const data=[
 {category:'Recall@10',first:evidence.rates.flat.recall10,second:evidence.rates.full_pyramid.recall10},
 {category:'Complete@4',first:evidence.rates.flat.complete4,second:evidence.rates.full_pyramid.complete4},
];
const chartSeries:[{label:string;color:string},{label:string;color:string}]=[{label:'Flat dense search',color:'var(--stone-300)'},{label:'LLM map + scoped search',color:'var(--survey-teal)'}];

export function ResearchEvidence(){
 // The chart now lives once, in the tall bento tile below: it and the two tickers
 // ride the page's shared P3 observer pool through useRevealed rather than opening a
 // new IntersectionObserver each, so the same 30%-panel threshold that plays the
 // tile-settle animation also gates when the chart lazy-loads and when the tickers
 // arm their once-only roll (DESIGN.md 4.1, 5; Reveal.tsx keeps the page at two
 // observers). The pre-existing block below (table, interval paragraphs, Pi trace,
 // <details>, CTA) is otherwise untouched.
 const chartTileRef=useRef<HTMLDivElement>(null);
 const chartRevealed=useRevealed(chartTileRef);
 const tickerTileRef=useRef<HTMLDivElement>(null);
 const tickersRevealed=useRevealed(tickerTileRef);
 const reducedMotion=useReducedMotion();
 // Spotlight hover (DESIGN.md 4.3) is gated the same way Reveal.tsx's private
 // motionAllowed gates every other entrance and hover effect on this page: reduced
 // motion or Save-Data both turn it off. That helper is not exported, so the
 // Save-Data half is replicated here rather than imported.
 const saveData=typeof navigator!=='undefined'&&(navigator as Navigator&{connection?:{saveData?:boolean}}).connection?.saveData===true;
 const spotlightOn=!reducedMotion&&!saveData;
 // NumberTicker calls motion/react's own useInView unconditionally on mount, which
 // throws where IntersectionObserver does not exist (jsdom, and any platform without
 // it); the static fallback below already carries the exact final figure, so this
 // guard is the same "no IntersectionObserver, final state" degradation Reveal.tsx
 // and this file's own chart-visibility effect already use.
 const canTick=typeof IntersectionObserver!=='undefined';

 return <section id="research-results" className={css.research} aria-labelledby="research-title">
  <div className={css.copy}>
   <p className={css.eyebrow}>Research update · 10 September 2026</p>
   {/* copy.md 6: the headline figure comes from the same row and the same formatter the
     table below uses, so a refreshed mirror moves both together. */}
   <h2 id="research-title">{`Plus ${number(evidence.vs_flat.recall10.delta_pp)} points of recall over flat.`}</h2>
   <p className={css.subline}>{evidence.queries.toLocaleString('en-US')}{' queries across '}{evidence.skills.toLocaleString('en-US')}{' skills on SRA-Bench, against flat dense search.'}</p>
  </div>

  <div className={css.bento}>
   <Reveal pattern="p3" as="div" className={[css.tile,css.tileChart].join(' ')}>
    <BentoCard borderAnim={false} spotlight={spotlightOn} className={css.tileCard}>
     <p className={css.tileLabel}>Relevant skills retrieved and complete sets found (%)</p>
     <div ref={chartTileRef} className={css.bentoChart} role="group" aria-label="Benchmark comparison; exact values in the table below">
      {chartRevealed&&<Suspense fallback={null}><BarChart data={data} series={chartSeries}/></Suspense>}
     </div>
    </BentoCard>
   </Reveal>

   <Reveal pattern="p3" index={1} as="div" className={[css.tile,css.tileTicker].join(' ')}>
    <BentoCard borderAnim={false} spotlight={spotlightOn} className={css.tileCard}>
     <div ref={tickerTileRef} className={css.tickerGroup}>
      <div className={css.tickerRow}>
       <p className={css.tickerLabel}>Recall@10</p>
       {tickersRevealed&&canTick
        ?<NumberTicker value={centipp(evidence.vs_flat.recall10.delta_pp)} format={formatPp} prefix="+" suffix=" pp" startOnView={false} className={css.tickerValue}/>
        :<span className={css.tickerValue}>{delta(evidence.vs_flat.recall10.delta_pp)+' pp'}</span>}
       <p className={css.baseline}>{number(evidence.rates.flat.recall10)}{' → '}{number(evidence.rates.full_pyramid.recall10)}</p>
      </div>
      <div className={css.tickerRow}>
       <p className={css.tickerLabel}>Complete@4</p>
       {tickersRevealed&&canTick
        ?<NumberTicker value={centipp(evidence.vs_flat.complete4.delta_pp)} format={formatPp} prefix="+" suffix=" pp" startOnView={false} className={css.tickerValue}/>
        :<span className={css.tickerValue}>{delta(evidence.vs_flat.complete4.delta_pp)+' pp'}</span>}
       <p className={css.baseline}>{number(evidence.rates.flat.complete4)}{' → '}{number(evidence.rates.full_pyramid.complete4)}</p>
      </div>
      <p className={css.tileNote}>Measured, exploratory offline retrieval, not completed coding tasks. Four of six datasets improved; CHAMP and TheoremQA regressed. The hierarchy came from benchmark corpus prefixes rather than real repository scopes.</p>
     </div>
    </BentoCard>
   </Reveal>

   <Reveal pattern="p3" index={2} as="div" className={[css.tile,css.tileOpen].join(' ')}>
    <BentoCard borderAnim={false} spotlight={spotlightOn} className={css.tileCard}>
     <p className={css.tileNote}>{'Task-level value is not settled. '}<a className={css.inlineLink} href="#proof-gate">The delivery boundary in section 4</a>{' is deterministic and source-backed; it says nothing about whether a delivered rule helped somebody finish the work. That measurement needs real repository snapshots and frozen tasks, and we have not made it yet.'}</p>
    </BentoCard>
   </Reveal>

   <Reveal pattern="p3" index={3} as="div" className={[css.tile,css.tileScale].join(' ')}>
    <BentoCard borderAnim={false} spotlight={spotlightOn} className={css.tileCard}>
     <p className={css.tileNote}>{'Corpora of 1k, 10k and 30k skills, cold and warm cache: in the Q6 validation plan. '}<span className={css.warning}>Designed for, not yet measured.</span>{' No latency figure appears on this page until that run exists.'}</p>
    </BentoCard>
   </Reveal>
  </div>

  <figure className={css.researchFigure}>
   <table className={css.researchTable}>
    <caption>SRA-Bench results · experimental offline retrieval</caption>
    <thead><tr><th scope="col">Measure</th><th scope="col">Flat</th><th scope="col">LLM map</th><th scope="col">Change</th></tr></thead>
    <tbody>{data.map(row=><tr key={row.category}><th scope="row">{row.category}</th><td>{number(row.first)}%</td><td>{number(row.second)}%</td><td>{delta(row.second-row.first)} pp</td></tr>)}</tbody>
   </table>
   <p className={css.researchNote}><strong>Recall@10:</strong> the average share of labelled relevant skills in the first ten results. <strong>Complete@4:</strong> the share of queries with every required skill in the first four. Neither measures completed coding tasks.</p>
  </figure>
  <div className={css.researchFinding}>
   <p><strong>The generated text contributed.</strong> With the same extra search budget, the LLM map beat a control using only the source skill names and descriptions by {number(evidence.vs_metadata.recall10.delta_pp)} pp Recall@10 and {number(evidence.vs_metadata.complete4.delta_pp)} pp Complete@4.</p>
   <p><strong>Results vary by task family.</strong> Four of six datasets improved over flat search; CHAMP and TheoremQA regressed. This is an exploratory research result, pending validation on real monorepo tasks and integration into the default search path.</p>
  </div>
  <details className={css.researchDetails}>
   <summary>All six datasets, uncertainty and method</summary>
   <table className={css.researchTable}>
    <caption>LLM map minus flat search · percentage points</caption>
    <thead><tr><th scope="col">Dataset</th><th scope="col">Queries</th><th scope="col">Recall@10</th><th scope="col">Complete@4</th></tr></thead>
    <tbody>{Object.entries(evidence.datasets).map(([name,row])=><tr key={name}><th scope="row">{labels[name]}</th><td>{row.n}</td><td>{delta(row.metrics.recall10.full_vs_flat_pp)}</td><td>{delta(row.metrics.complete4.full_vs_flat_pp)}</td></tr>)}</tbody>
   </table>
   <p>Paired query bootstrap, 95% intervals: +7.46 to +9.60 pp Recall@10 and +3.83 to +5.91 pp Complete@4. Intervals across the six datasets include zero, so the pooled gain does not establish a general improvement across domains.</p>
   <p>A post-hoc check grouped queries sharing the same labelled skill set. Its 95% intervals were +3.64 to +14.10 pp Recall@10 and +0.83 to +9.39 pp Complete@4. This accounts for some reused labels; it does not resolve the differences between domains.</p>
   <p>The map produced a complete top-four set for 551 queries that flat search missed, while losing completeness on 288 others. Of those 551 gains, 200 required a skill outside the original dense top-50. These are retrieval outcomes from the same run, not completed user tasks.</p>
   <p>The map was built from corpus prefix groups and embedding clusters, not repository folders. It was fitted without query annotations. Each map arm added two scoped searches, with up to ten candidates each, to the same dense top-50. The first dense result was preserved, fixing Hit@1. Flat search used no extra scoped searches. The public corpus had already been inspected; this is not a fresh confirmatory holdout.</p>
   <p>Only 636 distinct skills appear in the answer labels; 25,626 web skills serve as unlabelled distractors. All labelled answers belong to the query dataset’s source family. This makes source-family routing a possible contributor and limits what this test says about a natural monorepo hierarchy.</p>
  </details>
  <div className={css.researchFinding}>
   <h3>Pi respected a missing-proof response</h3>
   <p>In one explicitly instructed session, Pi called Guidefold SEARCH and USE. Both selected skills lacked the required source proof. The service returned ASK without a body, and Pi reported that it had loaded neither skill.</p>
   <pre className={css.researchTrace} aria-label="Observed Pi session, shortened">{'SEARCH _root → software-engineering → development\nUSE × 2 → ASK: proof_missing\nBodies delivered: 0 · Skills reported as used: 0'}</pre>
   <p className={css.researchNote}>This checks the delivery boundary. Neither selected skill matched the task’s labelled answers (0/2); task execution was not tested. Pi received a bootstrap skill and mandatory SEARCH/USE/ASK instructions, so this was not a test of spontaneous tool adoption.</p>
  </div>
  <div className={css.availabilityLinks}>
   <a className={css.textLink} href="/docs/evidence/">Read the evidence</a>
   <a className={css.textLink} href="/evidence/research-2026-09-10.json" download>Download results and source hashes</a>
  </div>
 </section>;
}
