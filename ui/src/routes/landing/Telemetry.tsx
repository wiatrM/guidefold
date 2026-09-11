import {Reveal} from './Reveal';
import css from './telemetry.module.css';

type AskReason='Conflicting rules'|'Missing dependencies'|'Revision changed';

type TeamRow={
 team:string;
 taskSuccess:string|null;
 safetyBoundary:string|null;
 funnel:string|null;
 costTime:readonly string[]|null;
 askReason:AskReason|null;
};

type ColumnKey=Exclude<keyof TeamRow,'team'>;

/**
 * Telemetry, DESIGN.md 3.5 with 7 decision 8. A labelled Meridian fixture, not a real
 * tenant: real per-team rows would be a tenancy and privacy question for a public page.
 * Hand-built against tokens; `@spectrumui/status-tracker` is deliberately not installed
 * here (recorded exception, DESIGN.md 3.5: its long-running-job framing would have to be
 * stripped down to less than it provides). Rows never animate (DESIGN.md 4.6 rejects
 * animated funnel bars): every value is already at its final state in the base DOM, and
 * the whole panel gets one P3 settle rather than a per-row stagger.
 *
 * Cost and time is three measures, not one string: it renders as three stacked lines
 * inside the cell rather than a single line joined with middle dots, which the anti-slop
 * gate reserves for decorative byline metadata, not an instrument's own data.
 */
const rows:readonly TeamRow[]=[
 {team:'Payments platform',taskSuccess:'94% (48 of 51 tasks)',safetyBoundary:'6 ASK, 0 loaded on conflict',funnel:'318 SEARCH → 92 USE',costTime:['21.4K tokens','58 tool calls','2m 40s'],askReason:'Conflicting rules'},
 {team:'Identity and access',taskSuccess:'88% (37 of 42 tasks)',safetyBoundary:'11 ASK, 0 loaded on conflict',funnel:'204 SEARCH → 61 USE',costTime:['14.9K tokens','33 tool calls','1m 55s'],askReason:'Revision changed'},
 {team:'Data platform',taskSuccess:null,safetyBoundary:'3 ASK, 0 loaded on conflict',funnel:'126 SEARCH → 40 USE',costTime:null,askReason:'Missing dependencies'},
 {team:'Growth',taskSuccess:'91% (29 of 32 tasks)',safetyBoundary:null,funnel:null,costTime:['9.2K tokens','22 tool calls','1m 05s'],askReason:null},
];

const columns:readonly {key:ColumnKey;label:string;isReason?:boolean}[]=[
 {key:'taskSuccess',label:'Task success'},
 {key:'safetyBoundary',label:'Safety boundary'},
 {key:'funnel',label:'SEARCH → USE'},
 {key:'costTime',label:'Cost and time'},
 {key:'askReason',label:'ASK reason',isReason:true},
];

/** A cell never shows a bare zero or a dash for missing data: it shows the word
 * `Unknown`, in the instrument itself, carrying `data-value="unknown"` so the rule is
 * checkable rather than only promised in the microcopy above. */
function Cell({label,value,isReason}:{label:string;value:string|readonly string[]|null;isReason?:boolean}){
 return <div className={css.cell}>
  <dt className={css.cellLabel}>{label}</dt>
  {value===null
   ?<dd className={css.cellValue} data-value="unknown">{'Unknown'}</dd>
   :Array.isArray(value)
    ?<dd className={css.cellValue}>{value.map(part=><span key={part} className={css.metaLine}>{part}</span>)}</dd>
    :<dd className={css.cellValue} data-ask-reason={isReason?value as string:undefined}>{value}</dd>}
 </div>;
}

export function Telemetry(){
 return <section id="telemetry" className={css.section} aria-labelledby="telemetry-title">
  <Reveal pattern="p1" as="p" className={css.eyebrow}>{'For the organisation'}</Reveal>
  <Reveal pattern="p1" as="h2" index={1} id="telemetry-title" className={css.heading}>{'You see which rule failed, and why.'}</Reveal>
  <Reveal pattern="p1" as="p" index={2} className={css.subline}>{'Per team: task success, ASK reasons, the SEARCH to USE funnel, tokens, tool calls, time.'}</Reveal>
  <Reveal pattern="p1" as="p" index={3} className={css.body}>{'ASK reasons come from a fixed vocabulary, so "Conflicting rules" and "Revision changed" arrive as counts you can act on rather than a log you have to read. Every pull request that touches a rule gets a report before merge: what changed, what collides, what an agent would now see.'}</Reveal>
  <Reveal pattern="p1" as="p" index={4} className={css.microcopy}>{'Missing data reads Unknown, never zero.'}</Reveal>

  <Reveal pattern="p3" as="div" className={css.panel}>
   <p className={css.fixtureLabel}><strong>{'Meridian fixture'}</strong>{': illustrative rows, not a live tenant or real telemetry.'}</p>
   <div className={css.rows}>
    {rows.map(row=>
     <dl key={row.team} className={css.row}>
      <div className={css.cell}>
       <dt className={css.cellLabel}>{'Team'}</dt>
       <dd className={css.cellValue+' '+css.team}>{row.team}</dd>
      </div>
      {columns.map(column=>
       <Cell key={column.key} label={column.label} value={row[column.key]} isReason={column.isReason}/>)}
     </dl>)}
   </div>
   <p className={css.gateRule}>{'Promotion gate: a rule reaches the default branch only once its clean-delivery streak holds and its pull-request report shows no unresolved collision.'}</p>
  </Reveal>
 </section>;
}
