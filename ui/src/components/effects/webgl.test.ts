import {describe,it,expect} from 'vitest';
import {supportsWebGL,readTokenColor} from './webgl';

describe('webgl helpers',()=>{
 it('reports no WebGL in jsdom without throwing',()=>{
  expect(supportsWebGL()).toBe(false);
 });
 it('falls back to the given colour when a token is unset',()=>{
  expect(readTokenColor('--does-not-exist','#0c1014')).toBe('#0c1014');
 });
});
