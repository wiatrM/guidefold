import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe,it,expect,vi} from 'vitest';
import {RepositoryItem} from './index';

describe('RepositoryItem',()=>{
 it('shows the repository name and calls onImport when Import is activated',async()=>{
  const onImport=vi.fn();
  render(<RepositoryItem name="atlas-search" onImport={onImport}/>);
  expect(screen.getByText('atlas-search')).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:'Import'}));
  expect(onImport).toHaveBeenCalledTimes(1);
 });
 it('renders secondary row actions and the passed state slot',()=>{
  const onRename=vi.fn();
  render(<RepositoryItem name="atlas-search" state={<span>Imported</span>} secondaryActions={[{label:'Re-import',onClick:onRename}]}/>);
  expect(screen.getByText('Imported')).toBeVisible();
  expect(screen.getByRole('button',{name:'Re-import'})).toBeEnabled();
 });
 it('disables Import when the row is not ready',()=>{
  render(<RepositoryItem name="atlas-search" onImport={vi.fn()} importDisabled/>);
  expect(screen.getByRole('button',{name:'Import'})).toBeDisabled();
 });
 it('does not wrap the name in an interactive control when there is no preview',()=>{
  render(<RepositoryItem name="atlas-search"/>);
  expect(screen.queryByRole('button',{name:'atlas-search'})).not.toBeInTheDocument();
 });
});
