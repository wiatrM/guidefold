import {render, screen, fireEvent} from '@testing-library/react';
import {describe, it, expect, vi} from 'vitest';
import {RepositoryFilter} from './index';

const repos = [
  {repo_id: 'monorepo', name: 'Monorepo', git_host_url: null, created_at: null, created: false},
  {repo_id: 'platform', name: 'Platform', git_host_url: null, created_at: null, created: false},
];

describe('RepositoryFilter', () => {
  it('offers the whole organisation first and every readable repository by id', () => {
    render(<RepositoryFilter repos={repos} value={null} onChange={() => {}} />);
    const select = screen.getByRole('combobox', {name: 'Repository'});
    expect(select).toHaveValue('');
    expect(screen.getAllByRole('option').map(option => option.textContent)).toEqual(['All repositories', 'monorepo', 'platform']);
  });
  it('reports a repository as its id and the whole organisation as null', () => {
    const onChange = vi.fn();
    render(<RepositoryFilter repos={repos} value={null} onChange={onChange} />);
    fireEvent.change(screen.getByRole('combobox', {name: 'Repository'}), {target: {value: 'platform'}});
    expect(onChange).toHaveBeenLastCalledWith('platform');
    fireEvent.change(screen.getByRole('combobox', {name: 'Repository'}), {target: {value: ''}});
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
  it('keeps a repository from the address selectable when the list does not name it, and says when the list is missing', () => {
    render(<RepositoryFilter repos={null} value="archive" onChange={() => {}} />);
    expect(screen.getByRole('combobox', {name: 'Repository'})).toHaveValue('archive');
    expect(screen.getByRole('option', {name: 'archive'})).toBeInTheDocument();
    expect(screen.getByText('Repository list not available yet.')).toBeInTheDocument();
  });
});
