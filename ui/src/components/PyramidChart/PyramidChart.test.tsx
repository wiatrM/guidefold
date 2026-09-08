import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, it, expect, vi} from 'vitest';
import {PyramidChart} from './index';

const bands = [
  {key: 'abstract' as const, label: 'Abstract', description: 'Concepts and domain knowledge', items: [{id: 'data-migration', label: 'Data Migration'}]},
  {key: 'task' as const, label: 'Task', description: 'Reusable capabilities and workflows', items: [{id: 'object-type-migrations', label: 'object-type-migrations', detail: 'forge.ontology'}]},
  {key: 'atomic' as const, label: 'Atomic', description: 'Concrete, executable elements', items: []},
];
const edges = [{from: 'object-type-migrations', to: 'data-migration'}, {from: 'object-type-migrations', to: 'unknown-node'}];

describe('PyramidChart', () => {
  it('renders every band label and its declared skills as buttons, in band order', () => {
    render(<PyramidChart bands={bands} edges={edges} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.map(button => button.textContent)).toEqual(['Data Migration', 'object-type-migrations']);
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
    const selected = screen.getByRole('button', {name: 'object-type-migrations'});
    expect(selected).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', {name: 'Data Migration'})).not.toHaveAttribute('aria-current');
    await userEvent.click(screen.getByRole('button', {name: 'Data Migration'}));
    expect(onSelect).toHaveBeenCalledWith('data-migration');
  });

  it('draws a connector only for edges whose both ends are on the chart, and hides the connector layer from the accessibility tree', () => {
    const {container} = render(<PyramidChart bands={bands} edges={edges} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    // The 'unknown-node' edge target is not a node on this chart and must not produce a dangling line.
    expect(container.querySelectorAll('line')).toHaveLength(1);
  });
});
