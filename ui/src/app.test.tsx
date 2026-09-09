import { afterEach, describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import App from './app';
import { AccessController, AccessProvider } from './api/access';
import { ApiClient, ApiError } from './api/client';
import { createApiDataSource } from './data/apiSource';
import { fakeResponse, fakeSource } from './test/fakes';
import type { Me } from './api/decoders';
// Layout, zoom and reduced motion are covered by schema-navigation browser tests.
vi.mock('./components/PyramidChart/SchemaFlow',()=>({SchemaFlow:()=> <div role="region" aria-label="Skill hierarchy"/>}));

const me: Me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian Data', role: 'owner' }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};

afterEach(() => { sessionStorage.clear(); });

const rejectingSource = () => fakeSource();

describe('shell composition', () => {
  test('the component gallery renders outside the shell and reads nothing from the API', async () => {
    render(<MemoryRouter initialEntries={['/__components']}><App source={rejectingSource()} /></MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Component gallery' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(screen.getByText(/Sample values from examples\/monorepo/)).toBeInTheDocument();
  });

  test('an unknown path lands on Import, and nothing but the hosted API is named in the footer', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/nowhere']}>
      <AccessProvider controller={controller}><App source={fakeSource({ getAuthProviders: async () => ({ mode: 'dev' as const, providers: [] }) })} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('heading', { level: 1, name: 'Import repository skills' })).toBeInTheDocument();
    expect(screen.getByText(/^Hosted API\./)).toBeInTheDocument();
    expect(document.title).toBe('Import | Guidefold');
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

  test('a denied session routes to the restricted state and still offers sign-in on Import', async () => {
    const controller = new AccessController({ fetchMe: async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); }, onDenied: vi.fn() });
    await controller.check(true);
    render(<MemoryRouter initialEntries={['/library']}>
      <AccessProvider controller={controller}><App source={fakeSource()} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findAllByText('Access unavailable')).not.toHaveLength(0);
    expect(screen.getByRole('link', { name: 'Sign in again' })).toBeInTheDocument();
  });

  test('after a denial the Import view still reaches the sign-in step', async () => {
    const controller = new AccessController({ fetchMe: async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); }, onDenied: vi.fn() });
    await controller.check(true);
    const source = fakeSource({ getAuthProviders: async () => ({ mode: 'workos' as const, providers: [{ id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' }] }) });
    render(<MemoryRouter initialEntries={['/import']}>
      <AccessProvider controller={controller}><App source={source} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('button', { name: /Continue with Google/ })).toBeInTheDocument();
    expect(screen.getByText('Access unavailable')).toBeInTheDocument();
  });

  test('an anonymous user can reach sign-in when the API is temporarily unavailable', async () => {
    const controller = new AccessController({
      fetchMe: async () => { throw new ApiError({ status: 503, code: 'database_unavailable', message: 'temporarily unavailable' }); },
      onDenied: vi.fn(),
    });
    await controller.check(true);
    const source = fakeSource({ getAuthProviders: async () => ({ mode: 'workos' as const, providers: [{ id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' }] }) });
    render(<MemoryRouter initialEntries={['/import']}>
      <AccessProvider controller={controller}><App source={source} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByRole('button', { name: /Continue with Google/ })).toBeInTheDocument();
  });

  test('an authenticated user can accept an invitation from its browser landing page', async () => {
    const controller = new AccessController({ fetchMe: async () => me, onDenied: vi.fn() });
    await controller.check(true);
    const acceptInvitation = vi.fn(async () => ({ org_id: 'o2', role: 'member' as const, joined: true }));
    const source = fakeSource({ acceptInvitation });
    render(<MemoryRouter initialEntries={['/invitations/invite-token/accept']}>
      <AccessProvider controller={controller}><App source={source} /></AccessProvider>
    </MemoryRouter>);
    expect(await screen.findByText('ada@example.com')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Accept invitation' }));
    await waitFor(() => expect(acceptInvitation).toHaveBeenCalledWith('invite-token', expect.stringMatching(/^accept-invitation:/)));
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
