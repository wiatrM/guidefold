import {describe,it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';

const source=readFileSync(join(process.cwd(),'src/tokens/tokens.css'),'utf8');
const OPEN='@media(prefers-reduced-motion:reduce){:root{';
const start=source.indexOf(OPEN);
const end=source.indexOf('}}',start);

/**
 * A media query adds no specificity, so `prefers-reduced-motion` only wins by source order.
 * The landing block and the 1080/720 breakpoint blocks redeclare `--duration-entrance`,
 * `--enter-rise`, `--parallax-panel`, `--landing-stage-height` and the rest; while any of
 * them was declared after the reduced-motion block the reduced value was silently lost and
 * the page animated for a reader who asked it not to. Assert the shape, not the values.
 */
describe('reduced-motion tokens',()=>{
 const declared=[...source.slice(start,end).matchAll(/(--[a-z0-9-]+):/g)].map(match=>match[1]);

 it('declares the reduced-motion overrides',()=>{
  expect(start).toBeGreaterThan(-1);
  expect(declared).toContain('--duration-entrance');
  expect(declared).toContain('--parallax-panel');
  expect(declared).toContain('--landing-stage-height');
 });

 it('declares every override last, so source order carries it',()=>{
  for(const name of declared){
   const last=source.lastIndexOf(name+':');
   expect({[name]:last>start&&last<end}).toEqual({[name]:true});
  }
 });
});
