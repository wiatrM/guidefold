import {render,screen,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {ActionButton} from './index';

function Location(){return <output aria-label="Location">{useLocation().pathname}</output>;}
describe('ActionButton',()=>{
 it('defaults to a native non-submit button and supports keyboard activation',async()=>{
  const onClick=vi.fn(),onSubmit=vi.fn(e=>e.preventDefault());
  render(<form onSubmit={onSubmit}><ActionButton onClick={onClick}>Inspect source</ActionButton></form>);
  const user=userEvent.setup();
  await user.tab();
  expect(screen.getByRole('button',{name:'Inspect source'})).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(onClick).toHaveBeenCalledOnce();
  expect(onSubmit).not.toHaveBeenCalled();
 });
 it('preserves explicit submit behavior',async()=>{
  const submit=vi.fn(e=>e.preventDefault());
  render(<form onSubmit={submit}><ActionButton type="submit">Save local draft</ActionButton></form>);
  await userEvent.click(screen.getByRole('button',{name:'Save local draft'}));
  expect(submit).toHaveBeenCalledOnce();
 });
 it('does not invoke disabled native actions',async()=>{
  const action=vi.fn();
  render(<ActionButton disabled onClick={action}>Export SKILL.md</ActionButton>);
  await userEvent.click(screen.getByRole('button',{name:'Export SKILL.md'}));
  expect(action).not.toHaveBeenCalled();
  expect(screen.getByRole('button')).toBeDisabled();
 });
 it('navigates internal links through the router',async()=>{
  render(<MemoryRouter initialEntries={['/import']}><ActionButton href="/library">Open Library</ActionButton><Location/></MemoryRouter>);
  await userEvent.click(screen.getByRole('link',{name:'Open Library'}));
  expect(screen.getByLabelText('Location')).toHaveTextContent('/library');
 });
 it('blocks disabled link navigation, callbacks and keyboard focus',async()=>{
  const action=vi.fn();
  render(<MemoryRouter initialEntries={['/import']}><ActionButton href="/library" disabled onClick={action}>Open Library</ActionButton><ActionButton>Next action</ActionButton><Location/></MemoryRouter>);
  const user=userEvent.setup(),link=screen.getByRole('link',{name:'Open Library'});
  expect(link).toHaveAttribute('aria-disabled','true');
  expect(link).toHaveAttribute('tabindex','-1');
  expect(link).not.toHaveAttribute('href');
  await user.click(link);
  expect(action).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Location')).toHaveTextContent('/import');
  link.blur();
  await user.tab();
  expect(screen.getByRole('button',{name:'Next action'})).toHaveFocus();
 });
 it('opens external source links safely and cancels disabled default navigation',()=>{
  const {rerender}=render(<ActionButton href="https://github.com/wiatrM/guidefold">Open source</ActionButton>);
  const link=screen.getByRole('link',{name:'Open source'});
  expect(link).toHaveAttribute('target','_blank');
  expect(link).toHaveAttribute('rel','noopener noreferrer');
  rerender(<ActionButton href="https://github.com/wiatrM/guidefold" disabled>Open source</ActionButton>);
  expect(screen.getByRole('link')).not.toHaveAttribute('href');
  expect(fireEvent.click(screen.getByRole('link'))).toBe(false);
 });
});
