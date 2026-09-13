import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {GlowAction} from './index';

describe('GlowAction',()=>{
 it('wraps its action and exposes a decorative halo',()=>{
  render(<GlowAction><button>Import repository</button></GlowAction>);
  expect(screen.getByRole('button',{name:'Import repository'})).toBeInTheDocument();
  const wrap=document.querySelector('[data-slot=glow-action]');
  expect(wrap?.querySelector('[aria-hidden]')).toBeInTheDocument();
 });
 it('applies the system tone class for a system action',()=>{
  render(<GlowAction tone="system"><button>Open Library</button></GlowAction>);
  const wrap=document.querySelector('[data-slot=glow-action]');
  expect(wrap?.className).toMatch(/system/);
 });
});
