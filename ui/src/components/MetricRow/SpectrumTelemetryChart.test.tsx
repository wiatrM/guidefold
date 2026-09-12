import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {SpectrumTelemetryChart, SpectrumTelemetryStackedBar} from './SpectrumTelemetryChart';

describe('Spectrum telemetry charts', () => {
  it('keeps exact counts as accessible text beside Spectrum chart marks', () => {
    render(<SpectrumTelemetryChart ariaLabel="Loads by skill" points={[{id: 'a', label: 'deploy', value: 8, detail: '8 verified'}]} />);
    expect(screen.getByRole('group', {name: 'Loads by skill'})).toHaveTextContent('8 verified');
    expect(screen.getByRole('group').querySelector('[data-spectrum-chart="registry-frame"]')).toBeInTheDocument();
  });

  it('shows an honest empty state instead of a zero chart', () => {
    render(<SpectrumTelemetryChart ariaLabel="Loads" points={[{id: 'a', label: 'deploy', value: 0, detail: '0 verified'}]} />);
    expect(screen.getByText('No measured data in this window.')).toBeInTheDocument();
    expect(screen.queryByRole('group', {name: 'Loads'})).not.toBeInTheDocument();
  });

  it('renders non-zero verdict slices and lists every verdict', () => {
    render(<SpectrumTelemetryStackedBar ariaLabel="Feedback verdicts" totalLabel="3 assessments recorded." segments={[
      {id: 'helped', label: 'Helped', value: 3, color: 'var(--survey-teal)'},
      {id: 'hindered', label: 'Hindered', value: 0, color: 'var(--warning)'},
    ]} />);
    expect(screen.getByRole('group', {name: 'Feedback verdicts'}).querySelector('[data-spectrum-chart="registry-frame"]')).toBeInTheDocument();
    expect(screen.getByText('Hindered')).toBeInTheDocument();
  });
});
