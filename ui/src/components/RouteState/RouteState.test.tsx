import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {RouteState} from './index';

describe('RouteState',()=>{
 it('announces loading politely without exposing skeleton decoration',()=>{
  render(<RouteState state="loading" title="Loading view" description="Waiting for the requested snapshot."/>);
  const section=screen.getByRole('heading',{name:'Loading view'}).closest('section')!;
  expect(section).toHaveAttribute('aria-live','polite');
  expect(section).toHaveAttribute('aria-busy','true');
  expect(section.querySelector('[aria-hidden="true"]')).not.toBeNull();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
 });
 it('clears busy state and exposes a retry action after an error',async()=>{
  const retry=vi.fn();
  const {rerender}=render(<RouteState state="loading" title="Loading view" description="Waiting for the requested snapshot."/>);
  rerender(<RouteState state="error" title="Could not load this view" description="No operation or publication is confirmed." action={<button onClick={retry}>Retry view</button>}/>);
  const section=screen.getByRole('heading',{name:'Could not load this view'}).closest('section')!;
  expect(section).toHaveAttribute('aria-busy','false');
  expect(screen.getByText('No operation or publication is confirmed.')).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:'Retry view'}));
  expect(retry).toHaveBeenCalledOnce();
 });
 it('describes restricted access without inventing a count or an action',()=>{
  render(<RouteState state="restricted" title="Organization access unavailable" description="This scenario does not expose organization content."/>);
  expect(screen.getByText('This scenario does not expose organization content.')).toBeVisible();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });
});
