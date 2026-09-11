import {describe,it,expect,afterEach,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Extraction} from './Extraction';

function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false})) as unknown as typeof window.matchMedia;
}
afterEach(()=>vi.restoreAllMocks());

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

 it('rests with the tier route drawn complete',()=>{
  reduceMotion(true);
  const {container}=render(<Extraction/>);
  const route=container.querySelector('[data-tier-route]');
  expect(route).toBeInTheDocument();
  expect(route).toHaveAttribute('stroke-dashoffset','0');
 });

 it('marks exactly one promoted row as the human decision',()=>{
  reduceMotion(false);
  const {container}=render(<Extraction/>);
  expect(container.querySelectorAll('[data-decision="human"]')).toHaveLength(1);
 });
});
