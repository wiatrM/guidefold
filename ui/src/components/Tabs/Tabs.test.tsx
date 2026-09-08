import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect} from 'vitest';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {Tabs} from './index';

const items=[{id:'source',label:'Source',href:'/skill?tab=source'},{id:'content',label:'Content',href:'/skill?tab=content'}];
function Subject(){const location=useLocation();return <><Tabs label="Skill sections" items={items} current={new URLSearchParams(location.search).get('tab')||'source'}/><output aria-label="Location">{location.pathname+location.search}</output></>;}
describe('Tabs',()=>{
 it('provides named native link navigation and the current page',()=>{
  render(<MemoryRouter initialEntries={['/skill?tab=source']}><Subject/></MemoryRouter>);
  expect(screen.getByRole('navigation',{name:'Skill sections'})).toBeVisible();
  expect(screen.getByRole('link',{name:'Source'})).toHaveAttribute('aria-current','page');
  expect(screen.getByRole('link',{name:'Content'})).not.toHaveAttribute('aria-current');
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
 });
 it('supports ordinary keyboard navigation and changes the selected route',async()=>{
  render(<MemoryRouter initialEntries={['/skill?tab=source']}><Subject/></MemoryRouter>);
  const user=userEvent.setup();
  await user.tab();await user.tab();
  expect(screen.getByRole('link',{name:'Content'})).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(screen.getByLabelText('Location')).toHaveTextContent('/skill?tab=content');
  expect(screen.getByRole('link',{name:'Content'})).toHaveAttribute('aria-current','page');
  expect(screen.getByRole('link',{name:'Source'})).not.toHaveAttribute('aria-current');
 });
});
