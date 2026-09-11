import {describe,it,expect} from 'vitest';
import {FILM_ANCHORS,playheadAt} from './FilmBackdrop';

describe('film anchor map',()=>{
 it('names the nine sections in DOM order with their playhead seconds',()=>{
  expect(FILM_ANCHORS.map(a=>a.id)).toEqual(['hero','extraction','how-it-works','proof-gate','telemetry','research-results','availability','waitlist','questions']);
  // Shipped anchors, not DESIGN.md's targets: `how-it-works` and `proof-gate` sit on the
  // film's measured cuts so each section opens on its own shot (DESIGN.md 3.0, "Implemented
  // anchors"). Controller ruling, 2026-09-11: the film's cuts are the truth.
  expect(FILM_ANCHORS.map(a=>a.second)).toEqual([0,1.4,4.3,5.75,6.8,7.8,8.6,9.1,9.7]);
 });

 it('interpolates piecewise linearly between measured anchors',()=>{
  const anchors=[{id:'a',second:0,at:0},{id:'b',second:4,at:0.5},{id:'c',second:10,at:1}];
  expect(playheadAt(0,anchors)).toBeCloseTo(0,4);
  expect(playheadAt(0.25,anchors)).toBeCloseTo(2,4);
  expect(playheadAt(0.5,anchors)).toBeCloseTo(4,4);
  expect(playheadAt(0.75,anchors)).toBeCloseTo(7,4);
  expect(playheadAt(1,anchors)).toBeCloseTo(10,4);
 });

 it('clamps outside the measured range and never exceeds the film duration',()=>{
  const anchors=[{id:'a',second:0,at:0.1},{id:'b',second:10,at:0.9}];
  expect(playheadAt(-1,anchors)).toBe(0);
  expect(playheadAt(2,anchors)).toBe(10);
 });

 it('is monotonic and exact in reverse',()=>{
  const anchors=FILM_ANCHORS.map((a,i)=>({...a,at:i/(FILM_ANCHORS.length-1)}));
  const forward=[...Array(21).keys()].map(i=>playheadAt(i/20,anchors));
  const backward=[...Array(21).keys()].map(i=>playheadAt((20-i)/20,anchors)).reverse();
  expect(backward).toEqual(forward);
  for(let i=1;i<forward.length;i++)expect(forward[i]).toBeGreaterThanOrEqual(forward[i-1]);
 });
});
