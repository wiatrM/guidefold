import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi,afterEach} from 'vitest';
import {AnimatedList} from './index';

const items=[{id:'a',content:'Import finished'},{id:'b',content:'Sync started'}];

describe('AnimatedList',()=>{
 afterEach(()=>vi.restoreAllMocks());
 it('renders every item as a list row',()=>{
  render(<AnimatedList items={items} ariaLabel="Recent events"/>);
  expect(screen.getByRole('list',{name:'Recent events'})).toBeInTheDocument();
  expect(screen.getByText('Import finished')).toBeInTheDocument();
  expect(screen.getByText('Sync started')).toBeInTheDocument();
 });
 it('renders without animation under prefers-reduced-motion',()=>{
  vi.spyOn(window,'matchMedia').mockImplementation((media:string)=>({matches:media.includes('reduce'),media,addEventListener:()=>{},removeEventListener:()=>{}})as never);
  render(<AnimatedList items={items}/>);
  expect(screen.getAllByRole('listitem')).toHaveLength(2);
 });
});
