import {render,waitFor} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {ShaderField} from './index';

describe('ShaderField',()=>{
 it('is purely decorative',()=>{
  const {container}=render(<ShaderField/>);
  expect(container.querySelector('[data-slot=shader-field]')).toHaveAttribute('aria-hidden','true');
 });
 it('falls back to a static gradient where WebGL is unavailable (jsdom has no WebGL context)',async()=>{
  const {container}=render(<ShaderField/>);
  await waitFor(()=>expect(container.querySelector('[class*=fallback]')).toBeInTheDocument());
 });
});
