import {render,screen} from '@testing-library/react';
import {describe,it,expect} from 'vitest';
import {Field} from './index';

describe('Field',()=>{
 it('associates the visible label, hint and error with the actual control',()=>{
  render(<><p id="policy">Owner decision policy.</p><Field id="reason" label="Reason for this decision" hint="Explain the change." error="A reason is required."><textarea id="old-id" aria-describedby="policy"/></Field></>);
  const control=screen.getByRole('textbox',{name:'Reason for this decision'});
  expect(control).toHaveAttribute('id','reason');
  expect(control).toHaveAttribute('aria-describedby','policy reason-hint reason-error');
  expect(control).toHaveAccessibleDescription('Owner decision policy. Explain the change. A reason is required.');
  expect(control).toHaveAttribute('aria-invalid','true');
  expect(screen.getByRole('alert')).toHaveTextContent('A reason is required.');
 });
 it('clears stale error associations when validation succeeds and preserves the hint',()=>{
  const {rerender}=render(<Field id="reason" label="Reason" hint="Explain the change." error="Required"><input/></Field>);
  rerender(<Field id="reason" label="Reason" hint="Explain the change."><input/></Field>);
  const control=screen.getByRole('textbox',{name:'Reason'});
  expect(control).toHaveAttribute('aria-describedby','reason-hint');
  expect(control).not.toHaveAttribute('aria-invalid');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
 });
 it('preserves caller validation and disabled state when no field-level error is supplied',()=>{
  render(<Field id="scope" label="Scope"><input aria-invalid disabled/></Field>);
  const control=screen.getByRole('textbox',{name:'Scope'});
  expect(control).toHaveAttribute('aria-invalid','true');
  expect(control).toBeDisabled();
  expect(control).not.toHaveAttribute('aria-describedby');
 });
});
