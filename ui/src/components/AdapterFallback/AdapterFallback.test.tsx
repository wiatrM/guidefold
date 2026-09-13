import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect} from 'vitest';
import {AdapterFallback} from './index';

describe('AdapterFallback',()=>{
 it('starts collapsed, naming both fallback paths without showing either body',()=>{
  render(<AdapterFallback commands={['guidefold login','guidefold link org']}/>);
  expect(screen.getByRole('button',{name:'Use the CLI'})).toBeVisible();
  expect(screen.getByRole('button',{name:'Upload a file'})).toBeVisible();
  expect(screen.queryByText('terminal')).not.toBeInTheDocument();
  expect(screen.queryByText(/Drag a file here/)).not.toBeInTheDocument();
 });
 it('shows the adapter commands once the CLI section is expanded',async()=>{
  render(<AdapterFallback commands={['guidefold login']}/>);
  await userEvent.click(screen.getByRole('button',{name:'Use the CLI'}));
  expect(await screen.findByText('terminal')).toBeVisible();
 });
 it('shows the drop target once the file section is expanded',async()=>{
  render(<AdapterFallback commands={['guidefold login']}/>);
  await userEvent.click(screen.getByRole('button',{name:'Upload a file'}));
  expect(await screen.findByText(/Drag a file here/)).toBeVisible();
 });
});
