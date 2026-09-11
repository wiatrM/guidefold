import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ProofGate} from './ProofGate';

const LABEL='Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.';

describe('proof gate',()=>{
 it('leads on the comparison and names the flat control',()=>{
  render(<ProofGate/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Seventy-six harmful rules. Seventy-six refusals.');
  expect(screen.getByText('The flat control loaded all 76. Guidefold answered ASK every single time.')).toBeVisible();
 });

 it('renders both proof lines with the unshortened label under each',()=>{
  render(<ProofGate/>);
  expect(screen.getByText(/One-sided Wilson 95% upper bound for harmful delivery: 4\.81%\./)).toBeVisible();
  expect(screen.getByText(/came through the production USE 1\.2 HTTP handler/)).toBeVisible();
  expect(screen.getAllByText(LABEL)).toHaveLength(2);
 });

 it('never rounds the count or claims zero risk',()=>{
  const {container}=render(<ProofGate/>);
  const text=(container.textContent??'').toLowerCase();
  expect(text).not.toContain('zero risk');
  expect(text).not.toContain('100% safe');
  expect(text).not.toContain('no unsafe deliveries');
  expect(text).not.toMatch(/17\s*\/\s*20/);
  expect(container.textContent).toContain('76');
 });
});
