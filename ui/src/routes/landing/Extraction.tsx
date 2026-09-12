import {useLayoutEffect,useRef,useState,type ReactNode} from 'react';
import {scroll} from 'motion';
import {Reveal} from './Reveal';
import {ValuePanel} from './ValuePanel';
import css from './extraction.module.css';

/**
 * Extraction, DESIGN.md 3.2: the pinned chapter, three beats, the page's centrepiece.
 *
 * A scroll track holds one `position: sticky` stage. The eyebrow and the h2 sit at the top
 * of the stage and do not move; the subline, the two body sentences and the microcopy line
 * of copy.md 2 section 2 are distributed across the three beats in that order, so the copy
 * is read once, in sequence.
 *
 * Base-state discipline, same as Reveal.tsx, and this file follows it in the CSS as well as
 * in the markup: **the pre-enhancement rules are the stacked fallback.** `position: sticky`,
 * the stage height, the track height, the single-cell grid, the crossfade, the chapter
 * parallax, the beat rail and the tier-route draw are every one of them keyed on
 * `[data-p-ready="true"]`, which is set only when a sampler is actually installed. With
 * JavaScript off, with a thrown error, at 1080 and below, under reduced motion and under
 * Save-Data the chapter is three stacked blocks, caption above instrument, in DOM order,
 * with no frozen 260 vh track above them and no two glass panels sharing a viewport.
 *
 * The sampler is motion's imperative `scroll()` rather than the `useScroll` hook, for one
 * reason: a hook cannot be conditional, and DESIGN.md 4.4 requires that under reduced
 * motion the sampler is never installed at all. It is the same primitive `useScroll`
 * wraps, `offset` makes progress an exact function of scroll position, and it therefore
 * reverses exactly. `--p` is written onto the stage element, never into React state.
 */

/**
 * DESIGN.md 4.2: beat windows at 0.0-0.33, 0.33-0.66 and 0.66-1.0, each handover a
 * crossfade of `BEAT_FADE` centred on the boundary. Since R2 this is the only place the
 * window arithmetic exists: the stylesheet reads the `--o` these numbers produce instead
 * of spelling them again in `clamp()`/`min()`, so the two can no longer drift.
 * `Extraction.test.tsx` asserts the shape of the curve and that the writer really puts
 * that curve on the beats and the ticks.
 */
export const BEAT_EDGES=[0.33,0.66] as const;
export const BEAT_FADE=0.06;

const ramp=(x:number)=>Math.min(1,Math.max(0,x));

export function beatOpacity(beat:1|2|3,p:number):number{
 const [first,second]=BEAT_EDGES,half=BEAT_FADE/2;
 if(beat===1)return ramp((first+half-p)/BEAT_FADE);
 if(beat===3)return ramp((p-(second-half))/BEAT_FADE);
 return Math.min(ramp((p-(first-half))/BEAT_FADE),ramp((second+half-p)/BEAT_FADE));
}

/** Which beat owns the pointer at this progress. Written as an attribute, only on change. */
export function activeBeat(p:number):1|2|3{
 const [first,second]=BEAT_EDGES;
 return p<first?1:p<second?2:3;
}

/**
 * The exact predicate scroll.ts and Reveal.tsx use, so the page enhances as one: reduced
 * motion and Save-Data both mean no sampler is installed at all.
 */
export function samplerAllowed(){
 if(typeof window==='undefined')return false;
 if(typeof window.matchMedia==='function'&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return false;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean}}).connection;
 return connection?.saveData!==true;
}

/**
 * The pin is a token decision, not a media query in this module: `--landing-stage-height`
 * is `auto` at 1080 and below and under reduced motion (tokens.css). The token is declared
 * on `:root`, so it is read there rather than off the stage. An empty value means no
 * stylesheet is applied at all, which is also not a pinned stage.
 */
function stageIsPinned(){
 if(typeof document==='undefined')return false;
 const height=getComputedStyle(document.documentElement).getPropertyValue('--landing-stage-height').trim();
 return height!==''&&height!=='auto';
}

/**
 * The four tiers of the Meridian fixture with the count of SKILL.md files declared at
 * each one: 26 rules over the 17 nodes of examples/monorepo/guidefold.yaml, the 27th file
 * being the generated hierarchy index. Bar length is scope breadth, narrowing as the tier
 * rises, which is the same geometry as the hero tier glyph (DESIGN.md 3.1); the count is
 * the number beside it. The instrument says which is which, because the two disagree.
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
 * The tier-route geometry, derived from one ladder rather than hand-placed.
 *
 * `SCOPE_LADDER` is the same 100/82/64/46 that tokens.css declares as
 * `--landing-scope-width-0..3` for the bars, and since 2026-09-12 that ladder is identical
 * at every breakpoint, so one set of stops lands on the bars at 1440 and at 390 alike.
 * `TIER_Y` are the bar centres in the 0-100 box: four rows of one 12 px mono line plus
 * `--space-1` plus an 8 px bar, separated by `--space-3`, which is 28 px on a 160 px stack.
 *
 * The invariant every stop keeps: a horizontal run lies inside the bar it runs along, and
 * a riser is inside the narrower of the two bars it joins. Hence `ROUTE_INSET` off the end
 * of the bar the route is climbing towards.
 */
const SCOPE_LADDER=[100,82,64,46] as const; // service, team, organisation, root
const ROUTE_INSET=14;
const TIER_Y=[97.5,70,42.5,15] as const;    // service at the bottom, root at the top
const ROUTE_STOPS=[
 SCOPE_LADDER[0]-12,
 ...SCOPE_LADDER.slice(1).map(width=>width-ROUTE_INSET),
 SCOPE_LADDER[3]-2*ROUTE_INSET,
];
const ROUTE_POINTS=TIER_Y
 .flatMap((y,i)=>[`${ROUTE_STOPS[i]},${y}`,`${ROUTE_STOPS[i+1]},${y}`])
 .join(' ');

/**
 * The dash run for the tier route, in rendered pixels. `vector-effect: non-scaling-stroke`
 * keeps the 2 px stroke even under the instrument's non-uniform scale, and it also makes
 * the browser measure dashes in rendered space rather than in path units, so `pathLength`
 * normalisation does not apply. One run longer than the route can ever be rendered gives
 * the same result: at rest, with `stroke-dashoffset="0"`, the whole route is drawn. The
 * draw moves `stroke-dasharray`, so the offset stays `0px` at every progress, which is the
 * value T12's end-to-end contract reads off this element.
 */
const ROUTE_RUN=2000;

/**
 * While the stage is pinned all three instruments are on screen at once, so P3 would fire
 * on three panels that are at opacity 0 and would have nothing to show. The pinned stage
 * owns their appearance through the crossfade; P3 belongs to the stacked fallback, where
 * each panel really does enter the viewport on its own.
 */
function Instrument({pinned,children}:{pinned:boolean;children:ReactNode}){
 return pinned
  ?<div className={css.instrument}>{children}</div>
  :<Reveal pattern="p3" className={css.instrument}>{children}</Reveal>;
}

export function Extraction(){
 const trackRef=useRef<HTMLDivElement|null>(null);
 const stageRef=useRef<HTMLDivElement|null>(null);
 const [pinned,setPinned]=useState(false);

 /**
  * A layout effect, not an effect: the enhancement collapses three flowed beats into one
  * grid cell, and on a deep link to `#extraction` or a mid-page reload that collapse would
  * be a visible layout shift if it happened after paint. React flushes the state change
  * from here before the browser paints, so the reader never sees the stacked arrangement
  * at a width where the pin is on.
  */
 useLayoutEffect(()=>{
  const track=trackRef.current,stage=stageRef.current;
  if(!track||!stage)return;
  let stop:VoidFunction|null=null;
  let beat=0;
  /**
   * R2: the sampler used to write one `--p` on the stage, which invalidated style for the
   * whole pinned subtree every frame. It now writes onto the elements that actually read
   * a value: `--o` on the three beats and the three ticks (the crossfade, evaluated here
   * with the same exported `beatOpacity` the stylesheet used to spell in `clamp()`), and
   * `--p` on the three panels, which are the common wrapper of the chapter parallax and,
   * for the third one, of the tier route's draw. Nine leaf writes instead of one write
   * with a subtree behind it.
   */
  const lit=(selector:string)=>[...stage.querySelectorAll<HTMLElement>(selector)];
  const beats=lit('[data-beat]'),ticks=lit('[data-tick]'),panels=lit('[data-panel]');
  const clear=()=>{
   for(const node of [...beats,...ticks])node.style.removeProperty('--o');
   for(const node of panels)node.style.removeProperty('--p');
  };
  const sync=()=>{
   const want=samplerAllowed()&&stageIsPinned();
   if(want&&!stop){
    stop=scroll((progress:number)=>{
     const p=progress.toFixed(4);
     for(const node of panels)node.style.setProperty('--p',p);
     for(let i=0;i<3;i++){
      const o=beatOpacity((i+1) as 1|2|3,progress).toFixed(3);
      beats[i]?.style.setProperty('--o',o);
      ticks[i]?.style.setProperty('--o',o);
     }
     const next=activeBeat(progress);
     if(next!==beat){beat=next;track.dataset.activeBeat=String(next);}
    },{target:track,offset:['start start','end end']});
   }else if(!want&&stop){
    stop();
    stop=null;
    beat=0;
    clear();
    delete track.dataset.activeBeat;
   }
   setPinned(want);
  };
  sync();
  // Reduced motion can be turned on mid-session. Without this the tokens would flip to
  // `auto` while `data-p-ready` stayed, which is the one combination that hides content.
  const reduced=typeof window.matchMedia==='function'?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
  window.addEventListener('resize',sync,{passive:true});
  reduced?.addEventListener('change',sync);
  return()=>{
   window.removeEventListener('resize',sync);
   reduced?.removeEventListener('change',sync);
   stop?.();
   clear();
   delete track.dataset.activeBeat;
  };
 },[]);

 return <section id="extraction" className={css.section} aria-labelledby="extraction-title">
  <div className={css.track} ref={trackRef} data-p-ready={pinned?'true':undefined}>
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
       <span className={css.tick1} data-tick="1"/>
       <span className={css.tick2} data-tick="2"/>
       <span className={css.tick3} data-tick="3"/>
      </div>
     </div>

     <div className={css.beat} data-beat="1">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'Written where the work is'}</h3>
       <p className={css.beatLede}>{'Guidefold finds the reusable part of a service rule,'}</p>
      </div>
      <Instrument pinned={pinned}>
       <div className={css.panel} data-panel="">
        <p className={css.panelLabel}>{'Sample data'}</p>
        <ol className={css.crumbs}>
         {FIXTURE_PATH.map(part=><li key={part}>{part}</li>)}
        </ol>
        <div className={css.fileRow}>
         <span className={css.fileName}>{'SKILL.md'}</span>
         <span className={css.fileScope}>{'atlas.identity.turnstile'}</span>
        </div>
       </div>
      </Instrument>
     </div>

     <div className={css.beat} data-beat="2">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'The reusable part is lifted'}</h3>
       <p className={css.beatLede}>{'promotes it a level, and shows an owner the diff.'}</p>
       <p className={css.beatBody}>{'Service, then team, then organisation.'}</p>
      </div>
      <Instrument pinned={pinned}>
       <div className={css.panel} data-panel="">
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
        <p className={css.panelNote}>{'Sample data'}</p>
       </div>
      </Instrument>
     </div>

     <div className={css.beat} data-beat="3">
      <div className={css.caption}>
       <h3 className={css.beatTitle}>{'It lands one level up'}</h3>
       <p className={css.beatLede}>{'The handbook nobody had time to write assembles itself out of work your teams already did, one reviewed diff at a time.'}</p>
       <p className={css.beatBody}>{'Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.'}</p>
      </div>
      <Instrument pinned={pinned}>
       <div className={css.panel} data-panel="">
        <p className={css.panelLabel}>{'Where the rules sit today'}</p>
        {/* Bar length and the number beside it encode different things and disagree on
          * purpose: team owns 13 rules on a narrower bar than service's 3, because the
          * bar is how wide the scope is, not how much is written in it. The header row
          * names both, so the panel answers that question on the instrument itself. */}
        <div className={css.tierHead}>
         <span>{'scope'}</span>
         <span>{'rules'}</span>
        </div>
        <div className={css.tiers}>
         <ol className={css.tierRows}>
          {TIERS.map(tier=><li key={tier.name} className={css.tierRow}>
           <span className={css.tierMeta}>
            <span className={css.tierName}>{tier.name}</span>
            <span className={css.tierCount}>{tier.count}</span>
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
           points={ROUTE_POINTS} strokeDasharray={ROUTE_RUN} strokeDashoffset={0}/>
         </svg>
        </div>
        <p className={css.panelNote}>{'Sample data, 26 rules across 17 nodes. Bar length is scope breadth.'}</p>
       </div>
      </Instrument>
     </div>

    </div>
   </div>
  </div>

  {/* The chapter's own answer to "what do I get", after the last beat and outside the
    * pinned track, so it is read once the three beats have finished rather than fading
    * with them. */}
  <div className={css.tail}>
   <ValuePanel>{"What you get: a fix written once by one team reaches every team that needs it, with an owner's approval, never by copy-paste."}</ValuePanel>
  </div>
 </section>;
}
