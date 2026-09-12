import {describe,it,expect,afterEach} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ValuePanel} from './ValuePanel';

const realMatchMedia=window.matchMedia;
function reduceMotion(reduce:boolean){
 window.matchMedia=((media:string)=>({
  matches:reduce&&media.includes('prefers-reduced-motion'),media,onchange:null,
  addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent:()=>false,
 })) as unknown as typeof window.matchMedia;
}
afterEach(()=>{window.matchMedia=realMatchMedia;});

const LINE='What you get: numbers you can check, not promises.';

describe('the value panel',()=>{
 it('renders the label and the sentence as one sentence',()=>{
  const {container}=render(<ValuePanel>{LINE}</ValuePanel>);
  expect(container.textContent).toBe(LINE);
  expect(screen.getByText('What you get:')).toBeVisible();
 });

 /**
  * The entrance layer applies only to a panel carrying `data-value-ready`, which is written
  * in an effect. Under reduced motion `useRevealed` reports entered immediately, so the
  * panel is at its resting state on the first paint rather than waiting for a callback that
  * the reduced-motion path never schedules.
  */
 it('is at its resting state immediately under reduced motion',()=>{
  reduceMotion(true);
  const {container}=render(<ValuePanel>{LINE}</ValuePanel>);
  const panel=container.firstElementChild as HTMLElement;
  expect(panel.dataset.valueEntered).toBe('true');
  expect(container.textContent).toBe(LINE);
 });

 it('carries a decorative rule that no screen reader announces',()=>{
  const {container}=render(<ValuePanel>{LINE}</ValuePanel>);
  expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(1);
 });
});
