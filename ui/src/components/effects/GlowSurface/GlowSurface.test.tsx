import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {GlowSurface} from './index';

describe('GlowSurface',()=>{
 it('renders its content and a decorative glow layer',()=>{
  render(<GlowSurface><p>Panel body</p></GlowSurface>);
  expect(screen.getByText('Panel body')).toBeInTheDocument();
  const surface=document.querySelector('[data-slot=glow-surface]');
  expect(surface?.querySelector('[aria-hidden]')).toBeInTheDocument();
 });
 it('writes pointer position onto the element instead of React state',()=>{
  render(<GlowSurface><p>Body</p></GlowSurface>);
  const surface=document.querySelector('[data-slot=glow-surface]') as HTMLElement;
  Object.defineProperty(surface,'getBoundingClientRect',{value:()=>({left:0,top:0,width:200,height:100})});
  // jsdom has no native PointerEvent, and testing-library's fallback Event() constructor drops
  // clientX/clientY; MouseEvent is the one jsdom-native constructor that keeps them, and React
  // dispatches onPointerMove by the event's type string, not its class.
  surface.dispatchEvent(new MouseEvent('pointermove',{clientX:50,clientY:25,bubbles:true}));
  expect(surface.style.getPropertyValue('--effect-pointer-x')).toBe('25%');
  expect(surface.style.getPropertyValue('--effect-pointer-y')).toBe('25%');
 });
});
