import {describe,it,expect} from 'vitest';
import {render,screen,within} from '@testing-library/react';
import {Telemetry} from './Telemetry';

describe('telemetry chapter',()=>{
 it('renders the copy.md block verbatim',()=>{
  render(<Telemetry/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('You see which rule failed, and why.');
  expect(screen.getByText('Per team: task success, ASK reasons, the SEARCH to USE funnel, tokens, tool calls, time.')).toBeVisible();
  expect(screen.getByText('Missing data reads Unknown, never zero.')).toBeVisible();
 });

 it('shows Unknown in the instrument itself, never a zero or a dash',()=>{
  const {container}=render(<Telemetry/>);
  const missing=container.querySelectorAll('[data-value="unknown"]');
  expect(missing.length).toBeGreaterThan(0);
  for(const cell of missing)expect(cell.textContent).toBe('Unknown');
 });

 it('labels the instrument as a Meridian fixture',()=>{
  const {container}=render(<Telemetry/>);
  expect(container.textContent).toMatch(/Meridian fixture/);
 });

 it('draws every ASK reason from the safe vocabulary',()=>{
  const {container}=render(<Telemetry/>);
  const allowed=['Conflicting rules','Missing dependencies','Revision changed'];
  const reasons=[...container.querySelectorAll('[data-ask-reason]')].map(n=>n.textContent);
  expect(reasons.length).toBeGreaterThan(0);
  for(const reason of reasons)expect(allowed).toContain(reason);
 });
});
