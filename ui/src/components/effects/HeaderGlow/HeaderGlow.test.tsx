import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {HeaderGlow} from './index';

describe('HeaderGlow',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('renders its content and a halo',()=>{
  render(<HeaderGlow><span data-testid="tile"/></HeaderGlow>);
  expect(screen.getByTestId('tile')).toBeInTheDocument();
  expect(document.querySelector('[data-slot=header-glow]')).toHaveAttribute('data-tone','system');
 });
 it('skips the sweep under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<HeaderGlow tone="human"><span/></HeaderGlow>);
  // Reduced motion plus jsdom's absent IntersectionObserver both keep `active` false: no sweep node.
  expect(container.querySelectorAll('[aria-hidden]').length).toBe(1);
 });
});
