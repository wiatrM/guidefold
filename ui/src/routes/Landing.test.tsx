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

/** The eight screens under the hero are their own chunk (index.tsx defers BelowHero so
 * the hero, which holds the LCP element, is not behind `motion` and @base-ui), so they
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

 it('opens on the outcome and orders the nine v3 sections',async()=>{
  const {container}=await renderLanding();
  expect(screen.getAllByRole('heading',{level:1})).toHaveLength(1);
  expect(screen.getByRole('heading',{level:1,name:"Your coding agent doesn't know your team's rules. Now it does."})).toBeInTheDocument();
  const ids=[...container.querySelectorAll('main section[id]')].map(n=>n.id);
  expect(ids).toEqual(['hero','why','extraction','portal','how-it-works','under-the-hood','proof','waitlist','questions']);
  expect(container.querySelector('a[href="#extraction"]')).toBeInTheDocument();
 });

 it('gives the hero one sentence, two actions and one real screen, and nothing else',async()=>{
  const {container}=await renderLanding();
  const hero=container.querySelector('section#hero')!;
  expect(hero.textContent).toContain('Your agents stop guessing your conventions.');
  expect(hero.textContent).toContain('Open source today. The hosted service is planned.');
  expect(within(hero as HTMLElement).getByRole('img')).toHaveAttribute('src','/assets/landing/app/proposals.webp');
  expect(within(hero as HTMLElement).getByText('The organisation portal, sample data')).toBeVisible();
  // The proof rail, the tier glyph and the scroll-cue sentence are gone; the only hero
  // figures a reader meets are in the proof band near the end.
  expect(hero.textContent).not.toContain('harmful');
  expect(hero.textContent).not.toContain('How rules move up');
  expect(hero.querySelector('svg[role="presentation"]')).toBeNull();
 });

 /**
  * The owner's instruction for v3: every block answers what the reader gets, in one shape.
  * Six blocks carry one, and the label is inside the sentence rather than a badge above it.
  */
 it('ends every block on one value panel in the same shape',async()=>{
  const {container}=await renderLanding();
  const lines=[...container.querySelectorAll('main p')]
   .map(n=>n.textContent??'').filter(text=>text.startsWith('What you get: '));
  expect(lines).toHaveLength(6);
  for(const line of lines)expect(line).toMatch(/^What you get: \S.*\.$/);
 });

 it('says what SEARCH, USE and ASK are in plain words',async()=>{
  const {container}=await renderLanding();
  const hood=container.querySelector('section#under-the-hood')!;
  for(const verb of ['SEARCH','USE','ASK'])expect(hood.textContent).toContain(verb);
  expect(hood.textContent).toContain('Guidefold is a separate service with a database of every rule in your organisation.');
  expect(within(hood as HTMLElement).getByText('The rule database with your hierarchy, sample data')).toBeVisible();
 });

 it('names why each role installs it, once each',async()=>{
  const {container}=await renderLanding();
  const why=container.querySelector('section#why')!;
  for(const role of ['Platform teams','Tech leads and rule owners','Developers'])
   expect(within(why as HTMLElement).getByText(role)).toBeVisible();
  expect(why.querySelectorAll('dt')).toHaveLength(3);
 });

 it('publishes both proof figures from the evidence mirror, readable without JavaScript',async()=>{
  const {container}=await renderLanding();
  const proof=container.querySelector('section#proof')!;
  const m=evidence.proof_gate.matrix;
  const d=evidence.vs_flat.recall10.delta_pp;
  expect(proof.textContent).toContain(`${m.harmful_mutations} of ${m.harmful_asked} poisoned rules refused.`);
  expect(proof.textContent).toContain(`${(d>0?'+':'')+d.toFixed(2)} pp recall over flat search.`);
  expect(proof.textContent).toContain('Sample repository, September 2026.');
  expect(proof.textContent).toContain('SRA-Bench, September 2026.');
 });

 it('gives the scroll cue one destination and an accessible name that says it',async()=>{
  await renderLanding();
  const cue=screen.getByRole('link',{name:'Scroll to the extraction section'});
  expect(cue).toHaveAttribute('href','#extraction');
 });

 it('keeps every protected destination and the availability statements',async()=>{
  const {container}=await renderLanding();
  const href=(selector:string)=>container.querySelector(selector);
  expect(href('a[href="#extraction"]')).toBeInTheDocument();      // nav and the hero cue
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

 /** v3 removed the poster still: the film layer opens on the graphite field it paints
   * itself, so under reduced motion there is nothing to decode and nothing to load. */
 it('creates no video and loads no film still under reduced motion',async()=>{
  reduceMotion(true);
  const {container}=await renderLanding();
  expect(container.querySelector('video')).toBeNull();
  expect(container.querySelector('img[src*="hero-poster"]')).toBeNull();
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
  expect(text).toContain('76 of 76 poisoned rules refused.');
  expect(text).toContain('+8.53 pp recall over flat search.');
  // The research vocabulary the owner struck out: no Wilson bound, no delivery-boundary
  // qualifier, no `reason=`, no millisecond claim anywhere on the page.
  expect(text).not.toContain('Wilson');
  expect(text).not.toContain('reason=');
  expect(text).not.toContain('Delivery boundary');
  expect(text).not.toContain('Measured, exploratory');
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/16\s*\/\s*20/);
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/\b\d+(\.\d+)?\s?(ms|milliseconds)\b/);
  expect(text.toLowerCase()).not.toContain('zero risk');
 });

 /** Owner instruction, 2026-09-12: nobody outside the project knows "Meridian". The only
   * survivor is the protected instruction-reader label, which the preservation contract
   * keeps byte-identical. */
 it('names example content "sample data" everywhere but the protected reader label',async()=>{
  const {container}=await renderLanding();
  const mentions=(container.textContent??'').match(/Meridian|fixture/g)??[];
  expect(mentions).toEqual(['Meridian']);
  expect(container.textContent).toContain('from the Meridian example repository in this project. Not a live run.');
 });

 // The mechanism clip (IntroFigure) and the Meridian reader (InstructionReader) are re-homed
 // in the retrieval section; their reduced-motion, poster and "not a live run" coverage now
 // lives in Retrieval.test.tsx, which renders that section directly.
});
