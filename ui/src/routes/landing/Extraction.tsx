import {useEffect,useRef} from 'react';
import {scroll} from 'motion';
import {Reveal} from './Reveal';
import css from './extraction.module.css';

/**
 * Extraction, DESIGN.md 3.2: the pinned chapter, three beats, the page's centrepiece.
 *
 * A scroll track of `--landing-stage-scroll` holds one `position: sticky` stage of
 * `--landing-stage-height`. The eyebrow and the h2 sit at the top of the stage and do not
 * move; the subline, the two body sentences and the microcopy line are distributed across
 * the three beats in copy.md order, so the copy is read once, in sequence.
 *
 * Base-state discipline, same as Reveal.tsx: the resting composition is the finished one.
 * With JavaScript off, under reduced motion, under Save-Data and at 1080 and below, both
 * stage tokens resolve to `auto`, `data-p-ready` is never set, and the three beats are
 * three stacked blocks at full opacity in the same DOM order. Nothing is hidden and
 * nothing is reordered; the crossfade, the chapter parallax, the beat rail and the tier
 * route draw are all keyed on `[data-p-ready="true"]`.
 *
 * The sampler is motion's imperative `scroll()` rather than the `useScroll` hook, for one
 * reason: a hook cannot be conditional, and DESIGN.md 4.4 requires that under reduced
 * motion the sampler is never installed at all. It is the same primitive `useScroll`
 * wraps, `offset` makes progress an exact function of scroll position, and it therefore
 * reverses exactly. `--p` is written onto the stage element, never into React state.
 */

/** The exact predicate scroll.ts and Reveal.tsx use, so the page enhances as one. */
function motionAllowed(){
 if(typeof window==='undefined')return false;
 if(typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return false;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
 return connection?.saveData!==true;
}

/**
 * The pin is a token decision, not a media query in this module: `--landing-stage-height`
 * is `auto` at 1080 and below and under reduced motion (tokens.css). Reading the token
 * keeps the breakpoint in one file. An empty value means no stylesheet is applied at all
 * (jsdom), which is also not a pinned stage.
 */
function pinned(stage:HTMLElement){
 const height=getComputedStyle(stage).getPropertyValue('--landing-stage-height').trim();
 return height!==''&&height!=='auto';
}

/**
 * The four tiers of the Meridian fixture with the count of SKILL.md files declared at
 * each one: 26 rules over the 17 nodes of examples/monorepo/guidefold.yaml, the 27th file
 * being the generated hierarchy index. Widths narrow as the tier rises, which is the same
 * geometry as the hero tier glyph (DESIGN.md 3.1).
 */
const TIERS=[
 {name:'root',count:5,bar:css.tierBar1},
 {name:'organisation',count:5,bar:css.tierBar2},
 {name:'team',count:13,bar:css.tierBar3},
 {name:'service',count:3,bar:css.tierBar4},
] as const;

/** The breadcrumb of the same fixture scope InstructionReader reads, so the page stays literal. */
const FIXTURE_PATH=['platforms','atlas','identity','turnstile','.agents','skills','postgres-auth'] as const;

/** Rules declared inside that one SKILL.md; every string is greppable in examples/monorepo. */
const STAYS=['legacyAuthMode','decision_cache','principal_roles'] as const;
const PROMOTED='Failure mode is closed';

/**
 * The dash run for the tier route, in rendered pixels. `vector-effect: non-scaling-stroke`
 * keeps the 2 px stroke even under the instrument's non-uniform scale, and it also makes
 * the browser measure dashes in rendered space rather than in path units, so `pathLength`
 * normalisation does not apply. One run longer than the route can ever be rendered gives
 * the same result: at rest, with `stroke-dashoffset="0"`, the whole route is drawn.
 */
const ROUTE_RUN=2000;

export function Extraction(){
 const trackRef=useRef<HTMLDivElement|null>(null);
 const stageRef=useRef<HTMLDivElement|null>(null);

 useEffect(()=>{
  const track=trackRef.current,stage=stageRef.current;
  if(!track||!stage||!motionAllowed())return;
  let stop:VoidFunction|null=null;
  const sync=()=>{
   if(pinned(stage)){
    if(stop)return;
    stage.dataset.pReady='true';
    stop=scroll((progress:number)=>{stage.style.setProperty('--p',progress.toFixed(4));},
     {target:track,offset:['start start','end end']});
   }else if(stop){
    stop();
    stop=null;
    delete stage.dataset.pReady;
    stage.style.removeProperty('--p');
   }
  };
  sync();
  window.addEventListener('resize',sync,{passive:true});
  return()=>{
   window.removeEventListener('resize',sync);
   stop?.();
   delete stage.dataset.pReady;
   stage.style.removeProperty('--p');
  };
 },[]);

 return <section id="extraction" className={css.section} aria-labelledby="extraction-title">
  <div className={css.track} ref={trackRef}>
   <div className={css.stage} ref={stageRef}>

    <div className={css.masthead}>
     <Reveal pattern="p1" as="p" className={css.eyebrow}>{'Where the rules come from'}</Reveal>
     <Reveal pattern="p1" as="h2" index={1} id="extraction-title" className={css.heading}>{"One team's fix becomes everyone's rule."}</Reveal>
    </div>

    <div className={css.beats}>

     {/* The beat rail: one hairline with three ticks, in the gap between the caption and
       * the instrument columns. It marks position in a sequence, so it exists only while
       * the stage is actually pinned and there is a position to mark. */}
     <div className={css.rail} aria-hidden="true">
      <div className={css.railLine}>
       <span className={css.tick1}/>
       <span className={css.tick2}/>
       <span className={css.tick3}/>
      </div>
     </div>

     <div className={css.beat} data-beat="1">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'Written where the work is'}</h3>
       <p className={css.beatLede}>{'Guidefold finds the reusable part of a service rule,'}</p>
      </div>
      <Reveal pattern="p3" className={css.instrument}>
       <div className={css.panel}>
        <p className={css.panelLabel}>{'Meridian fixture'}</p>
        <ol className={css.crumbs}>
         {FIXTURE_PATH.map(part=><li key={part}>{part}</li>)}
        </ol>
        <div className={css.fileRow}>
         <span className={css.fileName}>{'SKILL.md'}</span>
         <span className={css.fileScope}>{'atlas.identity.turnstile'}</span>
        </div>
       </div>
      </Reveal>
     </div>

     <div className={css.beat} data-beat="2">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'The reusable part is lifted'}</h3>
       <p className={css.beatLede}>{'promotes it a level, and shows an owner the diff.'}</p>
       <p className={css.beatBody}>{'Service, then team, then organisation.'}</p>
      </div>
      <Reveal pattern="p3" className={css.instrument}>
       <div className={css.panel}>
        <p className={css.panelLabel}>{'postgres-auth'}</p>
        <div className={css.diff}>
         <div className={css.diffColumn}>
          <p className={css.diffHead}>{'stays here'}</p>
          <ul className={css.diffList}>
           {STAYS.map(rule=><li key={rule}>{rule}</li>)}
          </ul>
          <p className={css.diffScope}>{'atlas.identity.turnstile'}</p>
         </div>
         <div className={css.diffColumn}>
          <p className={css.diffHead}>{'goes up'}</p>
          <ul className={css.diffList}>
           <li className={css.promoted} data-decision="human">
            <span>{PROMOTED}</span>
            <span className={css.promotedTag}>{'promoted'}</span>
           </li>
          </ul>
          <p className={css.diffScope}>{'atlas.identity'}</p>
         </div>
        </div>
        <p className={css.panelNote}>{'Meridian fixture'}</p>
       </div>
      </Reveal>
     </div>

     <div className={css.beat} data-beat="3">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'It lands one level up'}</h3>
       <p className={css.beatLede}>{'The handbook nobody had time to write assembles itself out of work your teams already did, one reviewed diff at a time.'}</p>
       <p className={css.beatBody}>{'Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.'}</p>
      </div>
      <Reveal pattern="p3" className={css.instrument}>
       <div className={css.panel}>
        <p className={css.panelLabel}>{'Where the rules sit today'}</p>
        <div className={css.tiers}>
         <ol className={css.tierRows}>
          {TIERS.map(tier=><li key={tier.name} className={css.tierRow}>
           <span className={css.tierMeta}>
            <span className={css.tierName}>{tier.name}</span>
            <span className={css.tierCount}>{tier.count} rules</span>
           </span>
           <span className={css.tierTrack}><span className={[css.tierBar,tier.bar].join(' ')}/></span>
          </li>)}
         </ol>
         {/* The one scroll-linked diagram on the page. It is a staircase rather than a
           * diagonal because the box is scaled non-uniformly: horizontal and vertical runs
           * survive that, a diagonal is sheared by it. Each horizontal run lies on the bar
           * of its tier, so the route reads as a rule resting at a tier and then climbing.
           * Its resting value is the finished route: the markup carries
           * `stroke-dashoffset="0"` and the draw exists only while the sampler drives. */}
         <svg className={css.tierSvg} viewBox="0 0 100 100" preserveAspectRatio="none"
          aria-hidden="true" focusable="false">
          <polyline data-tier-route="" className={css.tierRoute} vectorEffect="non-scaling-stroke"
           points="88,97.5 68,97.5 68,70 50,70 50,42.5 32,42.5 32,15 18,15"
           strokeDasharray={ROUTE_RUN} strokeDashoffset={0}/>
         </svg>
        </div>
        <p className={css.panelNote}>{'Meridian fixture, 26 rules across 17 nodes.'}</p>
       </div>
      </Reveal>
     </div>

    </div>
   </div>
  </div>
 </section>;
}
