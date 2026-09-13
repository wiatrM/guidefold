import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {OrbitingCircles} from './index';

describe('OrbitingCircles',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('renders the centre and up to six satellites',()=>{
  render(<OrbitingCircles center={<span>Repository</span>} items={[<span key="a">GitHub</span>,<span key="b">CI</span>]}/>);
  expect(screen.getByText('Repository')).toBeInTheDocument();
  expect(screen.getByText('GitHub')).toBeInTheDocument();
  expect(screen.getByText('CI')).toBeInTheDocument();
 });
 it('does not spin under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<OrbitingCircles center={<span>Repository</span>} items={[<span key="a">GitHub</span>]}/>);
  expect(container.querySelector('[class*=orbit]')?.className).not.toMatch(/\bspin\b/);
 });
});
