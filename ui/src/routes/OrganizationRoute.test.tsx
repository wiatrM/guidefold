import { describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ApiOrganizationRoute } from './OnboardingRoutes';
import { ApiError } from '../api/client';
import type { AuditPage, GitHubInstallation, Installation, InvitationLifecycle, Member, OrgCredential, Usage } from '../api/decoders';
import type { ApiRouteContext } from '../domain';
import type { DataSource } from '../data/source';
import { fakeSource } from '../test/fakes';

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
const githubInstallation = (over: Partial<GitHubInstallation> = {}): GitHubInstallation => ({
  installation_id: 501, account: 'meridian-data', repositories: [{ full_name: 'meridian-data/monorepo', repo_id: null }],
  suspended: false, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:05:00Z',
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
  test('a user can update the Guidefold display name and recheck the session', async () => {
    const updateProfile = vi.fn(async (name: string) => ({ user: { id: 'u1', email: 'ada@example.com', name } }));
    const recheckAccess = vi.fn(async () => {});
    renderRoute(fakeSource({ listMembers: async () => owners, updateProfile }), '', { recheckAccess });
    const input = await screen.findByLabelText('Display name');
    await userEvent.clear(input);
    await userEvent.type(input, 'Ada Lovelace');
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    expect(updateProfile).toHaveBeenCalledWith('Ada Lovelace', 'profile:u1:Ada Lovelace');
    expect(recheckAccess).toHaveBeenCalled();
    expect(await screen.findByText('Profile name saved.')).toBeInTheDocument();
  });

  test('owners can see invitation lifecycle and revoke a pending link', async () => {
    const invitations: InvitationLifecycle[] = [{ invitation_id: 'i1', email: 'bob@example.com', role: 'member', status: 'pending', created_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-15T00:00:00Z', accepted_at: null, revoked_at: null }];
    const listInvitations = vi.fn(async () => invitations);
    const revokeInvitation = vi.fn(async () => {});
    renderRoute(fakeSource({ listMembers: async () => owners, listInvitations, revokeInvitation }));
    const row = (await screen.findByText('bob@example.com')).closest('tr')!;
    await userEvent.click(within(row).getByRole('button', { name: 'Revoke' }));
    expect(revokeInvitation).toHaveBeenCalledWith('meridian', 'i1', 'revoke-invitation:meridian:i1');
    await waitFor(() => expect(listInvitations.mock.calls.length).toBeGreaterThan(1));
    expect(await screen.findByText('Invitation for bob@example.com was revoked.')).toBeInTheDocument();
  });

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

  test('the adapter setup guide shows all five commands and, for an owner, a link to Create an installation', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [] }), 'tab=integrations');
    await screen.findByText('Set up an adapter');
    expect(screen.getByText('guidefold install --harness claude')).toBeInTheDocument();
    expect(screen.getByText('guidefold login')).toBeInTheDocument();
    expect(screen.getByText(
      'printf \'%s\' "<paste the installation token>" > ~/.config/guidefold/search-token '
      + '&& chmod 600 ~/.config/guidefold/search-token '
      + '&& export GUIDEFOLD_SEARCH_TOKEN_FILE=~/.config/guidefold/search-token',
    )).toBeInTheDocument();
    expect(screen.getByText('guidefold doctor')).toBeInTheDocument();
    expect(screen.getByText('guidefold telemetry flush --url <api>')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Open Create an installation' });
    expect(link).toHaveAttribute('href', '/#create-installation');
  });

  test('a member sees the same adapter guide but no link to create a token', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [] }), 'tab=integrations', { role: 'member' });
    await screen.findByText('Set up an adapter');
    expect(screen.getByText('guidefold install --harness claude')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Open Create an installation' })).not.toBeInTheDocument();
    expect(screen.getByText('Only an owner can create an installation token here; ask one to run this step.')).toBeInTheDocument();
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

  test('a member still sees the owner note, but the audit log (1.3.0) is read and scoped as "Your own actions"', async () => {
    const getAudit = vi.fn(async () => auditPage());
    renderRoute(fakeSource({ getAudit }), 'tab=audit', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    // The server, not the client, scopes a member to their own rows (contract §4.1); the client
    // just reads whatever it is handed and labels the eyebrow accordingly.
    expect(await screen.findByText('member.invite')).toBeInTheDocument();
    expect(getAudit).toHaveBeenCalledWith('meridian', undefined);
    expect(screen.getByText('Your own actions')).toBeInTheDocument();
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

describe('Organization route, presentation', () => {
  test('the four sections are tab links and the address chooses the current one', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [] }), 'tab=integrations');
    const nav = screen.getByRole('navigation', { name: 'Organization sections' });
    expect(within(nav).getAllByRole('link').map(link => link.textContent)).toEqual(['Members', 'Integrations', 'Telemetry', 'Audit', 'Model keys']);
    expect(within(nav).getByRole('link', { name: 'Integrations' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: 'Members' })).not.toHaveAttribute('aria-current');
    expect(await screen.findByText('No installation yet')).toBeInTheDocument();
  });

  test('telemetry tab reads the repository report and exposes scorecards', async () => {
    const getUsage = vi.fn(async (): Promise<Usage> => ({
      window: { from: '2026-09-01T00:00:00Z', to: '2026-09-10T00:00:00Z', watermark: '2026-09-10T00:00:00Z' },
      coverage: { events_received: 42, dropped_reported: 0, oldest_lag_s: 2, task_ids_present: true },
      totals: {
        exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0,
        use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null,
        metrics: {
          tasks_started: 3, tasks_finished: 3, tasks_succeeded: 2, tasks_failed: 1, tasks_unknown: 0, harness_errors: 0,
          search_requests: 4, search_results: 4, search_errors: 0, use_requests: 3, ask_count: 1,
          input_tokens: 100, output_tokens: 40, tool_calls: 5, latency_ms: 900, latency_samples: 3,
          tasks_observed: true, cost_observed: true,
        },
      },
      previous: null,
      skills: [], queue: [], health: null,
    }));
    renderRoute(fakeSource({ getUsage }), 'tab=telemetry');
    const scorecards = within(await screen.findByRole('region', { name: 'Decision scorecards' }));
    expect(scorecards.getByText('2 / 3')).toBeInTheDocument();
    expect(scorecards.getByText('1 ASK')).toBeInTheDocument();
    expect(getUsage).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, { window: undefined });
    expect(await screen.findByText('Events received')).toBeInTheDocument();
  });

  test('the member status line is empty before any action and carries the outcome after one', async () => {
    const removeMember = vi.fn(async () => {});
    renderRoute(fakeSource({ listMembers: async () => owners, removeMember }));
    await screen.findByRole('table', { name: 'Members of this organization' });
    // `.feedback:empty` hides the line until it has text, so the query must include hidden nodes.
    const status = screen.getAllByRole('status', { hidden: true }).find(node => node.tagName === 'P')!;
    expect(status).toBeEmptyDOMElement();
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('ada@example.com was removed from this organization.')).toBe(status);
  });

  test('an installation row shows its scopes and reads Unknown for absent health values', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [installation({ capabilities: ['search'], adapter_version: '0.4.1' })] }), 'tab=integrations');
    const row = (await screen.findByText('ci-runner')).closest('tr')!;
    expect(within(row).getByText('search, use, events')).toBeInTheDocument();
    expect(within(row).getByText('0.4.1')).toBeInTheDocument();
    expect(within(row).getByText('Unknown')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Revoke' })).toBeEnabled();
  });

  test('a member reads the installation list but every owner control is disabled', async () => {
    renderRoute(fakeSource({ listInstallations: async () => [installation()] }), 'tab=integrations', { role: 'member' });
    expect(await screen.findByRole('button', { name: 'Revoke' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Create installation' })).toBeDisabled();
    expect(screen.getByLabelText('Harness')).toBeDisabled();
    expect(screen.getByText(/Member access is read only here/)).toBeInTheDocument();
  });
});

const credential = (over: Partial<OrgCredential> = {}): OrgCredential => ({
  provider: 'openrouter', name: 'default', last4: '9f2a', model: 'gpt-5.6', preferred: true,
  created_at: '2026-09-01T00:00:00Z', created_by: 'u1',
  ...over,
});

describe('Organization route, model keys', () => {
  test('every provider gets a row, including one with no stored key', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential()] }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const openrouter = within(table).getByRole('row', { name: /openrouter/ });
    expect(openrouter).toHaveTextContent('default');
    expect(openrouter).toHaveTextContent('9f2a');
    expect(openrouter).toHaveTextContent('gpt-5.6');
    expect(within(openrouter).getByText('Preferred')).toBeInTheDocument();
    const anthropic = within(table).getByRole('row', { name: /anthropic/ });
    expect(anthropic).toHaveTextContent('No key stored');
    const openai = within(table).getByRole('row', { name: /openai/ });
    expect(openai).toHaveTextContent('No key stored');
  });

  test('a stored key with no model reads as "Provider default", not a blank cell', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential({ model: '' })] }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    expect(within(table).getByRole('row', { name: /openrouter/ })).toHaveTextContent('Provider default');
  });

  test('an owner can store a key and the value is never kept after the request', async () => {
    const setCredential = vi.fn(async (org: string, provider: string, input: { api_key: string; name?: string | null }) => credential({ provider: provider as OrgCredential['provider'], name: input.name ?? '' }));
    renderRoute(fakeSource({ listCredentials: async () => [], setCredential }), 'tab=keys');
    await userEvent.type(await screen.findByLabelText('API key'), 'sk-test-value');
    await userEvent.click(screen.getByRole('button', { name: 'Store key' }));
    expect(setCredential).toHaveBeenCalledWith('meridian', 'openrouter', { api_key: 'sk-test-value', name: undefined, model: undefined }, 'credential:meridian:openrouter');
    expect(await screen.findByText('Key saved for openrouter.')).toBeInTheDocument();
    expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('');
  });

  test('an owner can set the model as free text alongside the key, with no dropdown of model names', async () => {
    const setCredential = vi.fn(async (org: string, provider: string, input: { api_key: string; model?: string | null }) => credential({ provider: provider as OrgCredential['provider'], model: input.model ?? '' }));
    renderRoute(fakeSource({ listCredentials: async () => [], setCredential }), 'tab=keys');
    expect(screen.queryByRole('combobox', { name: 'Model' })).not.toBeInTheDocument();
    await userEvent.type(await screen.findByLabelText('Model'), 'anthropic/claude-my-finetune');
    await userEvent.type(screen.getByLabelText('API key'), 'sk-test-value');
    await userEvent.click(screen.getByRole('button', { name: 'Store key' }));
    expect(setCredential).toHaveBeenCalledWith('meridian', 'openrouter', expect.objectContaining({ model: 'anthropic/claude-my-finetune' }), 'credential:meridian:openrouter');
  });

  test('"Make preferred" is one click: no form pre-fill, no key, just {preferred: true}', async () => {
    const patchCredential = vi.fn(async (org: string, provider: string, input: { model?: string; preferred?: boolean }) => credential({ provider: provider as OrgCredential['provider'], preferred: input.preferred ?? false }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential({ provider: 'openrouter', preferred: true }), credential({ provider: 'anthropic', name: 'backup', last4: 'aa11', model: 'claude-x', preferred: false })],
      patchCredential,
    }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const anthropicRow = within(table).getByRole('row', { name: /anthropic/ });
    await userEvent.click(within(anthropicRow).getByRole('button', { name: 'Make preferred' }));
    expect(patchCredential).toHaveBeenCalledWith('meridian', 'anthropic', { preferred: true }, expect.stringContaining('credential-patch:meridian:anthropic'));
    // No key was ever asked for: the create/replace form's own Provider select is untouched
    // (still defaulted to the first provider), proving nothing pre-filled it for this action.
    expect((screen.getByLabelText('Provider') as HTMLSelectElement).value).toBe('openrouter');
    expect(screen.queryByText(/Re-enter the API key/)).not.toBeInTheDocument();
    expect(await screen.findByText('anthropic is now the preferred credential.')).toBeInTheDocument();
  });

  test('an already-preferred credential offers no "unprefer" control', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential({ preferred: true })] }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const row = within(table).getByRole('row', { name: /openrouter/ });
    expect(within(row).getByText('Preferred')).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: 'Make preferred' })).not.toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: /unprefer/i })).not.toBeInTheDocument();
  });

  test('editing the model is its own inline edit sending {model: "..."}, free text, no key', async () => {
    const patchCredential = vi.fn(async (org: string, provider: string, input: { model?: string; preferred?: boolean }) => credential({ model: input.model ?? '' }));
    const listCredentials = vi.fn(async () => [credential({ model: 'gpt-5.6' })]);
    renderRoute(fakeSource({ listCredentials, patchCredential }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const row = within(table).getByRole('row', { name: /openrouter/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Edit' }));
    expect(screen.queryByRole('combobox', { name: /model/i })).not.toBeInTheDocument();
    const modelInput = screen.getByLabelText('Model for openrouter');
    expect((modelInput as HTMLInputElement).value).toBe('gpt-5.6');
    await userEvent.clear(modelInput);
    await userEvent.type(modelInput, 'anthropic/claude-my-finetune');
    await userEvent.click(within(row).getByRole('button', { name: 'Save' }));
    expect(patchCredential).toHaveBeenCalledWith('meridian', 'openrouter', { model: 'anthropic/claude-my-finetune' }, expect.stringContaining('credential-patch:meridian:openrouter'));
    await waitFor(() => expect(listCredentials.mock.calls.length).toBeGreaterThan(1));
    // The row returns to its read view; the edit itself never touched an API key field.
    expect(within(row).queryByRole('textbox')).not.toBeInTheDocument();
  });

  test('an inline model edit can be cancelled without saving', async () => {
    const patchCredential = vi.fn(async () => credential());
    renderRoute(fakeSource({ listCredentials: async () => [credential({ model: 'gpt-5.6' })], patchCredential }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const row = within(table).getByRole('row', { name: /openrouter/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Edit' }));
    await userEvent.click(within(row).getByRole('button', { name: 'Cancel' }));
    expect(patchCredential).not.toHaveBeenCalled();
    expect(within(row).getByText('gpt-5.6')).toBeInTheDocument();
  });

  test('invalid_model on the inline edit reads as itself on that row', async () => {
    const patchCredential = vi.fn(async () => { throw new ApiError({ status: 400, code: 'invalid_model', message: 'no' }); });
    renderRoute(fakeSource({ listCredentials: async () => [credential()], patchCredential }), 'tab=keys');
    const table = await screen.findByRole('table', { name: 'Model provider keys' });
    const row = within(table).getByRole('row', { name: /openrouter/ });
    await userEvent.click(within(row).getByRole('button', { name: 'Edit' }));
    await userEvent.click(within(row).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('The model was not saved (invalid_model).')).toBeInTheDocument();
  });

  test('credential_invalid, secret_encryption_unavailable and an unlisted code each read as themselves', async () => {
    let failWith = 'credential_invalid';
    const setCredential = vi.fn(async () => { throw new ApiError({ status: 400, code: failWith, message: 'no' }); });
    renderRoute(fakeSource({ listCredentials: async () => [], setCredential }), 'tab=keys');
    const input = await screen.findByLabelText('API key');

    await userEvent.type(input, 'sk-bad');
    await userEvent.click(screen.getByRole('button', { name: 'Store key' }));
    expect(await screen.findByText('The provider rejected this key. Nothing was saved.')).toBeInTheDocument();
    expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('');

    failWith = 'secret_encryption_unavailable';
    await userEvent.type(input, 'sk-bad');
    await userEvent.click(screen.getByRole('button', { name: 'Store key' }));
    expect(await screen.findByText('This deployment cannot store model keys right now: no secret-encryption key is configured. Nothing was saved.')).toBeInTheDocument();

    failWith = 'invalid_provider';
    await userEvent.type(input, 'sk-bad');
    await userEvent.click(screen.getByRole('button', { name: 'Store key' }));
    expect(await screen.findByText('The key was not saved (invalid_provider).')).toBeInTheDocument();
  });

  test('deleting a key reports the outcome and re-reads the list', async () => {
    const deleteCredential = vi.fn(async () => {});
    const listCredentials = vi.fn(async () => [credential()]);
    renderRoute(fakeSource({ listCredentials, deleteCredential }), 'tab=keys');
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(deleteCredential).toHaveBeenCalledWith('meridian', 'openrouter', 'credential-remove:meridian:openrouter');
    await waitFor(() => expect(listCredentials.mock.calls.length).toBeGreaterThan(1));
    expect(await screen.findByText('Key removed for openrouter.')).toBeInTheDocument();
  });

  test('a member sees the rows read only: no form, no delete action, no make-preferred control', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential({ preferred: false }), credential({ provider: 'anthropic', preferred: true })] }), 'tab=keys', { role: 'member' });
    await screen.findByRole('table', { name: 'Model provider keys' });
    expect(screen.queryByLabelText('API key')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Make preferred' })).not.toBeInTheDocument();
    expect(screen.getByText(/Member access is read only here/)).toBeInTheDocument();
  });
});

describe('Organization route, GitHub App installations (contract §4.7, ADR-0034/ADR-0036)', () => {
  test('an owner sees Connect GitHub, next to the recommendation to choose All repositories', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [githubInstallation()] }), 'tab=integrations');
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeInTheDocument();
    // The recommendation Task 1 asks for: since Guidefold cannot preselect it, the copy names
    // "All repositories" (bold, its own element) inside the explanation of why.
    expect(screen.getByText('All repositories')).toBeInTheDocument();
    expect(screen.getByText(/Guidefold cannot preselect that for you/)).toBeInTheDocument();
    expect(await screen.findByText('meridian-data')).toBeInTheDocument();
  });

  test('a member sees the same installation but no button to connect one', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [githubInstallation()] }), 'tab=integrations', { role: 'member' });
    // Member-readable per contract (GET is `member`, not `owner`): the list still reads, the
    // connect action does not appear at all (never merely disabled).
    expect(await screen.findAllByText('meridian-data')).not.toHaveLength(0);
    expect(screen.queryByRole('button', { name: 'Connect GitHub' })).not.toBeInTheDocument();
    expect(screen.queryByText('All repositories')).not.toBeInTheDocument();
  });

  test('Connect GitHub starts the link with a stable per-organization key; the browser is sent to what the API returns', async () => {
    const startGitHubInstall = vi.fn(async () => ({ schema_version: 'mgmt-1', install_url: 'https://github.com/apps/guidefold/installations/new?state=s1' }));
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [], startGitHubInstall }), 'tab=integrations');
    await userEvent.click(await screen.findByRole('button', { name: 'Connect GitHub' }));
    // jsdom's window.location.assign is a non-configurable, non-writable own property and cannot
    // be spied on (same limitation as the identity-link tests above); this stops at the call that
    // decides where the browser goes, which is the boundary this test double can observe.
    await waitFor(() => expect(startGitHubInstall).toHaveBeenCalledWith('meridian', 'github-install-start:meridian'));
    expect(screen.queryByText(/could not start/)).not.toBeInTheDocument();
  });

  test('github_app_not_configured reads as a deployment problem with nothing left to click, not a retryable error', async () => {
    const startGitHubInstall = vi.fn(async () => { throw new ApiError({ status: 503, code: 'github_app_not_configured', message: 'no app' }); });
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [], startGitHubInstall }), 'tab=integrations');
    await userEvent.click(await screen.findByRole('button', { name: 'Connect GitHub' }));
    expect(await screen.findByText('No GitHub App configured on this deployment')).toBeInTheDocument();
    expect(screen.getByText(/ask whoever operates this deployment/i)).toBeInTheDocument();
    // The button itself is gone — there is nothing here for the owner to click through.
    expect(screen.queryByRole('button', { name: 'Connect GitHub' })).not.toBeInTheDocument();
    // Nor does the empty-list state get to say "Install the Guidefold GitHub App..." right under
    // a message saying this deployment cannot start an install — that would contradict it.
    expect(screen.queryByText('No GitHub App installation')).not.toBeInTheDocument();
  });

  test('a linked installation with no reconciled repositories yet reads as still syncing, never as zero', async () => {
    const syncing = githubInstallation({ repositories: [], created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z' });
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [syncing] }), 'tab=integrations');
    expect(await screen.findByText('Linked. Repositories still syncing.')).toBeInTheDocument();
    expect(screen.queryByText('GitHub reported no repositories.')).not.toBeInTheDocument();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  test('a genuinely empty repository list — confirmed by a later reconciliation write — reads as zero, not syncing', async () => {
    const confirmedEmpty = githubInstallation({ repositories: [], created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-11T00:00:00Z' });
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [confirmedEmpty] }), 'tab=integrations');
    expect(await screen.findByText('GitHub reported no repositories.')).toBeInTheDocument();
    expect(screen.queryByText('Linked. Repositories still syncing.')).not.toBeInTheDocument();
  });

  test('Disconnect is owner-only: a member reads the installation but has no control to remove it', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [githubInstallation()] }), 'tab=integrations', { role: 'member' });
    expect(await screen.findByText('meridian-data')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Disconnect' })).not.toBeInTheDocument();
    expect(screen.getByText('Owner only')).toBeInTheDocument();
  });

  test('Disconnect says plainly that the App stays installed on GitHub and must be uninstalled there too', async () => {
    const deleteGitHubInstallation = vi.fn(async () => {});
    const listGitHubInstallations = vi.fn(async () => [githubInstallation()]);
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations, deleteGitHubInstallation }), 'tab=integrations');
    await userEvent.click(await screen.findByRole('button', { name: 'Disconnect' }));
    expect(deleteGitHubInstallation).toHaveBeenCalledWith('meridian', 501, 'github-installation:meridian:501');
    expect(await screen.findByText(/App stays installed on GitHub — uninstall it there too/)).toBeInTheDocument();
    await waitFor(() => expect(listGitHubInstallations.mock.calls.length).toBeGreaterThan(1));
  });

  test('a failed disconnect is reported honestly and the installation is not claimed removed', async () => {
    const deleteGitHubInstallation = vi.fn(async () => { throw new ApiError({ status: 404, code: 'installation_not_found', message: 'gone' }); });
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [githubInstallation()], deleteGitHubInstallation }), 'tab=integrations');
    await userEvent.click(await screen.findByRole('button', { name: 'Disconnect' }));
    expect(await screen.findByText('The GitHub installation was not disconnected (installation_not_found).')).toBeInTheDocument();
  });

  test('landing back from a successful GitHub round trip shows its own message, not a generic one', async () => {
    renderRoute(fakeSource({ listMembers: async () => owners, listGitHubInstallations: async () => [] }), 'tab=integrations&github_connected=1');
    expect(await screen.findByText(/back from GitHub/)).toBeInTheDocument();
  });

});
