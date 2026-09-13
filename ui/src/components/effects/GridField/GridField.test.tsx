import {render} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {GridField} from './index';

describe('GridField',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('is purely decorative',()=>{
  const {container}=render(<GridField/>);
  expect(container.querySelector('[data-slot=grid-field]')).toHaveAttribute('aria-hidden','true');
 });
 it('does not drift under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<GridField/>);
  expect(container.querySelector('[data-slot=grid-field]')?.className).not.toMatch(/drift/);
 });
});
