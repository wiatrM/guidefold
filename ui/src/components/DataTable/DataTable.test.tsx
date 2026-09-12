import {render,screen,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect} from 'vitest';
import {DataTable} from './index';

describe('DataTable',()=>{
 it('does not invent a revision or a loading state when the route supplies no rows',()=>{
  render(<DataTable caption="No available source revisions" headings={['Skill','Revision']}>{null}</DataTable>);
  const table=screen.getByRole('table',{name:'No available source revisions'});
  expect(within(table).getAllByRole('row')).toHaveLength(1);
  expect(within(table).queryByRole('cell')).not.toBeInTheDocument();
  expect(screen.queryByText('Loading')).not.toBeInTheDocument();
 });
 it('preserves caption, column headers and a row header supplied by the route',()=>{
  render(<DataTable caption="Source revisions" headings={['Skill','Scope']}><tr><th scope="row">postgres-auth</th><td>meridian.platform</td></tr></DataTable>);
  const table=screen.getByRole('table',{name:'Source revisions'});
  expect(within(table).getAllByRole('columnheader').map(h=>h.textContent)).toEqual(['Skill','Scope']);
  expect(within(table).getAllByRole('columnheader').every(h=>h.getAttribute('scope')==='col')).toBe(true);
  expect(within(table).getByRole('rowheader',{name:'postgres-auth'})).toHaveAttribute('scope','row');
  expect(within(table).getByRole('cell',{name:'meridian.platform'})).toBeInTheDocument();
 });
 it('allows keyboard focus on its named scroll region before reaching row actions',async()=>{
  const user=userEvent.setup();
  render(<DataTable caption="Source revisions" headings={['Skill']}><tr><td><a href="/skill">Inspect source</a></td></tr></DataTable>);
  await user.tab();
  expect(screen.getByRole('region',{name:'Source revisions'})).toHaveFocus();
  await user.tab();
  expect(screen.getByRole('link',{name:'Inspect source'})).toHaveFocus();
 });

 it('keeps the caption as the region name when flush hides it visually',()=>{
  render(<DataTable flush caption="Members of this organization" headings={['Member']}><tr><td>owner@example.test</td></tr></DataTable>);
  expect(screen.getByRole('region',{name:'Members of this organization'})).toBeInTheDocument();
  expect(screen.getByText('Members of this organization')).toHaveClass('sr-only');
 });
});
