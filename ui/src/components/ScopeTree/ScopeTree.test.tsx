import {render,screen,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter} from 'react-router-dom';
import {describe,it,expect} from 'vitest';
import {ScopeTree} from './index';
import type {TreeNode} from '../../domain';

const nodes:TreeNode[]=[{id:'root',label:'Repository',children:[
 {id:'platform',label:'Platform',children:[{id:'auth',label:'postgres-auth',href:'/skill?skill=auth',detail:'meridian.platform'}]},
 {id:'delivery',label:'Delivery',children:[{id:'deploy',label:'Deployment',href:'/skill?skill=deploy'}]}
]}];
describe('ScopeTree',()=>{
 it('opens the selected ancestor path and names the selected leaf',()=>{
  render(<MemoryRouter><ScopeTree label="Repository scopes" selected="auth" nodes={nodes}/></MemoryRouter>);
  const group=screen.getByRole('group',{name:'Repository scopes'});
  expect(within(group).getByRole('link',{name:'postgres-auth'})).toHaveAttribute('aria-current','true');
  expect(screen.getByRole('button',{name:/Repository/})).toHaveAttribute('aria-expanded','true');
  expect(screen.getByRole('button',{name:/Platform/})).toHaveAttribute('aria-expanded','true');
  expect(screen.getByRole('button',{name:/Delivery/})).toHaveAttribute('aria-expanded','false');
  expect(screen.getByText('meridian.platform')).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'postgres-auth'})).toHaveAttribute('href','/skill?skill=auth');
 });
 it('keeps the Base UI collapsible reversible without assigning a false tree widget role',async()=>{
  const user=userEvent.setup();
  const {container}=render(<MemoryRouter><ScopeTree label="Repository scopes" nodes={nodes}/></MemoryRouter>);
  const trigger=screen.getByRole('button',{name:/Repository/});
  expect(trigger).toHaveAttribute('aria-expanded','true');
  await user.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded','false');
  await user.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded','true');
  expect(container.querySelector('[role=tree]')).toBeNull();
 });

 it('reopens a manually collapsed ancestor when selection changes within it',async()=>{
  const user=userEvent.setup();
  const siblings:TreeNode[]=[{id:'root',label:'Repository',children:[{id:'platform',label:'Platform',children:[
   {id:'a',label:'Source A',href:'/a'},{id:'b',label:'Source B',href:'/b'}
  ]}]}];
  const {rerender}=render(<MemoryRouter><ScopeTree label="Sources" selected="a" nodes={siblings}/></MemoryRouter>);
  const trigger=screen.getByRole('button',{name:/Platform/});
  await user.click(trigger);expect(trigger).toHaveAttribute('aria-expanded','false');
  rerender(<MemoryRouter><ScopeTree label="Sources" selected="b" nodes={siblings}/></MemoryRouter>);
  expect(trigger).toHaveAttribute('aria-expanded','true');
  expect(screen.getByRole('link',{name:'Source B'})).toHaveAttribute('aria-current','true');
  await user.click(trigger);expect(trigger).toHaveAttribute('aria-expanded','false');
 });
 it('renders an unavailable leaf as text without inventing navigation',()=>{
  render(<MemoryRouter><ScopeTree label="Unmapped scope" nodes={[{id:'unmapped',label:'Unmapped',detail:'No declared node'}]}/></MemoryRouter>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('No declared node')).toBeInTheDocument();
 });
});
