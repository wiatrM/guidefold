import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {SuccessBurst} from './index';

describe('SuccessBurst',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('shows the label as a status when show is true',()=>{
  render(<SuccessBurst show label="Import finished"/>);
  expect(screen.getByRole('status')).toHaveTextContent('Import finished');
 });
 it('renders nothing when show is false',()=>{
  render(<SuccessBurst show={false} label="Import finished"/>);
  expect(screen.getByRole('status')).toHaveTextContent('');
 });
 it('appears without a scale animation under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  render(<SuccessBurst show label="Run finished"/>);
  expect(screen.getByRole('status')).toHaveTextContent('Run finished');
 });
});
