import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {BorderBeam} from './index';

describe('BorderBeam',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('renders its content inside the ring',()=>{
  render(<BorderBeam><p>Panel body</p></BorderBeam>);
  expect(screen.getByText('Panel body')).toBeInTheDocument();
 });
 it('freezes the ring under prefers-reduced-motion instead of removing it',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  const {container}=render(<BorderBeam><p>Body</p></BorderBeam>);
  const spinner=container.querySelector('span > span');
  expect(spinner).not.toHaveAttribute('data-spin');
 });
});
