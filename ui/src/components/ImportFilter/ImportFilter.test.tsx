import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {ImportFilter} from './index';

describe('ImportFilter',()=>{
 it('marks the current value as pressed and names the group',()=>{
  render(<ImportFilter value="not_imported" onChange={vi.fn()}/>);
  expect(screen.getByRole('group',{name:'Filter repositories'})).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Not imported'})).toHaveAttribute('aria-pressed','true');
  expect(screen.getByRole('button',{name:'All'})).toHaveAttribute('aria-pressed','false');
 });
 it('reports the newly chosen value without holding local state',async()=>{
  const onChange=vi.fn();
  render(<ImportFilter value="all" onChange={onChange}/>);
  await userEvent.click(screen.getByRole('button',{name:'Imported'}));
  expect(onChange).toHaveBeenCalledWith('imported');
 });
 it('shows a count next to a value when one is supplied',()=>{
  render(<ImportFilter value="all" onChange={vi.fn()} counts={{all:12,imported:5}}/>);
  expect(screen.getByRole('button',{name:'All 12'})).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Imported 5'})).toBeInTheDocument();
 });
});
