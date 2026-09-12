import {afterEach,beforeAll,beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen,waitFor,fireEvent,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import Landing from './landing';
import {submitWaitlist,WaitlistError} from '../data/waitlist';
import evidence from '../data/research-evidence.json';

vi.mock('../data/waitlist',async original=>({...await original<typeof import('../data/waitlist')>(),submitWaitlist:vi.fn()}));

const realMatchMedia=window.matchMedia;
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({
  matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false,
 })) as unknown as typeof window.matchMedia;
}
let errors:unknown[][];
beforeEach(()=>{errors=[];vi.spyOn(console,'error').mockImplementation((...args)=>{errors.push(args);});});
afterEach(()=>{vi.restoreAllMocks();vi.clearAllMocks();window.matchMedia=realMatchMedia;window.history.replaceState(null,'','/');});

async function fill(){
 const user=userEvent.setup();
 await user.type(screen.getByLabelText('Your email'),'person@example.test');
 await user.click(screen.getByRole('checkbox'));
 return user;
}

/** The eight sections under the hero are their own chunk (index.tsx defers BelowHero so
 * the hero copy, which is the LCP element, is not behind `motion` and @base-ui), so they
 * arrive one module load after render. Every assertion about them waits for it. */
beforeAll(async()=>{await import('./landing/BelowHero');});
async function renderLanding(ui=<Landing/>){
 const result=render(ui);
 await screen.findByRole('heading',{name:'Before you join'},{timeout:4000});
 return result;
}

describe('public landing',()=>{
 it('has no structural axe violations (contrast requires browser layout)',async()=>{
  const {container}=await renderLanding();
  const result=await axe.run(container,{rules:{'color-contrast':{enabled:false}}});
  expect(result.violations).toEqual([]);
  expect(errors).toEqual([]);
 // axe now scans the page only after the deferred sections have arrived, so this case
 // pays one module load on top of the scan; the default 5 s is no longer enough headroom.
 },15000);

 it('opens on the outcome and orders the nine sections',async()=>{
  const {container}=await renderLanding();
  expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1);
  expect(screen.getByRole('heading',{level:1,name:'Your repos are already writing the handbook.'})).toBeInTheDocument();
  const ids=[...container.querySelectorAll('main section[id]')].map(n=>n.id);
  expect(ids).toEqual(['hero','extraction','how-it-works','proof-gate','telemetry','research-results','availability','waitlist','questions']);
  expect(container.querySelector('a[href="#extraction"]')).toBeInTheDocument();
 });

 it('renders both hero proof cells with their qualifiers in full',async()=>{
  await renderLanding();
  expect(screen.getByText('76 of 76 harmful rules refused.')).toBeVisible();
  expect(screen.getAllByText('Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.').length).toBeGreaterThan(0);
  expect(screen.getByText('+8.53 pp Recall@10 on SRA-Bench.')).toBeVisible();
  expect(screen.getByText('Measured, exploratory offline retrieval. 10 September 2026.')).toBeVisible();
 });

 // Final review I1: the hero figure used to be typed into the markup, so a refreshed
 // mirror would have left it announcing a superseded count. The expectation is built from
 // the same JSON the component reads, so only the coupling can keep this green.
 it('derives the hero refusal figure from the evidence mirror',async()=>{
  await renderLanding();
  const m=evidence.proof_gate.matrix;
  expect(screen.getByText(`${m.harmful_mutations} of ${m.harmful_asked} harmful rules refused.`)).toBeVisible();
 });

 // Follow-up wave, 2026-09-12: the second rail cell was the last citable figure still
 // typed into the markup. The expectation is formatted here from the same row the
 // research headline and the results table read, with the table's two-decimal signed
 // form spelled out rather than imported, so the rendered hero fails this if it ever
 // stops deriving the number.
 it('derives the hero recall figure from the evidence mirror',async()=>{
  await renderLanding();
  const d=evidence.vs_flat.recall10.delta_pp;
  const expected=(d>0?'+':'')+d.toFixed(2);
  expect(screen.getByText(`${expected} pp Recall@10 on SRA-Bench.`)).toBeVisible();
 });

 it('gives the scroll cue one agreeing label, name and destination',async()=>{
  await renderLanding();
  const cue=screen.getByRole('link',{name:'Scroll to the extraction section'});
  expect(cue).toHaveAttribute('href','#extraction');
  expect(cue).toHaveTextContent('How rules move up');
 });

 it('keeps every protected destination and the availability statements',async()=>{
  const {container}=await renderLanding();
  const href=(selector:string)=>container.querySelector(selector);
  expect(href('a[href="#extraction"]')).toBeInTheDocument();      // nav, copy.md 5
  expect(container.querySelector('section#how-it-works')).toBeInTheDocument(); // v1 inbound anchor still resolves
  expect(href('a[href="#waitlist"]')).toBeInTheDocument();
  expect(href('a[href="#demo"]')).toBeInTheDocument();
  expect(href('a[href="#privacy"]')).toBeInTheDocument();
  expect(href('a[href="/docs/"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold#quickstart"]')).toBeInTheDocument();
  expect(href('a[href="https://github.com/wiatrM/guidefold#coding-harness-to-instruction-delivery"]')).toBeInTheDocument();
  expect(href('a[href="mailto:hello@cloudfloo.io"]')).toBeInTheDocument();
  expect(container.querySelector('#demo')).toBeInTheDocument();
  expect(container.querySelector('#waitlist')).toBeInTheDocument();
  for(const id of ['question-1','question-2','question-3','privacy'])expect(container.querySelector('#'+id)).toBeInTheDocument();
  expect(screen.getByText('Open source today.')).toBeInTheDocument();
  expect(screen.getByText('Paid hosting is planned.')).toBeInTheDocument();
  expect(screen.getByText('Open-source tools. Hosted service planned.')).toBeInTheDocument();
  expect(document.title).toBe('Guidefold | Team instructions for coding agents');
  expect(screen.getByRole('link',{name:'Skip to content'})).toHaveAttribute('href','#main');
 });

 it('keeps all four answers in the DOM with every panel closed on load',async()=>{
  await renderLanding();
  for(const question of ['Is Guidefold available now?','What will hosting cost?','Which coding tools can I use?','How is my email used?'])
   expect(screen.getByRole('button',{name:question})).toHaveAttribute('aria-expanded','false');
  expect(screen.getByText(/\$99 per organisation per month/)).toBeInTheDocument();
  expect(screen.getByText(/Unconfirmed signups are scheduled for deletion after 30 days/)).toBeInTheDocument();
 });

 it('opens the privacy disclosure from a direct anchor',async()=>{
  window.history.replaceState(null,'','/#privacy');
  await renderLanding();
  expect(screen.getByRole('button',{name:'How is my email used?'})).toHaveAttribute('aria-expanded','true');
 });

 it('makes no signup request on arrival and requires explicit consent',async()=>{
  await renderLanding();
  expect(submitWaitlist).not.toHaveBeenCalled();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(screen.getByRole('checkbox')).toBeRequired();
  expect(screen.getByLabelText('Your email')).toBeRequired();
  expect(screen.queryByTitle('Guidefold product demo')).not.toBeInTheDocument();
 });

 it('waits for acceptance, prevents duplicate submits, then focuses confirmation',async()=>{
  let finish!:()=>void;
  vi.mocked(submitWaitlist).mockImplementation(()=>new Promise<void>(r=>{finish=r;}));
  await renderLanding();
  const user=await fill();
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(screen.getByRole('button',{name:'Saving…'})).toBeDisabled();
  fireEvent.submit(document.getElementById('waitlist-form')!);
  expect(submitWaitlist).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('status',{name:'Waitlist confirmation'})).not.toBeInTheDocument();
  finish();
  await waitFor(()=>expect(screen.getByRole('status',{name:'Waitlist confirmation'})).toHaveFocus());
  expect(submitWaitlist).toHaveBeenCalledWith('join',{email:'person@example.test',consent:true,website:''},expect.any(AbortSignal));
  expect(screen.queryByLabelText('Your email')).not.toBeInTheDocument();
 });

 it('preserves input on rate limiting and allows retry',async()=>{
  vi.mocked(submitWaitlist).mockRejectedValueOnce(new WaitlistError('limited')).mockResolvedValueOnce();
  await renderLanding();
  const user=await fill();
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Please try again in an hour.');
  expect(screen.getByLabelText('Your email')).toHaveValue('person@example.test');
  await user.click(screen.getByRole('button',{name:'Join the waitlist'}));
  expect(await screen.findByRole('status',{name:'Waitlist confirmation'})).toHaveTextContent('Check your inbox to confirm.');
 });

 it('loads the player only after click, stops it, and restores keyboard focus',async()=>{
  await renderLanding();
  const user=userEvent.setup();
  await user.click(screen.getByRole('button',{name:'Play demo'}));
  // The dialog is fetched on the click rather than shipped with the hero (Hero.tsx keeps
  // @base-ui's dialog off the LCP critical path), so the player arrives one module load
  // after the press; the button itself is in the DOM from first paint either way.
  expect(await screen.findByTitle('Guidefold product demo')).toHaveAttribute('src','https://www.youtube-nocookie.com/embed/e350wBr1W8c?autoplay=1');
  const dialog=screen.getByRole('dialog');
  expect(within(dialog).getByRole('link',{name:/Watch on YouTube/})).toBeInTheDocument();
  await user.click(screen.getByRole('button',{name:'Stop video'}));
  await waitFor(()=>expect(screen.queryByTitle('Guidefold product demo')).not.toBeInTheDocument());
  await waitFor(()=>expect(screen.getByRole('button',{name:'Play demo'})).toHaveFocus());
 });

 it.each(['confirm','unsubscribe'] as const)('requires an explicit %s action and hides third-party content',async action=>{
  window.history.replaceState(null,'','/?'+action+'=private-token');
  vi.mocked(submitWaitlist).mockResolvedValueOnce();
  render(<Landing/>);
  expect(window.location.search).toBe('');
  expect(submitWaitlist).not.toHaveBeenCalled();
  expect(document.querySelector('img[src^="https:"]')).toBeNull();
  expect(screen.queryByRole('button',{name:'Play demo'})).not.toBeInTheDocument();
  expect(document.querySelector('video')).toBeNull();
  await userEvent.setup().click(screen.getByRole('button',{name:action==='confirm'?'Confirm email':'Unsubscribe'}));
  expect(submitWaitlist).toHaveBeenCalledWith(action,{token:'private-token'},expect.any(AbortSignal));
  expect(await screen.findByRole('status')).toBeInTheDocument();
 });

 it('creates no video element under reduced motion and keeps the film poster',async()=>{
  reduceMotion(true);
  const {container}=await renderLanding();
  expect(container.querySelector('video')).toBeNull();
  expect(container.querySelector('img[src="/assets/landing/hero-poster.webp"]')).toBeInTheDocument();
 });

 it('puts the skip link first and keeps DOM order equal to reading order',async()=>{
  const {container}=await renderLanding();
  const focusable=[...container.querySelectorAll('a[href],button:not([disabled]),input,summary,[tabindex]:not([tabindex="-1"])')];
  expect(focusable[0]).toHaveTextContent('Skip to content');
  expect(container.querySelector('[style*="order"]')).toBeNull();
 });

 it('publishes only the citable figures',async()=>{
  const {container}=await renderLanding();
  const text=container.textContent??'';
  expect(text).toContain('76 of 76 harmful rules refused.');
  expect(text).toContain('4.81%');
  expect(text).toContain('+8.53 pp Recall@10 on SRA-Bench.');
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/16\s*\/\s*20/);
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/\b\d+(\.\d+)?\s?(ms|milliseconds)\b/);
  expect(text.toLowerCase()).not.toContain('zero risk');
 });

 // The mechanism clip (IntroFigure) and the Meridian reader (InstructionReader) are re-homed
 // in the retrieval section; their reduced-motion, poster and "not a live run" coverage now
 // lives in Retrieval.test.tsx, which renders that section directly.
});
