import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {describe,it,expect,afterEach,beforeEach,vi} from 'vitest';
import {render,screen,act} from '@testing-library/react';
import {scroll} from 'motion';
import {Extraction,beatOpacity,activeBeat,samplerAllowed,BEAT_EDGES,BEAT_FADE} from './Extraction';

/**
 * `scroll` is the sampler. Spying on it is how "no sampler is installed" becomes an
 * assertion rather than a claim: DESIGN.md 4.4 requires that reduced motion and Save-Data
 * never install one, and finding 1 of the task-7 review requires the same when reduced
 * motion is turned on mid-session.
 */
vi.mock('motion',()=>({scroll:vi.fn(()=>vi.fn())}));
const sampler=vi.mocked(scroll);

/** The listeners `window.matchMedia` hands out, so a test can fire a `change` at them. */
const mediaListeners=new Set<(event:MediaQueryListEvent)=>void>();

function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({
  matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},
  addEventListener(_:string,listener:(event:MediaQueryListEvent)=>void){mediaListeners.add(listener);},
  removeEventListener(_:string,listener:(event:MediaQueryListEvent)=>void){mediaListeners.delete(listener);},
  dispatchEvent:()=>false,
 })) as unknown as typeof window.matchMedia;
}

function saveData(on:boolean){
 Object.defineProperty(navigator,'connection',{configurable:true,value:on?{saveData:true}:undefined});
}

/**
 * The pin is a token decision and the component reads `--landing-stage-height` off the
 * root. jsdom applies no stylesheet, so without this every path would look unpinned and
 * the sampler assertions would pass for the wrong reason.
 */
let tokens:HTMLStyleElement|null=null;
function stageTokens(height:string){
 tokens=document.createElement('style');
 tokens.textContent=':root{--landing-stage-height:'+height+'}';
 document.head.appendChild(tokens);
}

beforeEach(()=>{sampler.mockClear();mediaListeners.clear();});
afterEach(()=>{
 tokens?.remove();
 tokens=null;
 saveData(false);
 vi.restoreAllMocks();
});

describe('extraction chapter',()=>{
 it('keeps all three beats in the DOM in reading order',()=>{
  reduceMotion(false);
  const {container}=render(<Extraction/>);
  const beats=[...container.querySelectorAll('[data-beat]')].map(n=>(n as HTMLElement).dataset.beat);
  expect(beats).toEqual(['1','2','3']);
  expect(screen.getByRole('heading',{level:3,name:'Written where the work is'})).toBeVisible();
  expect(screen.getByRole('heading',{level:3,name:'The reusable part is lifted'})).toBeVisible();
  expect(screen.getByRole('heading',{level:3,name:'It lands one level up'})).toBeVisible();
 });

 it('carries the copy.md sentences verbatim across the beats',()=>{
  reduceMotion(false);
  render(<Extraction/>);
  expect(screen.getByText('Guidefold finds the reusable part of a service rule,')).toBeVisible();
  expect(screen.getByText('promotes it a level, and shows an owner the diff.')).toBeVisible();
  expect(screen.getByText('Service, then team, then organisation.')).toBeVisible();
  expect(screen.getByText(/assembles itself out of work your teams already did, one reviewed diff at a time\./)).toBeVisible();
  expect(screen.getByText('Promotion is a proposal. An owner approves it in Git, and Guidefold never edits a rule on its own.')).toBeVisible();
 });

 /**
  * T12's end-to-end contract reads `stroke-dashoffset` off this element and expects the
  * finished route. The draw moves `stroke-dasharray`, so the offset is the resting value
  * at every progress rather than only when the sampler is absent; this asserts the markup
  * half of that contract, and `qa/landing-v2` records the computed `0px` on the built
  * bundle, which is the half jsdom cannot see because it applies no CSS module.
  */
 it('rests with the tier route drawn complete',()=>{
  reduceMotion(true);
  const {container}=render(<Extraction/>);
  const route=container.querySelector('[data-tier-route]');
  expect(route).toBeInTheDocument();
  expect(route).toHaveAttribute('stroke-dashoffset','0');
  expect(route).toHaveAttribute('stroke-dasharray','2000');
 });

 it('marks exactly one promoted row as the human decision',()=>{
  reduceMotion(false);
  const {container}=render(<Extraction/>);
  expect(container.querySelectorAll('[data-decision="human"]')).toHaveLength(1);
 });

 it('names what the bar measures and what the number counts',()=>{
  reduceMotion(false);
  render(<Extraction/>);
  expect(screen.getByText('scope')).toBeVisible();
  expect(screen.getByText('rules')).toBeVisible();
  expect(screen.getByText(/Bar length is scope breadth\./)).toBeVisible();
 });
});

describe('extraction sampler',()=>{
 it('installs the sampler and marks the track when the stage is pinned',()=>{
  reduceMotion(false);
  stageTokens('100dvh');
  const {container}=render(<Extraction/>);
  expect(sampler).toHaveBeenCalledTimes(1);
  expect(container.querySelector('[data-p-ready="true"]')).toBeInTheDocument();
 });

 it('installs no sampler under reduced motion',()=>{
  reduceMotion(true);
  stageTokens('100dvh');
  const {container}=render(<Extraction/>);
  expect(sampler).not.toHaveBeenCalled();
  expect(container.querySelector('[data-p-ready]')).toBeNull();
 });

 it('installs no sampler under Save-Data',()=>{
  reduceMotion(false);
  saveData(true);
  stageTokens('100dvh');
  const {container}=render(<Extraction/>);
  expect(sampler).not.toHaveBeenCalled();
  expect(container.querySelector('[data-p-ready]')).toBeNull();
 });

 it('installs no sampler where the stage token says the pin is off',()=>{
  reduceMotion(false);
  stageTokens('auto');
  const {container}=render(<Extraction/>);
  expect(sampler).not.toHaveBeenCalled();
  expect(container.querySelector('[data-p-ready]')).toBeNull();
 });

 /**
  * Review finding 1: reduced motion can be turned on mid-session. Without a listener the
  * tokens flip to `auto` while `data-p-ready` stays, and the three beats sit in one grid
  * cell with `--p`-driven opacity over a collapsed track, which hides two of them.
  */
 it('tears the sampler down when reduced motion is turned on mid-session',()=>{
  reduceMotion(false);
  stageTokens('100dvh');
  const {container}=render(<Extraction/>);
  const stop=sampler.mock.results[0].value as ReturnType<typeof vi.fn>;
  expect(container.querySelector('[data-p-ready="true"]')).toBeInTheDocument();

  // The token swap the reduced-motion block performs, and the media change that follows.
  tokens!.textContent=':root{--landing-stage-height:auto}';
  reduceMotion(true);
  act(()=>{for(const listener of [...mediaListeners])listener({matches:true} as MediaQueryListEvent);});

  expect(stop).toHaveBeenCalled();
  expect(container.querySelector('[data-p-ready]')).toBeNull();
 });
});

describe('extraction beat windows',()=>{
 it('never leaves all three beats invisible',()=>{
  for(let step=0;step<=1000;step++){
   const p=step/1000;
   const total=beatOpacity(1,p)+beatOpacity(2,p)+beatOpacity(3,p);
   // The three windows partition [0,1] and each handover is a linear crossfade, so the
   // sum is 1 everywhere up to floating-point error. Never a dark frame.
   expect(total,'at --p '+p.toFixed(3)).toBeCloseTo(1,9);
  }
 });

 it('gives each beat the window DESIGN.md 4.2 assigns it',()=>{
  expect(beatOpacity(1,0)).toBe(1);
  expect(beatOpacity(2,0)).toBe(0);
  expect(beatOpacity(3,0)).toBe(0);
  expect(beatOpacity(2,0.5)).toBe(1);
  expect(beatOpacity(1,0.5)).toBe(0);
  expect(beatOpacity(3,0.5)).toBe(0);
  expect(beatOpacity(3,1)).toBe(1);
  expect(beatOpacity(1,1)).toBe(0);
  expect(beatOpacity(2,1)).toBe(0);
  // Exactly at a boundary the two neighbours share the frame half and half.
  expect(beatOpacity(1,BEAT_EDGES[0])).toBeCloseTo(0.5,6);
  expect(beatOpacity(2,BEAT_EDGES[0])).toBeCloseTo(0.5,6);
  expect(activeBeat(0)).toBe(1);
  expect(activeBeat(0.5)).toBe(2);
  expect(activeBeat(1)).toBe(3);
 });

 /**
  * The stylesheet evaluates the same expression in `clamp()`/`min()`, and CSS cannot import
  * the constants. This is the drift guard: change `BEAT_EDGES` or `BEAT_FADE` without
  * changing the module and the test fails here rather than in a screenshot review.
  */
 it('spells the same windows in extraction.module.css',()=>{
  // Vitest runs from ui/, and the module sits beside this file.
  const css=readFileSync(resolve('src/routes/landing/extraction.module.css'),'utf8');
  const [first,second]=BEAT_EDGES,half=BEAT_FADE/2,fade=BEAT_FADE.toFixed(2);
  const expected=[
   '('+(first+half).toFixed(2)+' - var(--p)) / '+fade,
   '(var(--p) - '+(first-half).toFixed(2)+') / '+fade,
   '('+(second+half).toFixed(2)+' - var(--p)) / '+fade,
   '(var(--p) - '+(second-half).toFixed(2)+') / '+fade,
  ];
  for(const fragment of expected)expect(css,fragment).toContain(fragment);
 });
});

describe('extraction sampler predicate',()=>{
 it('refuses reduced motion and Save-Data',()=>{
  reduceMotion(false);
  expect(samplerAllowed()).toBe(true);
  saveData(true);
  expect(samplerAllowed()).toBe(false);
  saveData(false);
  reduceMotion(true);
  expect(samplerAllowed()).toBe(false);
 });
});
