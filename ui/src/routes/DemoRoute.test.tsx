import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { DemoRoute } from './DemoRoute';

describe('demo route', () => {
  it('labels sample data and offers a path to the real import', () => {
    render(<MemoryRouter><DemoRoute /></MemoryRouter>);
    expect(screen.getByText(/fictional checkout/i)).toBeInTheDocument();
    expect(screen.getByText(/customer data read/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /use your own repository/i })).toHaveAttribute('href', '/import?step=login');
  });
});
