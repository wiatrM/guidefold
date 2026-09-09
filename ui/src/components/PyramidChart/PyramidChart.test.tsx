import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, it, expect, vi} from 'vitest';
import {PyramidChart} from './index';

// Browser tests cover the real layout engine; this suite covers Graph/List composition.
vi.mock('./SchemaFlow', () => ({SchemaFlow: () => <div role="region" aria-label="Skill hierarchy"/>}));

const bands = [
  {key: 'abstract' as const, label: 'Abstract', description: 'Concepts and domain knowledge', items: [{id: 'data-migration', label: 'Data Migration'}]},
  {key: 'task' as const, label: 'Task', description: 'Reusable capabilities and workflows', items: [{id: 'object-type-migrations', label: 'object-type-migrations', detail: 'forge.ontology'}]},
  {key: 'atomic' as const, label: 'Atomic', description: 'Concrete, executable elements', items: []},
];
const edges = [{from: 'object-type-migrations', to: 'data-migration'}, {from: 'object-type-migrations', to: 'unknown-node'}];

describe('PyramidChart', () => {
  it('renders every band label and its declared skills in list mode', async () => {
    render(<PyramidChart bands={bands} edges={edges} />);
    await userEvent.click(screen.getByRole('button', {name:'List'}));
    const buttons = screen.getAllByRole('button');
    expect(buttons.map(button => button.textContent)).toEqual(['Graph', 'List', 'Data Migration', 'object-type-migrations']);
    expect(screen.getByText('Abstract')).toBeInTheDocument();
    expect(screen.getByText('Concepts and domain knowledge')).toBeInTheDocument();
  });

  it('shows an explicit empty state for a band with no classified skill, never an empty row', () => {
    render(<PyramidChart bands={bands} edges={edges} />);
    expect(screen.getByText('No skill classified at this layer yet.')).toBeInTheDocument();
  });

  it('marks the selected node with aria-current and calls onSelect with its id', async () => {
    const onSelect = vi.fn();
    render(<PyramidChart bands={bands} edges={edges} selectedId="object-type-migrations" onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', {name:'List'}));
    const selected = screen.getByRole('button', {name: 'object-type-migrations'});
    expect(selected).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', {name: 'Data Migration'})).not.toHaveAttribute('aria-current');
    await userEvent.click(screen.getByRole('button', {name: 'Data Migration'}));
    expect(onSelect).toHaveBeenCalledWith('data-migration');
  });

  it('starts in graph mode and can return to it after reading the list', async () => {
    render(<PyramidChart bands={bands} edges={edges} />);
    expect(await screen.findByRole('region', {name:'Skill hierarchy'})).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', {name:'List'}));
    expect(screen.queryByRole('region', {name:'Skill hierarchy'})).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', {name:'Graph'}));
    expect(await screen.findByRole('region', {name:'Skill hierarchy'})).toBeInTheDocument();
  });
});
