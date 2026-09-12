import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import evidence from '../../data/research-evidence.json';
import css from './landing.module.css';

const BarChart=lazy(()=>import('../../components/spectrumui/charts/bar-chart').then(m=>({default:m.BarChart})));
const number=(value:number)=>value.toFixed(2);
const delta=(value:number)=>(value>0?'+':'')+number(value);
const labels:Record<string,string>={bigcodebench:'BigCodeBench',champ:'CHAMP',logicbench:'LogicBench',medcalcbench:'MedCalcBench',theoremqa:'TheoremQA',toolqa:'ToolQA'};
const data=[
 {category:'Recall@10',first:evidence.rates.flat.recall10,second:evidence.rates.full_pyramid.recall10},
 {category:'Complete@4',first:evidence.rates.flat.complete4,second:evidence.rates.full_pyramid.complete4},
];

export function ResearchEvidence(){
 const section=useRef<HTMLElement>(null);
 const [visible,setVisible]=useState(false);
 useEffect(()=>{
  if(!section.current||typeof IntersectionObserver==='undefined')return;
  const observer=new IntersectionObserver(entries=>{
   if(entries.some(entry=>entry.isIntersecting)){setVisible(true);observer.disconnect();}
  });
  observer.observe(section.current);
  return()=>observer.disconnect();
 },[]);
 return <section ref={section} id="research-results" className={css.research} aria-labelledby="research-title">
  <div className={css.copy}>
   <p className={css.eyebrow}>Research update · 10 September 2026</p>
   <h2 id="research-title">More relevant skills found</h2>
   <p className={css.answer}>An LLM-generated map of the skill library improved retrieval in our SRA-Bench experiment.</p>
   <p>Across {evidence.queries.toLocaleString('en-US')} queries and {evidence.skills.toLocaleString('en-US')} skills, the map raised Recall@10 by <strong>{delta(evidence.vs_flat.recall10.delta_pp)} percentage points</strong> over flat dense search. The model wrote summaries and example tasks for 28 groups; search used them to choose where to look next.</p>
  </div>
  <figure className={css.researchFigure}>
   <figcaption>Relevant skills retrieved and complete sets found (%)</figcaption>
   <div className={css.researchChart} role="group" aria-label="Benchmark comparison; exact values in the table below">
    {visible&&<Suspense fallback={null}><BarChart data={data} series={[{label:'Flat dense search',color:'var(--stone-300)'},{label:'LLM map + scoped search',color:'var(--survey-teal)'}]}/></Suspense>}
   </div>
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
