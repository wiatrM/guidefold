import {render} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {AnimatedText} from './index';

describe('AnimatedText',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('exposes the plain string to a screen reader',()=>{
  const {container}=render(<AnimatedText text="Import repository skills"/>);
  expect(container.querySelector('.sr-only')?.textContent).toBe('Import repository skills');
 });
 it('splits the aria-hidden copy into one span per word',()=>{
  const {container}=render(<AnimatedText text="One two three"/>);
  const words=container.querySelector('[aria-hidden]');
  expect(words?.children).toHaveLength(3);
 });
 it('does not throw under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<AnimatedText text="Steady state"/>);
  expect(container.querySelector('.sr-only')?.textContent).toBe('Steady state');
 });
});
