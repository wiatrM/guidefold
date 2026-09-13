import {render} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {NumberTicker} from './index';

/** The translateY a column is parked at: the digit it shows is -y / 1.1em. */
const columnOffsets=(container:HTMLElement)=>Array.from(container.querySelectorAll<HTMLElement>('[data-digit]')).map(column=>column.style.transform);

describe('NumberTicker',()=>{
 afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals();});
 it('exposes the formatted number to a screen reader',()=>{
  const {container}=render(<NumberTicker value={1284} suffix=" skills"/>);
  expect(container.querySelector('.sr-only')?.textContent).toBe('1284 skills');
 });
 it('builds one rolling column per digit, clipped from screen readers',()=>{
  const {container}=render(<NumberTicker value={42}/>);
  const ticker=container.querySelector('[data-slot=number-ticker]');
  expect(ticker?.querySelector('[aria-hidden]')).toHaveAttribute('aria-hidden','true');
  expect(ticker?.querySelectorAll('[class*=digit]').length).toBe(2);
 });
 it('does not throw under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<NumberTicker value={7} locale/>);
  expect(container.querySelector('.sr-only')?.textContent).toBe('7');
 });
 it('renders final value before intersection',()=>{
  // An observer that never reports: the element is off screen (zero rect in jsdom) and unscrolled.
  vi.stubGlobal('IntersectionObserver',class{observe(){}disconnect(){}unobserve(){}});
  const {container}=render(<NumberTicker value={10}/>);
  const ticker=container.querySelector('[data-slot=number-ticker]');
  expect(ticker).not.toHaveAttribute('data-rolling');
  // Columns sit on 1 and 0, never on 0 and 0: "10", not "00".
  expect(Array.from(container.querySelectorAll('[data-digit]')).map(column=>column.getAttribute('data-digit'))).toEqual(['1','0']);
  const [tens,ones]=columnOffsets(container as HTMLElement);
  expect(tens).toContain('-1.1em');
  expect(ones).not.toContain('-1.1em');
 });
 it('renders final value where IntersectionObserver does not exist',()=>{
  vi.stubGlobal('IntersectionObserver',undefined);
  const {container}=render(<NumberTicker value={30}/>);
  expect(container.querySelector('[data-slot=number-ticker]')).not.toHaveAttribute('data-rolling');
  expect(columnOffsets(container as HTMLElement)[0]).toContain('-3.3');
 });
});
