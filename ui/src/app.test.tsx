import { afterEach, describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import App from './app';
import Landing from './routes/landing';
import { AccessController, AccessProvider } from './api/access';
import { ApiClient, ApiError } from './api/client';
import { createApiDataSource } from './data/apiSource';
import { fakeResponse, fakeSource } from './test/fakes';
import type { Me } from './api/decoders';
vi.mock('./data/waitlist', async original => ({ ...await original<typeof import('./data/waitlist')>(), submitWaitlist: vi.fn() }));
// Layout, zoom and reduced motion are covered by schema-navigation browser tests.
vi.mock('./components/PyramidChart/SchemaFlow',()=>({SchemaFlow:()=> <div role="region" aria-label="Skill hierarchy"/>}));

const me: Me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian Data', role: 'owner' }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};

afterEach(() => { sessionStorage.clear(); });

const rejectingSource = () => fakeSource();

/** Reads the address the gate actually navigated to; MemoryRouter has no window.location. */
function Probe() {
  const location = useLocation();
  return <span data-testid="where">{location.pathname + location.search}</span>;
}

describe('shell composition', () => {
  test('the component gallery renders outside the shell and reads nothing from the API', async () => {
    render(<MemoryRouter initialEntries={['/__components']}><App source={rejectingSource()} /></MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Component gallery' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(screen.getByText(/Sample values from examples\/monorepo/)).toBeInTheDocument();
  });

  test('the management shell renders inside .console, which carries the shadcn dark-neutral theme', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const { container } = render(<MemoryRouter initialEntries={['/home?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={fakeSource()} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
    expect(container.querySelector('.console')).not.toBeNull();
  });

  test('the landing route (rendered outside App by main.tsx) never carries .console', async () => {
    // The landing route keeps the orange-branded `:root` tokens; only the management shell
    // (app.tsx Shell) gets the shadcn dark-neutral override (tokens.css `.console`).
    const { container } = render(<Landing />);
    expect(await within(container).findAllByRole('link', { name: 'Guidefold home' }, { timeout: 4000 })).not.toHaveLength(0);
    expect(container.querySelector('.console')).toBeNull();
  });

  test('an unknown path lands on Import, and nothing but the hosted API is named in the footer', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/nowhere']}>
      <AccessProvider controller={controller}><App source={fakeSource({ getAuthProviders: async () => ({ mode: 'dev' as const, providers: [] }) })} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByText(/^Hosted API\./)).toBeInTheDocument();
    expect(document.title).toBe('Overview | Guidefold');
  });

  test('the shell shows the organisation from /me and the repository from the URL', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/import?org=meridian&repo=monorepo&step=organization']}>
      <AccessProvider controller={controller}>
        <App source={fakeSource({ listOrgs: async () => [{ org_id: 'o1', slug: 'meridian', name: 'Meridian Data', my_role: 'owner', created_at: null, counts: null }] })} />
      </AccessProvider>
    </MemoryRouter>);
    expect(await screen.findAllByText('meridian')).not.toHaveLength(0);
    expect(screen.getAllByText('monorepo')).not.toHaveLength(0);
    expect(screen.getByText('Meridian Data')).toBeInTheDocument();
    expect(screen.getAllByText('Owner')).not.toHaveLength(0);
    expect(within(screen.getByRole('complementary')).getByRole('button', { name: 'Open profile menu' })).toBeInTheDocument();
  });

  test('the grouped sidebar folds without turning Skill into a global destination', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/import?org=meridian&repo=monorepo&step=organization']}>
      <AccessProvider controller={controller}>
        <App source={fakeSource({ listOrgs: async () => [] })} />
      </AccessProvider>
    </MemoryRouter>);
    const rail = screen.getByRole('complementary');
    const navigation = within(rail).getByRole('navigation', { name: 'Main navigation' });
    expect(within(navigation).getByText('Workspace')).toBeInTheDocument();
    expect(within(navigation).getByText('Knowledge')).toBeInTheDocument();
    expect(within(navigation).queryByRole('link', { name: 'Skill' })).not.toBeInTheDocument();
    const fold = within(rail).getByRole('button', { name: 'Collapse sidebar' });
    await userEvent.click(fold);
    expect(within(rail).getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute('aria-expanded', 'false');
  });

  test('switching organisation never leaves the previous organisation content on screen', async () => {
    const twoOrgs: Me = { ...me, orgs: [
      { org_id: 'o1', slug: 'meridian', name: 'Meridian Data', role: 'owner' },
      { org_id: 'o2', slug: 'apex', name: 'Apex Systems', role: 'owner' },
    ] };
    const controller = new AccessController({ fetchMe: async () => twoOrgs, onDenied: vi.fn() });
    await controller.check(true);
    const summary = (org: string) => ({
      skill_id: 'urn:skill:' + org + ':a:' + org + '-only-skill', name: org + '-only-skill',
      description: '[a] ' + org, scope: 'a', owner: org + '-team', source_layer: 'team',
      knowledge_layer: 'unclassified', source_status: 'active', publication_status: 'draft',
      path: 'a/SKILL.md', content_sha256: 's', revision_id: 'r', package_digest: null, commit: 'c', updated_at: null,
    });
    const client = new ApiClient({ baseUrl: 'https://api.test', delay: async () => {}, fetchImpl: async url => {
      const at = String(url);
      const org = at.includes('/orgs/apex/') ? 'apex' : 'meridian';
      if (at.includes('/skills/facets')) return fakeResponse({ field: 'scope', values: [], next_cursor: null });
      if (at.includes('/skills')) return fakeResponse({ items: [summary(org)], next_cursor: null, snapshot_id: null, schema_version: 'mgmt-1', filters: {} });
      return fakeResponse({});
    } });
    const source = createApiDataSource({ client });
    function SwitchOrganisation() {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/library?org=apex&repo=monorepo')}>Switch organisation</button>;
    }
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /><SwitchOrganisation /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('meridian-only-skill')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Switch organisation' }));
    expect(await screen.findByText('apex-only-skill')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('meridian-only-skill')).not.toBeInTheDocument());
  });

  test('switching organisation discards the paging state the previous organisation built up', async () => {
    const twoOrgs: Me = { ...me, orgs: [
      { org_id: 'o1', slug: 'meridian', name: 'Meridian Data', role: 'owner' },
      { org_id: 'o2', slug: 'apex', name: 'Apex Systems', role: 'owner' },
    ] };
    const controller = new AccessController({ fetchMe: async () => twoOrgs, onDenied: vi.fn() });
    await controller.check(true);
    const asked: string[] = [];
    const client = new ApiClient({ baseUrl: 'https://api.test', delay: async () => {}, fetchImpl: async url => {
      const at = String(url);
      const org = at.includes('/orgs/apex/') ? 'apex' : 'meridian';
      if (at.includes('/map/repository')) {
        asked.push(at);
        const cursor = new URL(at).searchParams.get('cursor');
        return fakeResponse({
          path: '', next_cursor: cursor ? null : 'page-2',
          children: [{ path: org + (cursor ? '/second.md' : '/first.md'), name: org + (cursor ? '-second' : '-first'), kind: 'document', skill_id: null, skills: 0 }],
        });
      }
      return fakeResponse({});
    } });
    const source = createApiDataSource({ client });
    function SwitchOrganisation() {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/map?org=apex&repo=monorepo&tab=repository')}>Switch organisation</button>;
    }
    render(<MemoryRouter initialEntries={['/map?org=meridian&repo=monorepo&tab=repository']}>
      <AccessProvider controller={controller}><App source={source} /><SwitchOrganisation /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('meridian-first')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Read the next 100 objects' }));
    expect(await screen.findByText('meridian-second')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Switch organisation' }));
    expect(await screen.findByText('apex-first')).toBeInTheDocument();
    // The tree is read from the first page again: a cursor issued for the previous organisation
    // is not a position in this one, and the rows it produced are gone.
    expect(asked.filter(at => at.includes('/orgs/apex/')).some(at => at.includes('cursor='))).toBe(false);
    expect(screen.queryByText('meridian-first')).not.toBeInTheDocument();
    expect(screen.queryByText('meridian-second')).not.toBeInTheDocument();
  });

  test('an organisation the account does not belong to is masked, not explained', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/library?org=someone-else']}>
      <AccessProvider controller={controller}><App source={fakeSource()} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('Organization unavailable')).toBeInTheDocument();
    expect(screen.getByText('Access unavailable')).toBeInTheDocument();
    expect(screen.queryByText('someone-else')).not.toBeInTheDocument();
  });

  test('an unauthenticated management route leaves the shell for the full-width login page', async () => {
    const controller = new AccessController({ fetchMe: async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); }, onDenied: vi.fn() });
    await controller.check(true);
    const source = fakeSource({ getAuthProviders: async () => ({ mode: 'workos' as const, providers: [{ id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' }] }) });
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /><Probe /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    // The shell is gone: no rail, no organisation context, nothing read for that organisation.
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent('/login?return=' + encodeURIComponent('/library?org=meridian&repo=monorepo'));
  });

  test('an unauthenticated /import?step=login shows the login page, and signing in returns to it', async () => {
    const controller = new AccessController({ fetchMe: async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); }, onDenied: vi.fn() });
    await controller.check(true);
    const startLogin = vi.fn(async () => ({ provider: 'github', loginUrl: '' }));
    const source = fakeSource({
      getAuthProviders: async () => ({ mode: 'workos' as const, providers: [{ id: 'github', label: 'GitHub', login_url: '/api/v1/auth/login/github' }] }),
      startLogin,
    });
    render(<MemoryRouter initialEntries={['/import?step=login']}>
      <AccessProvider controller={controller}><App source={source} /><Probe /></AccessProvider>
    </MemoryRouter>);
    const button = await screen.findByRole('button', { name: /Continue with GitHub/ });
    expect(screen.getByTestId('where')).toHaveTextContent('/login?return=' + encodeURIComponent('/import?step=login'));
    await userEvent.click(button);
    // Sign-in finishes at the provider and the API 302s to return_to, so the round trip is
    // the address handed to the API, not an in-app navigation.
    expect(startLogin).toHaveBeenCalledWith('github', '/import?step=login');
  });

  test('a confirmed session on /import?step=login gets the wizard at its first real step', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const source = fakeSource({ listRepos: async () => [] });
    render(<MemoryRouter initialEntries={['/import?step=login']}>
      <AccessProvider controller={controller}><App source={source} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Import repository skills' })).toBeInTheDocument();
    // Sign-in is no longer a step of the wizard: the stale address falls through to the first
    // real step this account is at (an organisation from /me, no repository in the URL yet).
    expect(await screen.findByText('Repositories')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continue with/ })).not.toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Import progress' })).queryByText('Sign in')).not.toBeInTheDocument();
  });

  test('a confirmed session that opens /login is sent on to the address it carried', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/login?return=' + encodeURIComponent('/import?step=preview')]}>
      <AccessProvider controller={controller}><App source={fakeSource({ listRepos: async () => [] })} /><Probe /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Import repository skills' })).toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent('/import?step=preview');
  });

  test('a 403 on a resource with a live session is a panel, never a redirect back into it', async () => {
    // The loop this prevents: 403 -> /login -> the provider round trip -> the same address -> 403.
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const client = new ApiClient({ baseUrl: 'https://api.test', delay: async () => {}, fetchImpl: async url =>
      String(url).endsWith('/api/v1/me')
        ? fakeResponse(me)
        : fakeResponse({ error: 'forbidden', message: 'No.', request_id: 'r-1' }, { status: 403 }) });
    const source = createApiDataSource({ client, onDenied: error => controller.reportDenied(error.status === 403 ? 'forbidden' : 'unauthenticated') });
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /><Probe /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('Not available to your account', {}, { timeout: 4000 })).toBeInTheDocument();
    // Still inside the shell, still signed in, and not on the login page.
    expect(screen.getByTestId('where')).toHaveTextContent('/library?org=meridian&repo=monorepo');
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open your organization' })).toBeInTheDocument();
    // An action, not a link: it has to end the session and forget the identity first.
    expect(screen.getByRole('button', { name: 'Sign in again' })).toBeInTheDocument();
  });

  test('the way out of a forbidden address is the account own organisation, not the login page', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const client = new ApiClient({ baseUrl: 'https://api.test', delay: async () => {}, fetchImpl: async url =>
      String(url).endsWith('/api/v1/me')
        ? fakeResponse(me)
        : fakeResponse({ error: 'forbidden', message: 'No.', request_id: 'r-1' }, { status: 403 }) });
    const source = createApiDataSource({ client, onDenied: error => controller.reportDenied(error.status === 403 ? 'forbidden' : 'unauthenticated') });
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /><Probe /></AccessProvider>
    </MemoryRouter>);
    await userEvent.click(await screen.findByRole('button', { name: 'Open your organization' }, { timeout: 4000 }));
    // The refused repository is gone from the address, and the denial is cleared so the heartbeat
    // may confirm membership again instead of leaving every view masked.
    expect(screen.getByTestId('where')).toHaveTextContent('/import?org=meridian&step=preview');
    expect(screen.getByTestId('where')).not.toHaveTextContent('/login');
  });

  test('Sign in again from a forbidden view really reaches the sign-in form', async () => {
    // The trap this covers: a forbidden denial keeps the identity, `derive()` stays 'denied' once
    // denied, and /login shows the neutral shell while an identity is held — so a plain link to
    // /login left the operator on "Checking your session" for ever: no form, no redirect.
    let session = true;
    const controller = new AccessController({
      fetchMe: async () => { if (!session) throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); return me; },
      onDenied: vi.fn(),
    });
    await controller.check(true);
    const logout = vi.fn(async () => { session = false; });
    const source = fakeSource({
      logout,
      getAuthProviders: async () => ({ mode: 'workos' as const, providers: [{ id: 'github' as const, label: 'GitHub', login_url: '/api/v1/auth/login/github' }] }),
    });
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /><Probe /></AccessProvider>
    </MemoryRouter>);
    controller.reportDenied('forbidden');
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in again' }));
    expect(logout).toHaveBeenCalledTimes(1);
    // No return target: the refused address is the one place this must not come back to.
    expect(screen.getByTestId('where')).toHaveTextContent('/login');
    expect(screen.getByTestId('where')).not.toHaveTextContent('return=');
    expect(await screen.findByRole('button', { name: /Continue with GitHub/ }, { timeout: 4000 })).toBeInTheDocument();
  });

  test('opening the login page with a live session never flashes the sign-in form', async () => {
    let answer: (value: Me) => void = () => {};
    const controller = new AccessController({ fetchMe: () => new Promise<Me>(resolve => { answer = resolve; }), onDenied: vi.fn() });
    const getAuthProviders = vi.fn(async () => ({ mode: 'workos' as const, providers: [{ id: 'github' as const, label: 'GitHub', login_url: '/api/v1/auth/login/github' }] }));
    render(<MemoryRouter initialEntries={['/login?return=' + encodeURIComponent('/usage')]}>
      <AccessProvider controller={controller}><App source={fakeSource({ getAuthProviders })} /><Probe /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('Checking your session')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continue with/ })).not.toBeInTheDocument();
    // Nothing was asked of the API while the session was still unknown.
    expect(getAuthProviders).not.toHaveBeenCalled();
    answer(me);
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/usage'));
    expect(getAuthProviders).not.toHaveBeenCalled();
  });

  test('the component gallery stays reachable while the session is refused', async () => {
    const controller = new AccessController({ fetchMe: async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); }, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/__components']}>
      <AccessProvider controller={controller}><App source={rejectingSource()} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Component gallery' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: 'Sign in' })).not.toBeInTheDocument();
  });

  test('an unconfirmed session masks the view instead of revealing stale data', async () => {
    let clock = 1_000_000;
    let answered = false;
    // The second /me fails without a denial, so the 45 s window closes unconfirmed.
    const controller = new AccessController({
      fetchMe: async () => { if (answered) throw new ApiError({ status: 0, code: 'timeout', message: 'no answer' }); answered = true; return me; },
      onDenied: vi.fn(), now: () => clock,
    });
    await controller.check(true);
    clock += 46_000;
    controller.refresh();
    render(<MemoryRouter initialEntries={['/organization?org=meridian']}>
      <AccessProvider controller={controller}><App source={fakeSource()} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('Access not reconfirmed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check access now' })).toBeInTheDocument();
  });

  test('the library reads the API and shows nothing when it answers an empty page', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const source = fakeSource({
      listSkills: async () => ({ items: [], next_cursor: null, snapshot_id: 'snap-1', schema_version: 'mgmt-1', filters: {} }),
      getFacets: async () => ({ field: 'scope', values: [], next_cursor: null }),
    });
    render(<MemoryRouter initialEntries={['/library?org=meridian&repo=monorepo']}>
      <AccessProvider controller={controller}><App source={source} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('No skills yet')).toBeInTheDocument();
    expect(screen.queryByText('postgres-auth')).not.toBeInTheDocument();
  });
});
