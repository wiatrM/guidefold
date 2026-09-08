import { describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ApiOrganizationRoute, OrganizationRoute } from './OnboardingRoutes';
import { ApiError } from '../api/client';
import type { AuditPage, Installation, Member } from '../api/decoders';
import type { ApiRouteContext, RouteContext } from '../domain';
import type { DataSource } from '../data/source';
import { fakeSource } from '../test/fakes';
import { meridian } from '../data/meridian';

const me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' as const }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};
const owners: Member[] = [{ user_id: 'u1', email: 'ada@example.com', name: 'Ada', role: 'owner', joined_at: '2026-01-01T00:00:00Z' }];
const installation = (over: Partial<Installation> = {}): Installation => ({
  installation_id: 'k1', name: 'ci-runner', repo_id: 'monorepo', scopes: ['search', 'use', 'events'],
  harness: 'claude', last_seen_at: null, adapter_version: null, capabilities: null, created_at: null, token: null,
  ...over,
});

function renderRoute(source: DataSource, search = '', over: Partial<ApiRouteContext> = {}) {
  const params = new URLSearchParams(search);
  const ctx: ApiRouteContext = {
    source, access: { status: 'confirmed', me, checkedAt: 1 }, me, org: 'meridian', repo: 'monorepo',
    role: 'owner', params, view: 'organization',
    href: (view, changes = {}) => '/' + view + '?' + new URLSearchParams(Object.entries(changes).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, String(value)])).toString(),
    go: vi.fn(),
    ...over,
  };
  return render(<MemoryRouter><ApiOrganizationRoute ctx={ctx} /></MemoryRouter>);
}

describe('Organization route, members', () => {
  test('the last-owner 409 is shown inline on that row and nothing is claimed as removed', async () => {
    const source = fakeSource({
      listMembers: async () => owners,
      removeMember: async () => { throw new ApiError({ status: 409, code: 'last_owner_protected', message: 'conflict' }); },
    });
    renderRoute(source);
    await userEvent.click(await screen.findByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('The last owner cannot be removed. Add another owner first.')).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
  });

  test('a 409 on a role change keeps the current role visible', async () => {
    const source = fakeSource({
      listMembers: async () => owners,
      changeMemberRole: async () => { throw new ApiError({ status: 409, code: 'last_owner_protected', message: 'conflict' }); },
    });
    renderRoute(source);
    await userEvent.selectOptions(await screen.findByLabelText('Role of ada@example.com'), 'member');
    expect(await screen.findByText('The last owner keeps the owner role. Add another owner first.')).toBeInTheDocument();
    expect((await screen.findByLabelText('Role of ada@example.com') as HTMLSelectElement).value).toBe('owner');
  });

  test('the invitation link is returned once and marked as not stored', async () => {
    const source = fakeSource({
      listMembers: async () => owners,
      inviteMember: async () => ({ invitation_id: 'i1', accept_url: 'https://app.test/invitations/tok-1/accept', expires_at: null, email: 'bob@example.com', role: 'member' as const }),
    });
    renderRoute(source);
    await userEvent.type(await screen.findByLabelText('E-mail address'), 'bob@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Create invitation' }));
    expect(await screen.findByLabelText('Invitation accept URL')).toHaveTextContent('https://app.test/invitations/tok-1/accept');
    expect(screen.getByText('Shown once')).toBeInTheDocument();
    expect(screen.getByText('Not stored')).toBeInTheDocument();
  });

  test('a member sees the read-only notice and disabled owner controls', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners }), '', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Create invitation' })).toBeDisabled();
    expect(screen.queryByLabelText('Role of ada@example.com')).not.toBeInTheDocument();
  });
});

describe('Organization route, integrations', () => {
  test('absent adapter health reads Unknown, never zero', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [installation()] }), 'tab=integrations');
    await screen.findByText('ci-runner');
    const row = screen.getByRole('row', { name: /ci-runner/ });
    expect(row).toHaveTextContent('Unknown');
    expect(row).toHaveTextContent('search, use, events');
  });

  test('a created installation shows its token once, with a copy action', async () => {
    const source = fakeSource({
      listInstallations: async () => [],
      createInstallation: async () => installation({ token: 'gf_secret_value' }),
    });
    renderRoute(source, 'tab=integrations');
    await userEvent.type(await screen.findByLabelText('Installation name'), 'ci-runner');
    await userEvent.click(screen.getByRole('button', { name: 'Create installation' }));
    expect(await screen.findByLabelText('Installation token value')).toHaveTextContent('gf_secret_value');
    expect(screen.getByRole('button', { name: 'Copy value' })).toBeInTheDocument();
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
  });

  test('revoking an installation reports it and re-reads the list', async () => {
    const revokeInstallation = vi.fn(async () => {});
    const listInstallations = vi.fn(async () => [installation()]);
    renderRoute(fakeSource({ listInstallations, revokeInstallation }), 'tab=integrations');
    await userEvent.click(await screen.findByRole('button', { name: 'Revoke' }));
    expect(revokeInstallation).toHaveBeenCalledWith('meridian', 'k1', 'revoke:meridian:k1');
    await waitFor(() => expect(listInstallations.mock.calls.length).toBeGreaterThan(1));
    expect(await screen.findByText('Installation revoked. Adapters using that token stop being served.')).toBeInTheDocument();
  });

  test('a device code in the URL opens the approval panel', async () => {
    const decideDevice = vi.fn(async () => ({ user_code: 'ABCD-1234', state: 'approved' as const, expires_at: null }));
    renderRoute(fakeSource({ listInstallations: async () => [], decideDevice }), 'tab=integrations&device=ABCD-1234');
    expect(await screen.findByText('Device authorization')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Approve this device' }));
    expect(decideDevice).toHaveBeenCalledWith('ABCD-1234', true, 'device:ABCD-1234:approve');
    expect(await screen.findByText('Device request ABCD-1234 is now approved.')).toBeInTheDocument();
  });

  test('without a device code there is no approval panel', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [] }), 'tab=integrations');
    await screen.findByText('No installation yet');
    expect(screen.queryByText('Device authorization')).not.toBeInTheDocument();
  });
});

const auditPage = (over: Partial<AuditPage> = {}): AuditPage => ({
  items: [{ at: '2026-09-01T00:00:00Z', actor: 'ada@example.com', action: 'member.invite', entity: 'urn:member:bob', revision: null, request_id: 'req-1' }],
  next_cursor: null,
  ...over,
});

describe('Organization route, audit', () => {
  test('audit entries are read only once the tab is open, with all six columns shown', async () => {
    const getAudit = vi.fn(async () => auditPage());
    renderRoute(fakeSource({ getAudit }), 'tab=audit');
    expect(await screen.findByText('member.invite')).toBeInTheDocument();
    expect(getAudit).toHaveBeenCalledWith('meridian', undefined);
    const row = screen.getByRole('row', { name: /member.invite/ });
    expect(row).toHaveTextContent('ada@example.com');
    expect(row).toHaveTextContent('urn:member:bob');
    expect(row).toHaveTextContent('req-1');
  });

  test('no entries renders the empty state, not an empty table', async () => {
    renderRoute(fakeSource({ getAudit: async () => auditPage({ items: [] }) }), 'tab=audit');
    expect(await screen.findByText('No audit entries yet')).toBeInTheDocument();
  });

  test('a next_cursor page advances the URL cursor via a Next page action', async () => {
    const go = vi.fn();
    renderRoute(fakeSource({ getAudit: async () => auditPage({ next_cursor: 'cur-2' }) }), 'tab=audit', { go });
    await userEvent.click(await screen.findByRole('button', { name: 'Next page' }));
    expect(go).toHaveBeenCalledWith('organization', { tab: 'audit', cursor: 'cur-2' });
  });

  test('a member sees the owner note and the audit log is never read', async () => {
    const getAudit = vi.fn();
    renderRoute(fakeSource({ getAudit }), 'tab=audit', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    expect(getAudit).not.toHaveBeenCalled();
  });
});

describe('Organization route, identity linking', () => {
  // jsdom's window.location.assign is a non-configurable, non-writable own property and cannot
  // be spied on; the assertions below stop at the call that decides whether to redirect, which
  // is the boundary this test double can actually observe.
  test('a link suggestion is never auto-linked: the operator action starts the flow with a stable key', async () => {
    const startIdentityLink = vi.fn(async () => ({ provider: 'github', loginUrl: 'https://auth.test/link/github' }));
    renderRoute(fakeSource({ listMembers: async () => owners, startIdentityLink }), '', {
      me: { ...me, link_suggestions: [{ provider: 'github' }] },
    });
    expect(await screen.findByText('Another sign-in method uses this e-mail.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Link github' }));
    await waitFor(() => expect(startIdentityLink).toHaveBeenCalledWith('github', 'identity-link:u1:github'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test('a response with no redirect URL is reported honestly, not silently ignored', async () => {
    const startIdentityLink = vi.fn(async () => ({ provider: 'github', loginUrl: '' }));
    renderRoute(fakeSource({ listMembers: async () => owners, startIdentityLink }), '', {
      me: { ...me, link_suggestions: [{ provider: 'github' }] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Link github' }));
    expect(await screen.findByText('The API returned no redirect for github.')).toBeInTheDocument();
  });

  test('with no link suggestions, no notice is shown', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners }));
    await screen.findByText('ada@example.com');
    expect(screen.queryByText('Another sign-in method uses this e-mail.')).not.toBeInTheDocument();
  });
});

// The local Meridian fixture flow (OrganizationRoute), not the hosted API flow above (ApiOrganizationRoute).
function fixtureCtx(over: Partial<RouteContext> = {}): RouteContext {
  const params = over.params ?? new URLSearchParams();
  return {
    data: meridian, source: fakeSource(), mode: 'fixture', params,
    state: 'ready', view: 'organization', member: false, canWrite: true, canFeedback: true,
    memory: {}, save: vi.fn(),
    href: (view, changes = {}) => '/' + view + '?' + new URLSearchParams(
      Object.entries({ ...Object.fromEntries(params.entries()), ...changes })
        .filter(([, value]) => value !== null && value !== undefined)
        .map(([key, value]) => [key, String(value)]),
    ).toString(),
    go: vi.fn(),
    ...over,
  };
}

describe('Organization route, fixture', () => {
  test('the Members panel action slot no longer holds an inert StateBadge', () => {
    const ctx = fixtureCtx();
    render(<MemoryRouter><OrganizationRoute ctx={ctx} /></MemoryRouter>);
    const membersPanel = screen.getByRole('region', { name: 'Members' });
    const badge = within(membersPanel).getByText('Local scenario');
    const header = membersPanel.querySelector('header');
    expect(header?.contains(badge)).toBe(false);
  });

  test('feedback text renders with its icon once a local action runs, and stays empty before that', async () => {
    const ctx = fixtureCtx({ source: fakeSource({
      inviteMember: async () => ({ invitation_id: 'i1', accept_url: 'https://app.test/accept/i1', expires_at: null, email: null, role: null }),
    }) });
    render(<MemoryRouter><OrganizationRoute ctx={ctx} /></MemoryRouter>);
    const before = screen.getByRole('status', { hidden: true });
    expect(before).toBeEmptyDOMElement();
    await userEvent.type(screen.getByLabelText('Member label for local simulation'), 'ops-lead');
    await userEvent.click(screen.getByRole('button', { name: 'Add local member' }));
    const feedbackText = await screen.findByText('Local member entry created. No invitation was sent.');
    const feedback = feedbackText.closest('p[role="status"]');
    expect(feedback?.querySelector('svg')).toBeTruthy();
  });

  test('the default integration caption carries no success icon; the icon appears after the local check', async () => {
    const ctx = fixtureCtx({ params: new URLSearchParams('tab=integrations'),
      source: fakeSource({ listInstallations: async () => [] }) });
    render(<MemoryRouter><OrganizationRoute ctx={ctx} /></MemoryRouter>);
    const before = screen.getByText('No local connection check has been run.');
    expect(before.closest('p[role="status"]')?.querySelector('svg')).toBeFalsy();
    await userEvent.click(screen.getByRole('button', { name: 'Simulate connection check' }));
    const after = await screen.findByText(/Local check complete/);
    expect(after.closest('p[role="status"]')?.querySelector('svg')).toBeTruthy();
  });

  test('the Install an adapter panel states the simulation before the button', () => {
    const ctx = fixtureCtx({ params: new URLSearchParams('tab=integrations') });
    render(<MemoryRouter><OrganizationRoute ctx={ctx} /></MemoryRouter>);
    const panel = screen.getByRole('region', { name: 'Install an adapter' });
    const intro = within(panel).getByText(/This is a local simulation/);
    const button = within(panel).getByRole('button', { name: 'Simulate connection check' });
    // eslint-disable-next-line no-bitwise
    expect(Boolean(intro.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });
});
