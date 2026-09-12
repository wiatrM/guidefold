import { describe, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LoginRoute } from './LoginRoute';
import { DEFAULT_RETURN, loginHref, safeReturn } from './loginTarget';
import { ApiError } from '../api/client';
import { fakeSource } from '../test/fakes';

const withProviders = (providers: { id: 'github' | 'google'; label: string; login_url: string }[]) =>
  fakeSource({ getAuthProviders: async () => ({ mode: 'workos' as const, providers }) });

const github = { id: 'github' as const, label: 'GitHub', login_url: '/api/v1/auth/login/github' };

function renderLogin(source = withProviders([github]), returnTo = '/import') {
  return render(<MemoryRouter><LoginRoute source={source} returnTo={returnTo} /></MemoryRouter>);
}

describe('the return target is a path, never a second origin', () => {
  test('an in-app address is kept exactly as requested', () => {
    expect(safeReturn('/import?step=preview&org=meridian')).toBe('/import?step=preview&org=meridian');
  });

  test.each([
    ['//evil.example', 'a protocol-relative address'],
    ['https://evil.example/import', 'an absolute URL'],
    ['/\\evil.example', 'a backslash variant'],
    ['import', 'a relative path'],
    ['/import\nHost: evil', 'an address carrying a control character'],
    [null, 'no target at all'],
  ])('%s falls back to Import (%s)', raw => {
    expect(safeReturn(raw)).toBe(DEFAULT_RETURN);
  });

  test('the login address carries the target, and leaves the default implicit', () => {
    expect(loginHref('/usage?window=30d')).toBe('/login?return=' + encodeURIComponent('/usage?window=30d'));
    expect(loginHref('/import')).toBe('/login');
  });
});

describe('login page, full width, outside the shell', () => {
  test('the page names itself and never echoes the address it was reached from', async () => {
    const target = '/skill?org=meridian&skill=' + encodeURIComponent('urn:skill:meridian:atlas:postgres-auth');
    renderLogin(withProviders([github]), target);
    expect(await screen.findByRole('button', { name: /Continue with GitHub/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByText('Guidefold')).toBeInTheDocument();
    // An address can carry an organization, a repository and a skill URN; this screen is reached
    // without a session, so it keeps the target and prints none of it.
    expect(document.body.textContent).not.toMatch(/urn:skill:|meridian/);
    // No shell: the login page reads nothing for an organisation the caller is not in yet.
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
  });

  test('the provider list comes from the API and the redirect carries the return target', async () => {
    const startLogin = vi.fn(async () => ({ provider: 'github', loginUrl: '' }));
    renderLogin(fakeSource({ getAuthProviders: async () => ({ mode: 'workos' as const, providers: [github] }), startLogin }), '/map?axis=scopes');
    await userEvent.click(await screen.findByRole('button', { name: /Continue with GitHub/ }));
    expect(startLogin).toHaveBeenCalledWith('github', '/map?axis=scopes');
  });

  test('a failed start says nothing was sent and nobody is signed in', async () => {
    const source = fakeSource({
      getAuthProviders: async () => ({ mode: 'workos' as const, providers: [github] }),
      startLogin: async () => { throw new ApiError({ status: 503, code: 'provider_unavailable', message: 'down' }); },
    });
    renderLogin(source);
    await userEvent.click(await screen.findByRole('button', { name: /Continue with GitHub/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign-in could not start (provider_unavailable)');
  });

  test('an API with no provider says so instead of offering a way in', async () => {
    renderLogin(withProviders([]));
    expect(await screen.findByText('No identity provider is configured')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continue with/ })).not.toBeInTheDocument();
  });

  test('a provider list that cannot be read is an error state with a retry, not an empty page', async () => {
    const source = fakeSource({ getAuthProviders: async () => { throw new ApiError({ status: 500, code: 'internal', message: 'boom' }); } });
    renderLogin(source);
    expect(await screen.findByText('Could not read this view')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry the provider list' })).toBeInTheDocument();
  });
});
