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
 it('renders the v3 copy verbatim',()=>{
  render(<Retrieval/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Thirty thousand rules. Four reach the agent.');
  expect(screen.getByText('At the start of a task, Guidefold walks your hierarchy and hands the agent the four rules that fit that folder and that job.')).toBeVisible();
  expect(screen.getByText(/every task starts with the right conventions already in the agent's context/)).toBeVisible();
 });

 /**
  * The owner's complaint about the previous instrument was that you could not see what was
  * asked or what happened. Both halves are asserted here rather than left to a screenshot.
  */
 it('shows what the developer typed and where',()=>{
  render(<Retrieval/>);
  expect(screen.getByText('What the developer typed')).toBeVisible();
  expect(screen.getByText('rotate the service token')).toBeVisible();
  expect(screen.getByText('in platforms/atlas/identity/turnstile/')).toBeVisible();
 });

 it('traces what the service did in four named steps, in order',()=>{
  const {container}=render(<Retrieval/>);
  expect(screen.getByText('What Guidefold did')).toBeVisible();
  const steps=[...container.querySelectorAll('ol li')].map(node=>node.textContent??'');
  expect(steps).toHaveLength(4);
  expect(steps[0]).toContain('Found the scope');
  expect(steps[0]).toContain('scope: atlas.identity.turnstile');
  expect(steps[1]).toContain('Searched the rules in reach');
  expect(steps[1]).toContain('SEARCH · 27 candidates · 4 selected');
  expect(steps[2]).toContain('Checked the proof');
  expect(steps[2]).toContain('USE · source hash and revision verified · LOAD');
  expect(steps[3]).toContain('Handed the agent four cards');
 });

 it('delivers exactly four cards, general first, each with a level and a proof state',()=>{
  const {container}=render(<Retrieval/>);
  const cards=container.querySelectorAll('[data-delivered-card]');
  expect(cards).toHaveLength(4);
  for(const card of cards){
   expect((card as HTMLElement).dataset.proof).toBeTruthy();
   expect(card).toHaveTextContent('Proof complete');
  }
  expect(cards[0]).toHaveTextContent('Organisation');
  expect(cards[0]).toHaveTextContent('security-baseline');
  expect(cards[3]).toHaveTextContent('Service');
  expect(cards[3]).toHaveTextContent('postgres-auth');
 });

 it('carries no excluded figure and no research vocabulary',()=>{
  const {container}=render(<Retrieval/>);
  const text=container.textContent??'';
  expect(text).not.toMatch(/25\s*\/\s*25/);
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(text).not.toMatch(/\b\d+\s?ms\b/);
  expect(text).not.toContain('Q6');
  expect(text).not.toContain('Wilson');
 });

 /** The mechanism clip was removed with IntroFigure; nothing in this chapter decodes video. */
 it('creates no video element at any motion setting',()=>{
  reduceMotion(true);
  expect(render(<Retrieval/>).container.querySelector('video')).toBeNull();
  reduceMotion(false);
  expect(render(<Retrieval/>).container.querySelector('video')).toBeNull();
 });

 it('folds the protected reader into a closed details with its "not a live run" label',()=>{
  const {container}=render(<Retrieval/>);
  const details=container.querySelector('details');
  expect(details).toBeInTheDocument();
  expect(details).not.toHaveAttribute('open');
  expect(screen.getByText('Read the full rule the agent loaded')).toBeVisible();
  expect(container.querySelector('code')?.textContent).toBe('postgres-auth');
  expect(container.textContent).toContain('Not a live run.');
 });

 it('captions its two visuals in plain words and names the sample data',()=>{
  const {container}=render(<Retrieval/>);
  expect(screen.getByText('Sample data, the example repository in this project.')).toBeVisible();
  expect(screen.getByText('Afterwards, the portal shows which rule helped, sample data')).toBeVisible();
  for(const image of container.querySelectorAll('img'))expect(image.getAttribute('alt')).toBeTruthy();
 });
});
