import { describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ApiLiveAgentRoute } from './LiveAgentRoute';
import { ApiError } from '../api/client';
import type { LiveRun, LiveRunDetail, LiveRunEvent, LiveRunEventPage, OrgCredential } from '../api/decoders';
import type { ApiRouteContext } from '../domain';
import type { DataSource } from '../data/source';
import { fakeSource } from '../test/fakes';

const me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' as const }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};
const credential = (over: Partial<OrgCredential> = {}): OrgCredential => ({
  provider: 'openrouter', name: 'default', last4: '9f2a', model: 'gpt-5.6', preferred: true,
  created_at: '2026-09-01T00:00:00Z', created_by: 'u1', ...over,
});
const run = (over: Partial<LiveRun> = {}): LiveRun => ({
  run_id: 'r-1', state: 'running', provider: 'openrouter', model: 'gpt-5.6',
  created_by: 'u1', created_at: '2026-09-10T00:00:00Z', started_at: '2026-09-10T00:00:01Z', finished_at: null,
  counts: { targets: 1, done: 0, failed: 0, skipped: 0 }, summary: { skills_indexed: 0, proposals_created: 0 },
  cost: { tokens_in: 0, tokens_out: 0, usd: 0, usd_estimated: false },
  error: null, ...over,
});
const detail = (over: Partial<LiveRunDetail> = {}): LiveRunDetail => ({
  run: run(),
  targets: [{ repo_id: 'monorepo', state: 'running', job_id: 'j-1', phase: 'parse', skills: 0, proposals: 0, error: null, started_at: null, finished_at: null }],
  ...over,
});
const eventPage = (over: Partial<LiveRunEventPage> = {}): LiveRunEventPage => ({ items: [], next_after: 0, done: false, ...over });
const event = (over: Partial<LiveRunEvent> = {}): LiveRunEvent => ({ seq: 1, at: '2026-09-10T00:00:02Z', repo_id: null, type: 'run.started', payload: { text: 'Run started.' }, ...over });

function renderRoute(source: DataSource, search = '', over: Partial<ApiRouteContext> = {}) {
  const params = new URLSearchParams(search);
  const ctx: ApiRouteContext = {
    source, access: { status: 'confirmed', me, checkedAt: 1 }, me, org: 'meridian', repo: 'monorepo',
    role: 'owner', params, view: 'live',
    href: (view, changes = {}) => '/' + view + '?' + new URLSearchParams(Object.entries(changes).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, String(value)])).toString(),
    go: vi.fn(),
    ...over,
  };
  return { ...render(<MemoryRouter><ApiLiveAgentRoute ctx={ctx} /></MemoryRouter>), ctx };
}

describe('Live Agent route, the button', () => {
  test('an owner sees the lead sentence and a single button with no fields to fill in', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }) }));
    expect(await screen.findByText(/reads every connected repository, refreshes the skill library/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start run' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Prompt')).not.toBeInTheDocument();
    expect(screen.queryByText('Repository scope')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Provider')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Model')).not.toBeInTheDocument();
  });

  test('pressing the button starts a run with an empty body and a fresh idempotency key each time', async () => {
    const startLiveRun = vi.fn(async (_org: string, _idempotencyKey: string) => run());
    const { ctx } = renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }), startLiveRun,
    }));
    await userEvent.click(await screen.findByRole('button', { name: 'Start run' }));
    await waitFor(() => expect(startLiveRun).toHaveBeenCalledWith('meridian', expect.stringContaining('live-run:meridian:')));
    expect(ctx.go).toHaveBeenCalledWith('live', { run: 'r-1' });

    // A second press must not reuse the first key: the body never varies, so a stable key would
    // make the API replay the first run's stored response instead of starting a new one (§3).
    await userEvent.click(await screen.findByRole('button', { name: 'Start run' }));
    await waitFor(() => expect(startLiveRun).toHaveBeenCalledTimes(2));
    const [, firstKey] = startLiveRun.mock.calls[0];
    const [, secondKey] = startLiveRun.mock.calls[1];
    expect(firstKey).not.toBe(secondKey);
  });

  test('no stored model key replaces the button with a link to Model keys', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }) }));
    expect(await screen.findByText(/This organization has no stored model key/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start run' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add one in Model keys' })).toHaveAttribute('href', expect.stringContaining('tab=keys'));
  });

  test('live_run_already_active, model_credential_missing and an unlisted code each read as themselves', async () => {
    let failWith = 'live_run_already_active';
    const startLiveRun = vi.fn(async () => { throw new ApiError({ status: 409, code: failWith, message: 'no' }); });
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }), startLiveRun }));
    await userEvent.click(await screen.findByRole('button', { name: 'Start run' }));
    expect(await screen.findByText(/This organization already has a run in progress/)).toBeInTheDocument();

    failWith = 'model_credential_missing';
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    expect(await screen.findByText(/has no stored model key any more/)).toBeInTheDocument();

    failWith = 'some_other_code';
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    expect(await screen.findByText('The run was not started (some_other_code).')).toBeInTheDocument();
  });

  test('a member watches without a button, but recent runs are still readable', async () => {
    const listLiveRuns = vi.fn(async () => ({ items: [run({ run_id: 'r-2', state: 'succeeded', summary: { skills_indexed: 5, proposals_created: 2 } })], next_cursor: null }));
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listLiveRuns }), '', { role: 'member' });
    expect(await screen.findByText(/Member access is read only here/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start run' })).not.toBeInTheDocument();
    const link = await screen.findByRole('link', { name: /r-2/ });
    expect(link).toBeInTheDocument();
    const row = link.closest('tr')!;
    expect(within(row).getByText('5')).toBeInTheDocument();
    expect(within(row).getByText('2')).toBeInTheDocument();
  });

  test('no runs yet is an honest empty state, not an empty table', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }) }));
    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
  });
});

describe('Live Agent route, an open run', () => {
  test('the event log fills by polling with the after cursor and stops once the page says done', async () => {
    vi.useFakeTimers();
    try {
      const getLiveRun = vi.fn(async () => detail());
      const getLiveRunEvents = vi.fn(async (_org: string, _id: string, after?: number) =>
        !after ? eventPage({ items: [event({ seq: 1, type: 'run.started', payload: { text: 'Run started.' } })], next_after: 1 }) : eventPage({ next_after: 1, done: true }));
      renderRoute(fakeSource({
        listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
        getLiveRun, getLiveRunEvents,
      }), 'run=r-1');
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(1));
      expect(getLiveRunEvents).toHaveBeenCalledWith('meridian', 'r-1', 0);
      await vi.advanceTimersByTimeAsync(1000);
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(2));
      expect(getLiveRunEvents).toHaveBeenLastCalledWith('meridian', 'r-1', 1);
      await vi.advanceTimersByTimeAsync(5000);
      expect(getLiveRunEvents).toHaveBeenCalledTimes(2);
      expect(getLiveRun).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });

  test('an empty page is normal: it neither stops the poll nor renders as an error', async () => {
    vi.useFakeTimers();
    try {
      const getLiveRunEvents = vi.fn(async () => eventPage());
      renderRoute(fakeSource({
        listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
        getLiveRun: async () => detail(), getLiveRunEvents,
      }), 'run=r-1');
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(1));
      await vi.advanceTimersByTimeAsync(1000);
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(2));
      expect(screen.queryByText(/Could not read this view/)).not.toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });

  test('every event line is the server\'s own payload.text, printed verbatim', async () => {
    const getLiveRunEvents = vi.fn(async () => eventPage({
      items: [
        event({ seq: 1, type: 'run.started', payload: { text: 'Run started.' } }),
        event({ seq: 2, type: 'repo.parsed', repo_id: 'monorepo', payload: { text: 'monorepo: parsed 4 skills.', skills: 4 } }),
      ],
      next_after: 2, done: true,
    }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents,
    }), 'run=r-1');
    expect(await screen.findByText('Run started.')).toBeInTheDocument();
    expect(await screen.findByText('monorepo: parsed 4 skills.')).toBeInTheDocument();
  });

  test('the per-repository table shows phase, skills and proposals', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ targets: [{ repo_id: 'monorepo', state: 'running', job_id: 'j-1', phase: 'propose', skills: 6, proposals: 2, error: null, started_at: null, finished_at: null }] }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    const row = (await screen.findByText('monorepo')).closest('tr')!;
    expect(within(row).getByText('Proposing')).toBeInTheDocument();
    expect(within(row).getByText('6')).toBeInTheDocument();
    expect(within(row).getByText('2')).toBeInTheDocument();
  });

  test('a repository skipped for a missing GitHub App installation says so on its row', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ targets: [{ repo_id: 'no-app', state: 'skipped', job_id: null, phase: 'fetch', skills: 0, proposals: 0, error: 'github_app_not_configured', started_at: null, finished_at: null }] }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    const row = (await screen.findByText('no-app')).closest('tr')!;
    expect(within(row).getByText('skipped')).toBeInTheDocument();
    expect(within(row).getByText('No GitHub App installed for this repository.')).toBeInTheDocument();
  });

  test('partial says how many repositories failed or were skipped, without reading as success', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ run: run({ state: 'partial', finished_at: '2026-09-10T00:05:00Z', counts: { targets: 3, done: 1, failed: 1, skipped: 1 }, summary: { skills_indexed: 2, proposals_created: 0 } }) }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    expect(await screen.findByText('1 of 3 repositories failed and 1 were skipped.')).toBeInTheDocument();
    expect(screen.getByText('partial')).toBeInTheDocument();
  });

  test('cancelled and failed each read as themselves, never as success', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ run: run({ state: 'cancelled', finished_at: '2026-09-10T00:05:00Z' }) }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    expect(await screen.findByText(/This run was cancelled before it finished/)).toBeInTheDocument();
  });

  test('a run that indexed nothing and proposed nothing says so, with no proposals link and no green tick', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ run: run({ state: 'succeeded', finished_at: '2026-09-10T00:05:00Z', summary: { skills_indexed: 0, proposals_created: 0 } }) }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    expect(await screen.findByText(/This run indexed no skills and created no consolidation proposals/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Review proposals' })).not.toBeInTheDocument();
  });

  test('a finished run with output links into Proposals scoped to consolidation', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ run: run({ state: 'succeeded', finished_at: '2026-09-10T00:05:00Z', summary: { skills_indexed: 7, proposals_created: 3 } }) }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    const summaryPanel = (await screen.findByRole('heading', { name: 'What this run left behind' })).closest('section')!;
    expect(within(summaryPanel).getByText('7')).toBeInTheDocument();
    expect(within(summaryPanel).getByText('3')).toBeInTheDocument();
    const link = within(summaryPanel).getByRole('link', { name: 'Review proposals' });
    expect(link).toHaveAttribute('href', expect.stringContaining('kind=consolidation'));
  });

  test('an owner can cancel a running run; a member sees no cancel action', async () => {
    const cancelLiveRun = vi.fn(async () => run({ state: 'cancelled' }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents: async () => eventPage({ done: true }), cancelLiveRun,
    }), 'run=r-1');
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel run' }));
    expect(cancelLiveRun).toHaveBeenCalledWith('meridian', 'r-1', 'live-run-cancel:meridian:r-1');
    expect(await screen.findByText('Run cancelled.')).toBeInTheDocument();
  });

  test('a member watching an active run has no cancel button', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1', { role: 'member' });
    await screen.findByText('Run r-1');
    expect(screen.queryByRole('button', { name: 'Cancel run' })).not.toBeInTheDocument();
  });
});
