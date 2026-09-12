import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {ResearchEvidence} from './ResearchEvidence';
import evidence from '../../data/research-evidence.json';

describe('evidence section',()=>{
 it('leads on the recall figure with its qualifier on the same screen',()=>{
  render(<ResearchEvidence/>);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent('Plus 8.53 points of recall over flat.');
  expect(screen.getByText('5,400 queries across 26,262 skills on SRA-Bench, against flat dense search.')).toBeVisible();
  expect(screen.getByText(/Four of six datasets improved; CHAMP and TheoremQA regressed\./)).toBeVisible();
 });

 // Final review I1: the headline figure was typed into the h2 while the table two lines
 // below read the mirror. The expectation is formatted from the JSON with the table's own
 // formatter, so it fails if the two ever drift apart.
 it('derives the headline figure from the same row and formatter as the table',()=>{
  render(<ResearchEvidence/>);
  const expected=evidence.vs_flat.recall10.delta_pp.toFixed(2);
  expect(screen.getByRole('heading',{level:2})).toHaveTextContent(`Plus ${expected} points of recall over flat.`);
 });

 it('keeps the open question and the scale envelope, neither carrying a figure',()=>{
  render(<ResearchEvidence/>);
  const open=screen.getByText(/Task-level value is not settled\./);
  expect(open).toBeVisible();
  expect(open.textContent).not.toMatch(/\d+\s*\/\s*\d+/);
  expect(screen.getByText(/Designed for, not yet measured\./)).toBeVisible();
 });

 it('renders every figure from the data file, not from markup',()=>{
  const {container}=render(<ResearchEvidence/>);
  expect(container.textContent).toContain(evidence.rates.full_pyramid.recall10.toFixed(2));
  expect(container.textContent).toContain(evidence.rates.flat.recall10.toFixed(2));
 });

 it('keeps both existing calls to action',()=>{
  render(<ResearchEvidence/>);
  expect(screen.getByRole('link',{name:'Read the evidence'})).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Download results and source hashes'})).toBeInTheDocument();
 });

 it('renders the chart once, in the bento tile, not a second time below',()=>{
  render(<ResearchEvidence/>);
  expect(screen.getAllByText('Relevant skills retrieved and complete sets found (%)')).toHaveLength(1);
  expect(document.querySelectorAll('figcaption')).toHaveLength(0);
 });
});
