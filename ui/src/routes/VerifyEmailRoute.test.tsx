import { describe, expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { VerifyEmailRoute } from './VerifyEmailRoute';
import { ApiError } from '../api/client';
import { fakeSource } from '../test/fakes';

function renderPage(source = fakeSource(), email = 'k•••@example.test') {
  return render(<MemoryRouter><VerifyEmailRoute source={source} email={email} /></MemoryRouter>);
}

describe('the email-verification code screen', () => {
  test('shows the masked email it was given, never asking for the real one', async () => {
    renderPage(fakeSource(), 'k•••@example.test');
    expect(await screen.findByRole('heading', { level: 1, name: 'Check your email' })).toBeInTheDocument();
    expect(screen.getByText(/k•••@example\.test/)).toBeInTheDocument();
    expect(screen.getByLabelText('Code from your email')).toBeInTheDocument();
    // No resend button: WorkOS does not expose one for this flow.
    expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument();
  });

  test('a wrong code is refused and the form stays usable for another try', async () => {
    let calls = 0;
    const source = fakeSource({
      verifyEmailCode: async () => {
        calls += 1;
        throw new ApiError({ status: 400, code: 'email_code_invalid', message: 'wrong code' });
      },
    });
    renderPage(source);
    await userEvent.type(screen.getByLabelText('Code from your email'), '000000');
    await userEvent.click(screen.getByRole('button', { name: /Verify and continue/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/wasn.t accepted/);
    // The form is still there — a wrong code does not end the round trip.
    expect(screen.getByLabelText('Code from your email')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify and continue/ })).toBeInTheDocument();
    expect(calls).toBe(1);
  });

  test.each([
    ['invalid_state', /no longer matches this browser/],
    ['expired_state', /expired/],
    ['email_code_attempts_exceeded', /Too many attempts/],
  ] as const)('%s ends the round trip: no form, a way back to sign in', async (code, expected) => {
    const source = fakeSource({
      verifyEmailCode: async () => { throw new ApiError({ status: 400, code, message: 'terminal' }); },
    });
    renderPage(source);
    await userEvent.type(screen.getByLabelText('Code from your email'), '000000');
    await userEvent.click(screen.getByRole('button', { name: /Verify and continue/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(expected);
    expect(screen.queryByLabelText('Code from your email')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toBeInTheDocument();
  });

  test('the correct code is sent, and nothing but the code leaves this screen', async () => {
    const seen: string[] = [];
    const source = fakeSource({
      verifyEmailCode: async (code: string) => { seen.push(code); return { returnTo: '/organization' }; },
    });
    renderPage(source);
    await userEvent.type(screen.getByLabelText('Code from your email'), '123456');
    await userEvent.click(screen.getByRole('button', { name: /Verify and continue/ }));
    expect(seen).toEqual(['123456']);
  });
});
