import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {ModelKeysTable} from './index';

const keys=[{id:'k1',provider:'OpenAI',lastFour:'a1b2',preferred:true},{id:'k2',provider:'Anthropic',lastFour:'9f3d'}];

describe('ModelKeysTable',()=>{
 it('never shows the full secret, only provider, masked key and preferred state',()=>{
  render(<ModelKeysTable keys={keys}/>);
  expect(screen.getByText('OpenAI')).toBeVisible();
  expect(screen.getByText(/a1b2$/)).toBeVisible();
  expect(screen.getAllByText('Preferred')).toHaveLength(2); // column header + the one preferred key's badge
 });
 it('calls onDelete with the row id',async()=>{
  const onDelete=vi.fn();
  render(<ModelKeysTable keys={keys} onDelete={onDelete}/>);
  const rows=screen.getAllByRole('button',{name:'Delete'});
  await userEvent.click(rows[1]);
  expect(onDelete).toHaveBeenCalledWith('k2');
 });
 it('offers to make a non-preferred key preferred, but not the one that already is',()=>{
  render(<ModelKeysTable keys={keys} onSetPreferred={vi.fn()}/>);
  expect(screen.getAllByRole('button',{name:'Make preferred'})).toHaveLength(1);
 });
 it('names the empty state instead of rendering nothing',()=>{
  render(<ModelKeysTable keys={[]}/>);
  expect(screen.getByText('No model keys yet.')).toBeVisible();
 });
});
