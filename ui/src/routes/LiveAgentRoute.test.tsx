import { describe, expect, test, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ApiLiveAgentRoute } from './LiveAgentRoute';
import { ApiError } from '../api/client';
import type { LiveRun, LiveRunDetail, LiveRunEvent, LiveRunEventPage, OrgCredential, Repo } from '../api/decoders';
import type { ApiRouteContext } from '../domain';
import type { DataSource } from '../data/source';
import { fakeSource } from '../test/fakes';

const me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' as const }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};
const credential = (over: Partial<OrgCredential> = {}): OrgCredential => ({
  provider: 'openrouter', name: 'default', last4: '9f2a', created_at: '2026-09-01T00:00:00Z', created_by: 'u1', ...over,
});
const repos: Repo[] = [{ repo_id: 'monorepo', name: null, git_host_url: null, created_at: null, created: false }];
const run = (over: Partial<LiveRun> = {}): LiveRun => ({
  run_id: 'r-1', state: 'running', prompt: 'Check auth skills for drift', provider: 'openrouter', model: 'gpt-x',
  created_by: 'u1', created_at: '2026-09-10T00:00:00Z', started_at: '2026-09-10T00:00:01Z', finished_at: null,
  counts: { targets: 1, done: 0, failed: 0, skipped: 0 }, cost: { tokens_in: 0, tokens_out: 0, usd: 0, usd_estimated: false },
  error: null, ...over,
});
const detail = (over: Partial<LiveRunDetail> = {}): LiveRunDetail => ({
  run: run(), targets: [{ repo_id: 'monorepo', state: 'running', job_id: 'j-1', findings: 0, error: null, started_at: null, finished_at: null }],
  ...over,
});
const eventPage = (over: Partial<LiveRunEventPage> = {}): LiveRunEventPage => ({ items: [], next_after: 0, done: false, ...over });
const event = (over: Partial<LiveRunEvent> = {}): LiveRunEvent => ({ seq: 1, at: '2026-09-10T00:00:02Z', repo_id: null, type: 'run.started', payload: {}, ...over });

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

describe('Live Agent route, composer', () => {
  test('an owner can start a run with the prompt, provider, model and no repository scope', async () => {
    const startLiveRun = vi.fn(async () => run());
    const { ctx } = renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => repos, listLiveRuns: async () => ({ items: [], next_cursor: null }), startLiveRun,
    }));
    await userEvent.type(await screen.findByLabelText('Prompt'), 'Check auth skills for drift');
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    await waitFor(() => expect(startLiveRun).toHaveBeenCalledWith(
      'meridian', { prompt: 'Check auth skills for drift', provider: 'openrouter', model: undefined, repos: undefined }, expect.stringContaining('live-run:'),
    ));
    expect(ctx.go).toHaveBeenCalledWith('live', { run: 'r-1' });
  });

  test('the repository scope fieldset lists the organization\'s repositories', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => repos, listLiveRuns: async () => ({ items: [], next_cursor: null }),
    }));
    const fieldset = (await screen.findByText('Repository scope')).closest('fieldset')!;
    expect(within(fieldset).getByText('monorepo')).toBeInTheDocument();
    expect(screen.getByText(/Leaving every repository unchecked runs against every repository/)).toBeInTheDocument();
  });

  test('no stored key for the selected provider replaces the Start button with a link to Model keys', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }) }));
    await userEvent.type(await screen.findByLabelText('Prompt'), 'Check auth skills for drift');
    expect(await screen.findByText(/This organization has no stored key for openrouter/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start run' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add one in Model keys' })).toHaveAttribute('href', expect.stringContaining('tab=keys'));
  });

  test('live_run_already_active, model_credential_missing and an unlisted code each read as themselves', async () => {
    let failWith = 'live_run_already_active';
    const startLiveRun = vi.fn(async () => { throw new ApiError({ status: 409, code: failWith, message: 'no' }); });
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }), startLiveRun }));
    const prompt = await screen.findByLabelText('Prompt');
    await userEvent.type(prompt, 'Check auth skills for drift');
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    expect(await screen.findByText(/This organization already has a run in progress/)).toBeInTheDocument();

    failWith = 'model_credential_missing';
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    expect(await screen.findByText(/has no stored key for openrouter any more/)).toBeInTheDocument();

    failWith = 'some_other_code';
    await userEvent.click(screen.getByRole('button', { name: 'Start run' }));
    expect(await screen.findByText('The run was not started (some_other_code).')).toBeInTheDocument();
  });

  test('a member watches without a composer, but recent runs are still readable', async () => {
    const listLiveRuns = vi.fn(async () => ({ items: [run({ run_id: 'r-2', state: 'succeeded' })], next_cursor: null }));
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns }), '', { role: 'member' });
    expect(await screen.findByText(/Member access is read only here/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Prompt')).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /r-2/ })).toBeInTheDocument();
  });

  test('no runs yet is an honest empty state, not an empty table', async () => {
    renderRoute(fakeSource({ listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }) }));
    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
  });
});

describe('Live Agent route, an open run', () => {
  test('the transcript fills by polling with the after cursor and stops once the page says done', async () => {
    vi.useFakeTimers();
    try {
      const getLiveRun = vi.fn(async () => detail());
      const getLiveRunEvents = vi.fn(async (_org: string, _id: string, after?: number) =>
        !after ? eventPage({ items: [event({ seq: 1, type: 'run.started' })], next_after: 1 }) : eventPage({ next_after: 1, done: true }));
      renderRoute(fakeSource({
        listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
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
        listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
        getLiveRun: async () => detail(), getLiveRunEvents,
      }), 'run=r-1');
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(1));
      await vi.advanceTimersByTimeAsync(1000);
      await vi.waitFor(() => expect(getLiveRunEvents).toHaveBeenCalledTimes(2));
      expect(screen.queryByText(/Could not read this view/)).not.toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });

  test('model.delta accumulates in the transcript and finding is shown outside it', async () => {
    const getLiveRunEvents = vi.fn(async () => eventPage({
      items: [
        event({ seq: 1, type: 'run.started' }),
        event({ seq: 2, type: 'model.delta', repo_id: 'monorepo', payload: { text: 'Reading SKILL.md files.' } }),
        event({ seq: 3, type: 'finding', repo_id: 'monorepo', payload: { path: 'a/SKILL.md', summary: 'Stale scope reference', severity: 'warn' } }),
      ],
      next_after: 3, done: true,
    }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents,
    }), 'run=r-1');
    const transcript = await screen.findByText('Run started.');
    expect(transcript.closest('pre')).toHaveTextContent('Reading SKILL.md files.');
    expect(transcript.closest('pre')).not.toHaveTextContent('Stale scope reference');
    const findingsPanel = (await screen.findByRole('heading', { name: 'Findings' })).closest('section')!;
    expect(within(findingsPanel).getByText(/Stale scope reference/)).toBeInTheDocument();
  });

  test('a truncated log says so instead of reading as a quiet agent', async () => {
    const getLiveRunEvents = vi.fn(async () => eventPage({
      items: [event({ seq: 1, type: 'error', payload: { reason: 'live_run_log_truncated' } })],
      next_after: 1, done: true,
    }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents,
    }), 'run=r-1');
    expect(await screen.findByText(/reached its 20,000-event ceiling and was truncated/)).toBeInTheDocument();
  });

  test('a repository skipped for a missing GitHub App installation says so on its row', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ targets: [{ repo_id: 'no-app', state: 'skipped', job_id: null, findings: 0, error: 'github_app_not_configured', started_at: null, finished_at: null }] }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    const row = (await screen.findByText('no-app')).closest('tr')!;
    expect(within(row).getByText('skipped')).toBeInTheDocument();
    expect(within(row).getByText('No GitHub App installed for this repository.')).toBeInTheDocument();
  });

  test('partial says how many repositories failed or were skipped', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail({ run: run({ state: 'partial', counts: { targets: 3, done: 1, failed: 1, skipped: 1 } }) }),
      getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1');
    expect(await screen.findByText('1 of 3 repositories failed and 1 were skipped.')).toBeInTheDocument();
  });

  test('an owner can cancel a running run; a member sees no cancel action', async () => {
    const cancelLiveRun = vi.fn(async () => run({ state: 'cancelled' }));
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents: async () => eventPage({ done: true }), cancelLiveRun,
    }), 'run=r-1');
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel run' }));
    expect(cancelLiveRun).toHaveBeenCalledWith('meridian', 'r-1', 'live-run-cancel:meridian:r-1');
    expect(await screen.findByText('Run cancelled.')).toBeInTheDocument();
  });

  test('a member watching an active run has no cancel button', async () => {
    renderRoute(fakeSource({
      listCredentials: async () => [credential()], listRepos: async () => [], listLiveRuns: async () => ({ items: [], next_cursor: null }),
      getLiveRun: async () => detail(), getLiveRunEvents: async () => eventPage({ done: true }),
    }), 'run=r-1', { role: 'member' });
    await screen.findByText('Run r-1');
    expect(screen.queryByRole('button', { name: 'Cancel run' })).not.toBeInTheDocument();
  });
});
