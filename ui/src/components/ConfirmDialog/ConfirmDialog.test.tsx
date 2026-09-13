import {render,screen} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import {ConfirmDialog} from './index';

// The dialog itself is a Base UI portal that hangs jsdom once opened
// (docs/ui/pipeline/08-components.md lines 45-48); this covers the closed state only.
// Opening, focus trap and Escape are exercised in the Playwright gallery spec.
describe('ConfirmDialog',()=>{
 it('renders only the trigger before it is opened',()=>{
  render(<ConfirmDialog triggerLabel="Disconnect GitHub" title="Disconnect GitHub?" description="Existing imports keep their history." onConfirm={vi.fn()} destructive/>);
  expect(screen.getByRole('button',{name:'Disconnect GitHub'})).toBeVisible();
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(screen.queryByText('Existing imports keep their history.')).not.toBeInTheDocument();
 });
 it('disables the trigger when asked',()=>{
  render(<ConfirmDialog triggerLabel="Delete key" title="Delete this key?" description="Anything using it stops working." onConfirm={vi.fn()} disabled destructive/>);
  expect(screen.getByRole('button',{name:'Delete key'})).toBeDisabled();
 });
});
