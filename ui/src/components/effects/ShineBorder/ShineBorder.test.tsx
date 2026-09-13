import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {ShineBorder} from './index';

describe('ShineBorder',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('renders its content',()=>{
  render(<ShineBorder><p>Card body</p></ShineBorder>);
  expect(screen.getByText('Card body')).toBeInTheDocument();
 });
 it('replays the sweep when trigger changes',()=>{
  const view=render(<ShineBorder trigger={1}><p>Body</p></ShineBorder>);
  const first=view.container.querySelector('[data-slot=shine-border] span+span');
  expect(first).toBeInTheDocument();
  view.rerender(<ShineBorder trigger={2}><p>Body</p></ShineBorder>);
  const second=view.container.querySelector('[data-slot=shine-border] span+span');
  expect(second).toBeInTheDocument();
  expect(second).not.toBe(first);
 });
 it('keeps only the static edge under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<ShineBorder><p>Body</p></ShineBorder>);
  expect(container.querySelectorAll('[aria-hidden]').length).toBe(1);
 });
});
