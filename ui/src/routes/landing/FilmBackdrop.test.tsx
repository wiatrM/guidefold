import {describe,it,expect} from 'vitest';
import {FILM_ANCHORS,normaliseAnchors,playheadAt} from './FilmBackdrop';

describe('film anchor map',()=>{
 it('names the nine sections in DOM order with their playhead seconds',()=>{
  expect(FILM_ANCHORS.map(a=>a.id)).toEqual(['hero','extraction','how-it-works','proof-gate','telemetry','research-results','availability','waitlist','questions']);
  // Shipped anchors, not DESIGN.md's targets: `how-it-works` and `proof-gate` sit on the
  // film's measured cuts so each section opens on its own shot (DESIGN.md 3.0, "Implemented
  // anchors"). Controller ruling, 2026-09-11: the film's cuts are the truth.
  expect(FILM_ANCHORS.map(a=>a.second)).toEqual([0,1.4,4.4,5.85,6.8,7.8,8.6,9.1,9.7]);
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

 // `playheadAt` scans forward once per frame rather than sorting, so the ascending,
 // offset-unique shape it needs is produced by `normaliseAnchors` on every measure.
 // Nothing in the DOM guarantees that shape, so it is tested rather than assumed.
 it('sorts measured anchors ascending whatever order they arrive in',()=>{
  const scrambled=[{id:'c',second:10,at:0.9},{id:'a',second:0,at:0.1},{id:'b',second:4,at:0.5}];
  const anchors=normaliseAnchors(scrambled);
  expect(anchors.map(a=>a.id)).toEqual(['a','b','c']);
  expect(playheadAt(0.3,anchors)).toBeCloseTo(2,4);
  expect(playheadAt(0.7,anchors)).toBeCloseTo(7,4);
 });

 it('keeps the later beat when two sections share an offset',()=>{
  const anchors=normaliseAnchors([{id:'a',second:0,at:0},{id:'b',second:4,at:0.5},{id:'c',second:6,at:0.5},{id:'d',second:10,at:1}]);
  expect(anchors.map(a=>a.id)).toEqual(['a','c','d']);
  expect(anchors.map(a=>a.at)).toEqual([0,0.5,1]);
  expect(playheadAt(0.5,anchors)).toBeCloseTo(6,4);
  expect(playheadAt(0.25,anchors)).toBeCloseTo(3,4);
  expect(playheadAt(0.75,anchors)).toBeCloseTo(8,4);
 });

 // The `span<=0` guard in playheadAt is defensive: the forward scan cannot actually reach it
 // once the table is normalised. What is worth asserting is that an un-normalised table with a
 // duplicate offset still yields a finite second rather than a NaN reaching `currentTime`.
 it('returns a finite second if an equal offset reaches it unnormalised',()=>{
  const anchors=[{id:'a',second:0,at:0},{id:'b',second:4,at:0.5},{id:'c',second:6,at:0.5},{id:'d',second:10,at:1}];
  expect(Number.isFinite(playheadAt(0.5,anchors))).toBe(true);
  expect(playheadAt(0.5,anchors)).toBeCloseTo(4,4);
 });

 it('holds the end anchors before the first and after the last',()=>{
  const anchors=normaliseAnchors([{id:'b',second:4,at:0.8},{id:'a',second:1,at:0.2}]);
  expect(playheadAt(0,anchors)).toBe(1);
  expect(playheadAt(0.19,anchors)).toBe(1);
  expect(playheadAt(0.2,anchors)).toBe(1);
  expect(playheadAt(0.8,anchors)).toBe(4);
  expect(playheadAt(0.81,anchors)).toBe(4);
  expect(playheadAt(1,anchors)).toBe(4);
 });

 it('returns 0 for an empty table and survives a single anchor',()=>{
  expect(playheadAt(0.5,[])).toBe(0);
  expect(normaliseAnchors([])).toEqual([]);
  const one=normaliseAnchors([{id:'only',second:3,at:0.4}]);
  expect(playheadAt(0,one)).toBe(3);
  expect(playheadAt(1,one)).toBe(3);
 });
});
