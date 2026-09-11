import {describe,it,expect,afterEach} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Retrieval} from './Retrieval';

const realMatchMedia=window.matchMedia;
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({
  matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false,
 })) as unknown as typeof window.matchMedia;
}
afterEach(()=>{window.matchMedia=realMatchMedia;});

describe('retrieval chapter',()=>{
 it('renders the copy.md block verbatim',()=>{
  render(<Retrieval/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Thirty thousand rules. Four reach the agent.');
  expect(screen.getByText('Ranked by the task and by the place in the repository, in real time, every prompt.')).toBeVisible();
  expect(screen.getByText(/Your context window carries four cards instead of a filing cabinet\./)).toBeVisible();
  expect(screen.getByText('Designed for a 30k-skill corpus. Latency at that size is in the Q6 validation plan and is not claimed here.')).toBeVisible();
 });

 it('delivers exactly four cards, general first, each with a proof state',()=>{
  const {container}=render(<Retrieval/>);
  const cards=container.querySelectorAll('[data-delivered-card]');
  expect(cards).toHaveLength(4);
  for(const card of cards)expect((card as HTMLElement).dataset.proof).toBeTruthy();
  expect(cards[0]).toHaveTextContent('security-baseline');
  expect(cards[0]).toHaveTextContent('_root');
  expect(cards[3]).toHaveTextContent('postgres-auth');
  expect(cards[3]).toHaveTextContent('atlas.identity.turnstile');
 });

 it('carries no excluded figure in any form',()=>{
  const {container}=render(<Retrieval/>);
  const text=container.textContent??'';
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/\b\d+\s?ms\b/);
  expect(text).not.toMatch(/422/);
 });

 it('links to the open-source quickstart exactly once and without a glyph in the label',()=>{
  const {container}=render(<Retrieval/>);
  const links=container.querySelectorAll('a[href="https://github.com/wiatrM/guidefold#quickstart"]');
  expect(links).toHaveLength(1);
  expect(links[0].textContent).toBe('Try the open-source version');
 });

 // IntroFigure and InstructionReader belong to this section (carried finding from T5, which
 // left both unmounted). These two restore the coverage Landing.test.tsx dropped when T5
 // reduced the page to a shell: git show 2cf2ba8:ui/src/routes/Landing.test.tsx had
 // 'creates no video element under reduced motion and keeps the posters' (both posters) and
 // 'mounts the mechanism clip only when motion is allowed'.
 it('creates no video element under reduced motion and keeps the intro poster',()=>{
  reduceMotion(true);
  const {container}=render(<Retrieval/>);
  expect(container.querySelector('video')).toBeNull();
  expect(container.querySelector('img[src="/assets/landing/intro-poster.webp"]')).toBeInTheDocument();
 });

 it('mounts the mechanism clip only when motion is allowed',()=>{
  reduceMotion(false);
  const {container}=render(<Retrieval/>);
  const clip=container.querySelector('video');
  expect(clip).toHaveAttribute('poster','/assets/landing/intro-poster.webp');
  expect(clip).not.toHaveAttribute('loop');
  expect(clip).toHaveAttribute('preload','none');
 });

 it('keeps the protected Meridian fixture reader with its "not a live run" label',()=>{
  const {container}=render(<Retrieval/>);
  expect(container.querySelector('code')?.textContent).toBe('postgres-auth');
  expect(container.textContent).toContain('Not a live run.');
 });
});
