import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {IconTile} from './index';

describe('IconTile',()=>{
 it('is decorative unless it carries the only label',()=>{
  const {container}=render(<IconTile icon={<svg data-testid="glyph"/>}/>);
  const tile=container.querySelector('[data-slot=icon-tile]');
  expect(tile).toHaveAttribute('aria-hidden','true');
  expect(tile).not.toHaveAttribute('role');
  expect(screen.getByTestId('glyph')).toBeInTheDocument();
 });
 it('exposes a name as an image when asked to',()=>{
  render(<IconTile icon={<svg/>} label="Skill library" tone="human" size="lg"/>);
  const tile=screen.getByRole('img',{name:'Skill library'});
  expect(tile).toHaveAttribute('data-tone','human');
  expect(tile).toHaveAttribute('data-size','lg');
  expect(tile).not.toHaveAttribute('aria-hidden');
 });
});
