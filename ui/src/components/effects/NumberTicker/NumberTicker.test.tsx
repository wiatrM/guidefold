import {render} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {NumberTicker} from './index';

describe('NumberTicker',()=>{
 afterEach(()=>vi.restoreAllMocks());
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
});
