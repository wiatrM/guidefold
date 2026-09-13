import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {Marquee} from './index';

describe('Marquee',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('duplicates the track for a seamless loop, the copy hidden from screen readers',()=>{
  render(<Marquee ariaLabel="Connected repositories">{[<span key="a">alpha</span>]}</Marquee>);
  expect(screen.getByRole('group',{name:'Connected repositories'})).toBeInTheDocument();
  const copies=screen.getAllByText('alpha');
  expect(copies).toHaveLength(2);
  expect(copies[1].closest('[aria-hidden]')).toHaveAttribute('aria-hidden','true');
 });
 it('does not duplicate the track under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  render(<Marquee>{[<span key="a">alpha</span>]}</Marquee>);
  expect(screen.getAllByText('alpha')).toHaveLength(1);
 });
});
