import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import type {Tone} from '../../domain';
import {StateBadge} from './index';

describe('StateBadge',()=>{
 it.each<[Tone,string]>([['neutral','Unknown'],['system','Published'],['human','Approved for export'],['warning','Partial'],['error','Failed']])('preserves a readable label for the %s state',(tone,label)=>{
  render(<StateBadge tone={tone}>{label}</StateBadge>);
  expect(screen.getByText(label)).toBeVisible();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
 });
 it('does not infer a positive outcome from an unknown observation',()=>{
  render(<StateBadge>Unknown</StateBadge>);
  expect(screen.getByText('Unknown')).toBeVisible();
  expect(screen.queryByText('Success')).not.toBeInTheDocument();
 });
});
