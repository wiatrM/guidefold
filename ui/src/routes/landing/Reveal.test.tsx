import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Reveal,RevealGroup,RevealLines} from './Reveal';

const observers:{cb:IntersectionObserverCallback;opts?:IntersectionObserverInit}[]=[];
function stubObserver(){
 observers.length=0;
 (globalThis as unknown as {IntersectionObserver:unknown}).IntersectionObserver=class{
  constructor(cb:IntersectionObserverCallback,opts?:IntersectionObserverInit){observers.push({cb,opts});}
  observe(){}unobserve(){}disconnect(){}
 };
}
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false})) as unknown as typeof window.matchMedia;
}
afterEach(()=>{vi.restoreAllMocks();});

describe('Reveal',()=>{
 it('renders its children visible before any observer callback fires',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p1"><p>Seventy-six refusals.</p></Reveal>);
  expect(screen.getByText('Seventy-six refusals.')).toBeVisible();
 });

 it('marks itself entered only once and never re-enters on a second intersection',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<Reveal pattern="p1"><p>once</p></Reveal>);
  const node=container.firstElementChild as HTMLElement;
  const entry={isIntersecting:true,target:node} as unknown as IntersectionObserverEntry;
  observers[0].cb([entry],{} as IntersectionObserver);
  expect(node.dataset.revealEntered).toBe('true');
  observers[0].cb([{...entry,isIntersecting:false} as IntersectionObserverEntry],{} as IntersectionObserver);
  expect(node.dataset.revealEntered).toBe('true');
 });

 it('observes at 22% from the bottom for p1 and p2',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p1"><p>x</p></Reveal>);
  expect(observers[0].opts?.rootMargin).toBe('0px 0px -22% 0px');
 });

 it('observes p3 panels at 30% visibility',()=>{
  stubObserver();reduceMotion(false);
  render(<Reveal pattern="p3"><p>panel</p></Reveal>);
  expect(observers[0].opts?.threshold).toBe(0.3);
 });

 it('installs no observer and sets no ready flag under reduced motion',()=>{
  stubObserver();reduceMotion(true);
  const {container}=render(<Reveal pattern="p1"><p>static</p></Reveal>);
  expect(observers).toHaveLength(0);
  expect((container.firstElementChild as HTMLElement).dataset.revealReady).toBeUndefined();
  expect(screen.getByText('static')).toBeVisible();
 });

 it('caps the stagger slot at five items',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<RevealGroup pattern="p1">
   {['a','b','c','d','e','f','g'].map(k=><p key={k}>{k}</p>)}
  </RevealGroup>);
  const slots=[...container.querySelectorAll('[data-reveal-slot]')].map(n=>(n as HTMLElement).dataset.revealSlot);
  expect(slots).toEqual(['0','1','2','3','4','4','4']);
 });

 it('renders every child of a group even when the observer never fires',()=>{
  stubObserver();reduceMotion(false);
  render(<RevealGroup pattern="p3">{['one','two'].map(k=><p key={k}>{k}</p>)}</RevealGroup>);
  expect(screen.getByText('one')).toBeVisible();
  expect(screen.getByText('two')).toBeVisible();
 });
});

describe('RevealLines',()=>{
 it('masks each line separately but keeps one accessible name',()=>{
  stubObserver();reduceMotion(false);
  const {container}=render(<RevealLines as="h1" id="hero-title"
   lines={['Your repos are already','writing the handbook.']}/>);
  const heading=screen.getByRole('heading',{level:1});
  expect(heading).toHaveAccessibleName('Your repos are already writing the handbook.');
  expect(container.querySelectorAll('[data-reveal-line]')).toHaveLength(2);
  expect([...container.querySelectorAll('[data-reveal-slot]')].map(n=>(n as HTMLElement).dataset.revealSlot)).toEqual(['0','1']);
 });

 it('renders the whole headline visible before any observer callback',()=>{
  stubObserver();reduceMotion(false);
  render(<RevealLines as="h1" lines={['One line.']}/>);
  expect(screen.getByRole('heading',{level:1})).toBeVisible();
 });

 it('installs no observer and masks nothing under reduced motion',()=>{
  stubObserver();reduceMotion(true);
  const {container}=render(<RevealLines as="h1" lines={['a','b']}/>);
  expect(observers).toHaveLength(0);
  for(const line of container.querySelectorAll('[data-reveal-line]'))
   expect((line as HTMLElement).dataset.revealReady).toBeUndefined();
 });
});
