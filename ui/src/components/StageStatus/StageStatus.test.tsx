import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {StageStatus} from './index';

const stages=[{id:'fetch',label:'Fetch'},{id:'parse',label:'Parse'},{id:'propose',label:'Propose'}];

describe('StageStatus',()=>{
 it('renders the wizard-style steps variant with every stage label',()=>{
  render(<StageStatus stages={stages} activeIndex={1}/>);
  expect(screen.getByText('Fetch')).toBeVisible();
  expect(screen.getByText('Parse')).toBeVisible();
  expect(screen.getByText('Propose')).toBeVisible();
 });
 it('renders the inline variant naming only the active stage, with a status role for the detail', ()=>{
  render(<StageStatus stages={stages} activeIndex={1} variant="inline" detail="Parsing 3 of 5 files"/>);
  expect(screen.getByText('Parse')).toBeVisible();
  expect(screen.queryByText('Fetch')).not.toBeInTheDocument();
 });
 it('names the completed step for assistive technology without inventing a percentage detail',()=>{
  render(<StageStatus stages={stages} activeIndex={3}/>);
  expect(screen.getAllByText(/Fetch|Parse|Propose/)).toHaveLength(3);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
 });
});
