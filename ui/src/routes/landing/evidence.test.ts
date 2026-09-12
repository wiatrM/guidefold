import {describe,it,expect} from 'vitest';
import evidence from '../../data/research-evidence.json';

describe('citable evidence contract',()=>{
 it('mirrors the proof-gate matrix with its source, date and label',()=>{
  const gate=evidence.proof_gate;
  expect(gate.date).toBe('2026-09-11');
  expect(gate.label).toBe('delivery boundary, not task success');
  expect(gate.microcopy).toBe('Delivery boundary, deterministic, source-backed; not a task-success claim. 2026-09-11.');
  expect(gate.matrix.harmful_mutations).toBe(76);
  expect(gate.matrix.harmful_loaded).toBe(0);
  expect(gate.matrix.flat_control_loaded).toBe(76);
  expect(gate.matrix.wilson_upper_bound_pct).toBe(4.81);
  expect(gate.matrix.source).toContain('docs/RESEARCH.md');
  expect(gate.http_path.loaded).toBe(4);
  expect(gate.http_path.reason).toBe('source_proof_complete');
 });

 it('keeps the retrieval figure and its denominators intact',()=>{
  expect(evidence.vs_flat.recall10.delta_pp).toBeCloseTo(8.527,3);
  expect(evidence.queries).toBe(5400);
  expect(evidence.skills).toBe(26262);
  expect(evidence.date).toBe('2026-09-10');
 });
});
