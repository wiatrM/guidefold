import { beforeEach, describe, expect, test, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiUsageRoute } from './ReviewRoutes';
import { ApiError } from '../api/client';
import type { ExecutionMetrics, Usage, UsageSkill } from '../api/decoders';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';

const noMetrics: ExecutionMetrics = {
  tasks_started: 0, tasks_finished: 0, tasks_succeeded: 0, tasks_failed: 0, tasks_unknown: 0,
  harness_errors: 0, search_requests: 0, search_results: 0, search_errors: 0, use_requests: 0,
  ask_count: 0, input_tokens: 0, output_tokens: 0, tool_calls: 0, latency_ms: 0,
  latency_samples: 0, tasks_observed: false, cost_observed: false,
};
const empty: Usage = {
  window: { from: '2026-08-31T00:00:00Z', to: '2026-09-06T00:00:00Z', watermark: '2026-09-06T00:00:00Z' },
  coverage: { events_received: 0, dropped_reported: 0, oldest_lag_s: null, task_ids_present: false },
  totals: { exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null, metrics: noMetrics },
  skills: [], queue: [], health: null,
};
const report = (over: Partial<Usage> = {}): Usage => ({
  ...empty,
  coverage: { events_received: 420, dropped_reported: 0, oldest_lag_s: 12, task_ids_present: true },
  totals: { exposures: 120, loads_verified: 44, context_loaded: 40, context_unknown: 4, use_reported: 11, use_observed: 7, use_episodes: 9, exposures_expanded: 38, loads_unlinked: 6, feedback: null, metrics: noMetrics },
  skills: [
    { skill_id: 'urn:a', revision: 'rev-a', card_revision: 'card-a', content_sha256: 'sha-a', scope: 'atlas.identity', owner: 'identity-team', harness: 'claude', exposures: 60, loads_verified: 30, context_loaded: 28, context_unknown: 2, use_reported: 8, use_observed: 5, use_episodes: 6, exposures_expanded: 26, loads_unlinked: 4, feedback: null, helped_ratio: { numerator: 21, denominator: 30, small_sample: false }, zero_loads: false },
    { skill_id: 'urn:b', revision: 'rev-b', card_revision: null, content_sha256: null, scope: 'forge.pipelines', owner: null, harness: null, exposures: 40, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0, feedback: null, helped_ratio: { numerator: 2, denominator: 3, small_sample: true }, zero_loads: true },
    { skill_id: 'urn:c', revision: null, card_revision: null, content_sha256: null, scope: null, owner: null, harness: null, exposures: 20, loads_verified: 14, context_loaded: 12, context_unknown: 2, use_reported: 3, use_observed: 2, use_episodes: 2, exposures_expanded: 12, loads_unlinked: 2, feedback: null, helped_ratio: null, zero_loads: false },
  ],
  queue: [{
    item_id: 'q-1', skill_id: 'urn:b', revision: 'rev-b', reason: 'zero_loads', since: '2026-09-01T00:00:00Z',
    evidence: { exposures: 40, loads: 0 }, decision: null,
  }],
  health: { adapters: [{ harness: 'claude', adapter_version: '0.4.1', capabilities: ['search', 'use'], last_seen_at: '2026-09-06T09:00:00Z', lag_s: 3, dropped: 0 }] },
  ...over,
});

beforeEach(() => {
  window.localStorage.removeItem('guidefold.notifications.v1');
});

describe('Usage route, hosted API, six states', () => {
  test('Empty: no events read as No observations, never a zero rate', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => empty }));
    expect((await screen.findAllByText('No observations')).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('Top skills')).not.toBeInTheDocument();
    const scorecards = within(await screen.findByRole('region', { name: 'Decision scorecards' }));
    expect(scorecards.getAllByText('Unknown')).toHaveLength(4);
  });

  test('decision scorecards make task, safety, retrieval and cost signals readable', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ totals: {
      ...report().totals,
      metrics: {
        ...noMetrics,
        tasks_observed: true, tasks_finished: 10, tasks_succeeded: 8, tasks_failed: 1, tasks_unknown: 1,
        search_requests: 14, search_results: 12, search_errors: 2, use_requests: 6, ask_count: 2,
        harness_errors: 1, input_tokens: 1200, output_tokens: 500, tool_calls: 9, cost_observed: true,
        latency_ms: 900, latency_samples: 3,
      },
    } }) }));
    const scorecards = within(await screen.findByRole('region', { name: 'Decision scorecards' }));
    expect(scorecards.getByText('8 / 10')).toBeInTheDocument();
    expect(scorecards.getByText('2 ASK')).toBeInTheDocument();
    expect(scorecards.getByText('14 · 6')).toBeInTheDocument();
    expect(scorecards.getByText('1,700 tok · 300 ms avg')).toBeInTheDocument();
    expect(scorecards.getByText(/To sygnał kierunkowy/)).toBeInTheDocument();
  });

  test('scorecards keep unmeasured tokens Unknown when only latency is observed', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ totals: {
      ...report().totals,
      metrics: { ...noMetrics, latency_ms: 600, latency_samples: 2 },
    } }) }));
    const scorecards = within(await screen.findByRole('region', { name: 'Decision scorecards' }));
    expect(scorecards.getByText('Unknown tokens · 300 ms avg')).toBeInTheDocument();
    expect(scorecards.getByText(/No token measurement in this window/)).toBeInTheDocument();
  });

  test('Loading: no number is shown before the report arrives', () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: () => new Promise(() => {}) }));
    expect(screen.getByText('Reading the usage report')).toBeInTheDocument();
  });

  test('Partial: dropped events make every count a lower bound', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ coverage: { events_received: 100, dropped_reported: 9, oldest_lag_s: 60, task_ids_present: true } }) }));
    expect(await screen.findByText(/reported 9 dropped events/)).toBeInTheDocument();
  });

  test('Error: a failed report is not a zero result', async () => {
    let fail = true;
    const getUsage = vi.fn(async () => {
      if (fail) throw new ApiError({ status: 503, code: 'database_unavailable', message: 'no' });
      return report();
    });
    renderApi(ApiUsageRoute, fakeSource({ getUsage }));
    const retry = await screen.findByRole('button', { name: 'Retry this report' });
    expect(screen.queryByText('No observations')).not.toBeInTheDocument();
    fail = false;
    await userEvent.click(retry);
    // The ranking, the chart and the "Per skill" table all name the skill: assert the table row.
    const perSkill = await screen.findByRole('table', { name: 'Delivery and outcome per skill' });
    expect(within(perSkill).getByRole('link', { name: 'urn:a' })).toBeInTheDocument();
  });

  test('Degraded: an unconfirmed membership blocks the queue decision', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }), '', { access: { status: 'offline', me: null, checkedAt: 1 } });
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record decision' })).toBeDisabled();
  });

  test('Restricted: a denial shows no aggregate', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'no' }); } }));
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('urn:a')).not.toBeInTheDocument();
  });
});

describe('Usage route, queue, denominators and export', () => {
  test('the review queue comes first with its reason, revision and evidence', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    expect((await screen.findAllByText('Published but never loaded')).length).toBeGreaterThan(0);
    expect(screen.getByText('exposures=40 loads=0')).toBeInTheDocument();
    expect(screen.getByText('Revision rev-b')).toBeInTheDocument();
  });

  test('an owner decision carries an action and a reason', async () => {
    const decideQueueItem = vi.fn(async () => undefined);
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report(), decideQueueItem }));
    await userEvent.selectOptions(await screen.findByLabelText('Owner decision'), 'fixed_in_git');
    await userEvent.type(screen.getByLabelText('Reason'), 'Removed the stale skill.');
    await userEvent.click(screen.getByRole('button', { name: 'Record decision' }));
    await waitFor(() => expect(decideQueueItem).toHaveBeenCalledWith(
      { org: 'meridian', repo: 'monorepo' }, 'q-1',
      { action: 'fixed_in_git', reason: 'Removed the stale skill.' },
      expect.stringMatching(/^queue:[0-9a-f]{8}$/),
    ));
  });

  test('a decision without a reason is refused before any request', async () => {
    const decideQueueItem = vi.fn(async () => undefined);
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report(), decideQueueItem }));
    await userEvent.click(await screen.findByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText('Say what you did. The reason is stored with the decision.')).toBeInTheDocument();
    expect(decideQueueItem).not.toHaveBeenCalled();
  });

  test('helped shows a rate, counts for a small sample and Unknown without a denominator', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    const perSkill = within(await screen.findByRole('table', { name: 'Delivery and outcome per skill' }));
    expect(perSkill.getByText('21 of 30 (70%)')).toBeInTheDocument();
    expect(perSkill.getByText('2 of 3')).toBeInTheDocument();
    expect(perSkill.getByText(/Small sample; no rate is reported below 20 assessments./)).toBeInTheDocument();
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
    expect(perSkill.getByText('No eligible assessment')).toBeInTheDocument();
  });

  test('filters round-trip through the URL', async () => {
    const seen: unknown[] = [];
    const { ctx } = renderApi(ApiUsageRoute, fakeSource({ getUsage: async (_target, query) => { seen.push(query); return report(); } }), 'window=7d&scope=atlas.identity&skill=urn:a&revision=rev-a&harness=claude');
    expect(await screen.findByLabelText('Window')).toHaveValue('7d');
    expect(screen.getByLabelText('Window').tagName).toBe('SELECT');
    expect(seen[0]).toMatchObject({ window: '7d', scope: 'atlas.identity', skillId: 'urn:a', revision: 'rev-a', harness: 'claude' });
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    expect(ctx.go).toHaveBeenCalledWith('usage', expect.objectContaining({ window: '7d', harness: 'claude' }));
  });

  test('a row links to the skill with its scope and revision', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }), 'scope=atlas.identity');
    const perSkill = await screen.findByRole('table', { name: 'Delivery and outcome per skill' });
    const link = within(perSkill).getByRole('link', { name: 'urn:a' });
    expect(link).toHaveAttribute('href', expect.stringContaining('skill=urn%3Aa'));
    expect(link).toHaveAttribute('href', expect.stringContaining('revision=rev-a'));
    expect(link).toHaveAttribute('href', expect.stringContaining('scope=atlas.identity'));
  });

  test('the export asks for the chosen format and window', async () => {
    const exportUsage = vi.fn(async () => 'skill_id,exposures\nurn:a,60\n');
    URL.createObjectURL = vi.fn(() => 'blob:test') as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as typeof URL.revokeObjectURL;
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report(), exportUsage }), 'window=30d');
    await userEvent.click(await screen.findByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(exportUsage).toHaveBeenCalledWith({ org: 'meridian', repo: 'monorepo' }, { format: 'csv', window: '30d' }));
    expect(await screen.findByText(/Downloaded the CSV report/)).toBeInTheDocument();
  });

  test('an absent adapter row is Unknown, not healthy', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ health: null }) }));
    expect(await screen.findByText(/An absent row is Unknown, not healthy/)).toBeInTheDocument();
  });

  test('a member sees the notice and cannot record a queue decision', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }), '', { role: 'member' });
    expect(await screen.findByText('Member access is read only here. Import and organization changes require an owner.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record decision' })).toBeDisabled();
  });

  test('owner can opt in to deduplicated in-app alerts and mute them', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    const toggle = await screen.findByRole('checkbox', { name: 'Show in-app alerts for new owner queue items' });
    expect(screen.getByText('Alerts are off until an owner opts in.')).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(await screen.findByRole('list', { name: 'Open Guidefold notifications' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Published but never loaded: urn:b' })).toHaveAttribute('href', '#needs-review');
    expect(screen.getByRole('button', { name: 'Mute alerts for 24 hours' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Mute alerts for 24 hours' }));
    expect(await screen.findByText(/Alerts are muted until/)).toBeInTheDocument();
  });

  test('dismissed queue items stay hidden until their item id changes', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    await userEvent.click(await screen.findByRole('checkbox', { name: 'Show in-app alerts for new owner queue items' }));
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(await screen.findByText('No new actionable problems.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Published but never loaded: urn:b' })).not.toBeInTheDocument();
  });
});

describe('Usage route, funnel, ranking and teams', () => {
  test('the funnel names every step with its count and never calls a SEARCH response an exposure', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    const funnel = within(await screen.findByRole('region', { name: 'From delivery to value' }));
    expect(funnel.getByText('Exposed')).toBeInTheDocument();
    expect(funnel.getByText(/A SEARCH response alone is not an exposure/)).toBeInTheDocument();
    expect(funnel.getByText('44 of 120 (37%) of exposed cards had a verified body load')).toBeInTheDocument();
    expect(funnel.getByText('9 task-linked episodes; an HTTP 200 on USE is neither')).toBeInTheDocument();
    // No feedback at all: the Helped step is Unknown, never 0%.
    expect(funnel.getByText('No assessment recorded; not 0%')).toBeInTheDocument();
    expect(funnel.queryByText('0%')).not.toBeInTheDocument();
  });

  test('feedback recorded without any adapter event still counts as an observation', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => ({
      ...empty,
      totals: { ...empty.totals, feedback: { helped: 3, hindered: 1, mixed: 0, not_applicable: 0, unknown: 0, n: 4 } },
      skills: [{ ...report().skills[0], exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0, use_reported: 0, use_observed: 0, use_episodes: 0, feedback: { helped: 3, hindered: 1, mixed: 0, not_applicable: 0, unknown: 0, n: 4 }, helped_ratio: { numerator: 3, denominator: 4, small_sample: true }, zero_loads: true }],
    }) }));
    const funnel = within(await screen.findByRole('region', { name: 'From delivery to value' }));
    expect(funnel.getByText('Helped')).toBeInTheDocument();
    expect(funnel.getByText('3 of 4')).toBeInTheDocument();
    expect(screen.getByText('No verified load in this window')).toBeInTheDocument();
    expect(screen.queryByText('Exposed but never loaded')).not.toBeInTheDocument();
  });

  test('feedback coverage is named only when task identifiers exist', async () => {
    const withFeedback = () => report({ totals: { ...report().totals, feedback: { helped: 15, hindered: 5, mixed: 0, not_applicable: 0, unknown: 0, n: 20 } } });
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => withFeedback() }));
    expect(await screen.findByText('20 assessed of 9 applied episodes; helped over helped plus hindered')).toBeInTheDocument();
    expect(screen.getByText('15 of 20 (75%)')).toBeInTheDocument();
  });

  test('the ranking lists only skills at the 20-assessment floor, ordered by helped share', async () => {
    const skills = report().skills;
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ skills: [
      { ...skills[2], skill_id: 'urn:c', feedback: { helped: 18, hindered: 2, mixed: 0, not_applicable: 0, unknown: 0, n: 20 }, helped_ratio: { numerator: 18, denominator: 20, small_sample: false } },
      skills[0], // 21 of 30 (70%)
      skills[1], // 2 of 3, small sample: unranked
    ] }) }));
    const table = (await screen.findByRole('table', { name: 'Skills ranked by helped share' }));
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByRole('link', { name: 'urn:c' })).toBeInTheDocument();
    expect(within(rows[0]).getByText('18 of 20 (90%)')).toBeInTheDocument();
    expect(within(rows[1]).getByRole('link', { name: 'urn:a' })).toBeInTheDocument();
    expect(within(table).queryByText('urn:b')).not.toBeInTheDocument();
    expect(screen.getByText(/1 skill has assessments below the 20 floor and no rank/)).toBeInTheDocument();
  });

  test('without any skill at the floor the ranking says so instead of ranking small samples', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report({ skills: report().skills.slice(1) }) }));
    expect(await screen.findByText('No rank yet')).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Skills ranked by helped share' })).not.toBeInTheDocument();
  });

  test('the team view groups rows by scope with owner, sums and attention count', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    const table = await screen.findByRole('table', { name: 'Delivery and feedback per scope' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(3); // atlas.identity, forge.pipelines, no scope
    expect(within(rows[0]).getByText('atlas.identity')).toBeInTheDocument();
    expect(within(rows[0]).getByText('identity-team')).toBeInTheDocument();
    expect(within(rows[0]).getByText('None observed')).toBeInTheDocument();
    // forge.pipelines: one skill exposed 40 times and never loaded, so attention is 1.
    expect(within(rows[1]).getByText('forge.pipelines')).toBeInTheDocument();
    expect(within(rows[1]).getAllByText('1')).toHaveLength(2); // one skill, one needing attention
    expect(within(rows[1]).getByText('No helped or hindered assessment')).toBeInTheDocument();
    expect(within(rows[2]).getByText('No scope in catalog')).toBeInTheDocument();
  });
});

describe('Usage route, delivery and feedback charts', () => {
  test('zero totals show the text empty state, never a chart of zeros', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => empty }));
    await screen.findAllByText('No observations');
    // Scoped to the chart landmarks, not `svg` in general: every Panel icon is also an SVG.
    expect(screen.queryByRole('group', { name: /Exposures and verified loads per skill/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /Feedback verdicts/ })).not.toBeInTheDocument();
  });

  test('non-zero totals render the delivery bars and feedback proportions with real counts', async () => {
    renderApi(ApiUsageRoute, fakeSource({
      getUsage: async () => report({
        totals: { ...report().totals, feedback: { helped: 12, hindered: 4, mixed: 2, not_applicable: 0, unknown: 0, n: 18 } },
      }),
    }));
    const deliveryChart = await screen.findByRole('group', { name: /Exposures and verified loads per skill/ });
    // Delivery chart: one row per skill, exact counts as text next to the bar.
    expect(await screen.findByText('30 of 60 verified')).toBeInTheDocument();
    expect(screen.getByText('14 of 20 verified')).toBeInTheDocument();
    expect(screen.getByText('0 of 40 verified')).toBeInTheDocument();
    expect(deliveryChart.querySelector('[data-spectrum-chart="registry-frame"]')).toBeInTheDocument();
    // Feedback chart: real counts in the legend, small-sample honesty preserved (18 < 20).
    const feedbackChart = screen.getByRole('group', { name: /Feedback verdicts/ });
    expect(feedbackChart.querySelector('[data-spectrum-chart="registry-frame"]')).toBeInTheDocument();
    const feedbackSection = feedbackChart.closest('div')!;
    expect(within(feedbackSection).getByText('Helped')).toBeInTheDocument();
    expect(within(feedbackSection).getByText('Hindered')).toBeInTheDocument();
    expect(within(feedbackSection).getByText('18 assessments; no rate is reported below 20.')).toBeInTheDocument();
  });
  test('context chart keeps confirmed and unknown outcomes distinct', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => report() }));
    const chart = await screen.findByRole('group', { name: /Verified loads split into confirmed and unknown context outcome/ });
    expect(within(chart).getByText('28 confirmed · 2 unknown of 30')).toBeInTheDocument();
    expect(within(chart).getByText('12 confirmed · 2 unknown of 14')).toBeInTheDocument();
    expect(within(chart).queryByText('0 confirmed')).not.toBeInTheDocument();
    expect(chart.textContent).toContain('it is not a failure.');
  });

});

// ---------------------------------------------------------------------------
// Skill health: four gates, a recommendation, a ranking and a per-skill funnel (domain/skillHealth).
// ---------------------------------------------------------------------------

const healthy = (over: Partial<UsageSkill> & { skill_id: string }): UsageSkill => ({
  revision: 'rev', card_revision: null, content_sha256: null, scope: 'atlas.identity', owner: 'identity-team', harness: 'claude',
  exposures: 50, loads_verified: 30, context_loaded: 30, context_unknown: 0, use_reported: 10, use_observed: 10, use_episodes: 30,
  exposures_expanded: 30, loads_unlinked: 0, feedback: null,
  helped_ratio: { numerator: 24, denominator: 30, small_sample: false }, zero_loads: false,
  ...over,
});
const healthSkills: UsageSkill[] = [
  healthy({ skill_id: 'urn:promote' }),
  healthy({ skill_id: 'urn:keep-partial', exposures_expanded: 10, loads_verified: 14, loads_unlinked: 4 }),
  healthy({ skill_id: 'urn:review-neg', helped_ratio: { numerator: 10, denominator: 25, small_sample: false } }),
  healthy({ skill_id: 'urn:review-queue' }),
  healthy({ skill_id: 'urn:small-high', helped_ratio: { numerator: 5, denominator: 5, small_sample: true } }),
  healthy({ skill_id: 'urn:archive', exposures: 0, exposures_expanded: 0, loads_verified: 0, context_loaded: 0, use_reported: 0, use_observed: 0, use_episodes: 0, helped_ratio: null, zero_loads: true }),
];
const healthReport = (over: Partial<Usage> = {}) => report({
  skills: healthSkills,
  queue: [
    { item_id: 'q-drift', skill_id: 'urn:review-queue', revision: 'rev', reason: 'source_changed', since: null, evidence: null, decision: null },
    // A decided item no longer asks anything: it must not pull urn:promote into review.
    { item_id: 'q-done', skill_id: 'urn:promote', revision: 'rev', reason: 'zero_loads', since: null, evidence: null, decision: { action: 'reviewed', reason: 'Checked', at: null } },
  ],
  ...over,
});
async function healthRows() {
  const table = await screen.findByRole('table', { name: 'Skill health per skill' });
  const rows = within(table).getAllByRole('row').slice(1);
  const byId = (id: string) => rows.find(row => within(row).queryByRole('link', { name: id }))!;
  return { table, rows, byId };
}

describe('Usage route, skill health gates', () => {
  test('each gate is a labelled badge with its reason; colour is never alone', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    const row = within(byId('urn:promote'));
    expect(row.getByText('50 exposures')).toBeInTheDocument();
    expect(row.getByText('30 of 50 (60%)')).toBeInTheDocument();
    expect(row.getByText('At least half of the cards led to a verified body load.')).toBeInTheDocument();
    expect(row.getByText('24 of 30 (80%)')).toBeInTheDocument();
    expect(row.getByText('No open item')).toBeInTheDocument();
  });

  test('unlinked loads make pull a lower bound, never a clear gate', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    const row = within(byId('urn:keep-partial'));
    expect(row.getByText('At least 10 of 50')).toBeInTheDocument();
    expect(row.getByText(/4 verified loads carry no search_id, so this share is a lower bound/)).toBeInTheDocument();
    expect(row.getByText('4 loads unlinked to any exposure')).toBeInTheDocument();
    expect(row.queryByText('10 of 50 (20%)')).not.toBeInTheDocument();
  });

  test('value shows counts for a small sample and flags hindered at least matching helped', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    expect(within(byId('urn:small-high')).getByText('5 of 5')).toBeInTheDocument();
    expect(within(byId('urn:small-high')).queryByText(/100%/)).not.toBeInTheDocument();
    expect(within(byId('urn:small-high')).getByText(/small sample/)).toBeInTheDocument();
    expect(within(byId('urn:review-neg')).getByText('10 of 25 (40%)')).toBeInTheDocument();
    expect(within(byId('urn:review-neg')).getByText('Hindered at least matched helped.')).toBeInTheDocument();
  });

  test('health names the open queue item and ignores a decided one', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    expect(within(byId('urn:review-queue')).getByText('Source file changed since publication')).toBeInTheDocument();
    expect(within(byId('urn:review-queue')).getByText('Open: Source file changed since publication')).toBeInTheDocument();
    expect(within(byId('urn:promote')).queryByText(/Published but never loaded/)).not.toBeInTheDocument();
    expect(within(byId('urn:archive')).getByText('No verified load')).toBeInTheDocument();
  });
});

describe('Usage route, skill health recommendations', () => {
  test('the four recommendations, each with its why list, and none applied automatically', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    expect(within(byId('urn:promote')).getByText('Recommended: promote up')).toBeInTheDocument();
    expect(within(byId('urn:promote')).getByText('All four gates clear on at least 20 assessments.')).toBeInTheDocument();
    expect(within(byId('urn:keep-partial')).getByText('Recommended: keep')).toBeInTheDocument();
    expect(within(byId('urn:keep-partial')).getByText('Not every gate is clear: pull.')).toBeInTheDocument();
    expect(within(byId('urn:small-high')).getByText('Recommended: keep')).toBeInTheDocument();
    expect(within(byId('urn:review-neg')).getByText('Recommended: review')).toBeInTheDocument();
    expect(within(byId('urn:review-neg')).getByText('Hindered at least matched helped (10 of 25).')).toBeInTheDocument();
    expect(within(byId('urn:review-queue')).getByText('Recommended: review')).toBeInTheDocument();
    expect(within(byId('urn:review-queue')).getByText('Open queue item: Source file changed since publication')).toBeInTheDocument();
    expect(within(byId('urn:archive')).getByText('Recommended: archive candidate')).toBeInTheDocument();
    expect(within(byId('urn:archive')).getByText('Never shown, never loaded and never assessed in this window.')).toBeInTheDocument();
    expect(screen.queryByText(/will be promoted/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /promote|archive/i })).not.toBeInTheDocument();
  });

  test('acting goes through the queue or a proposal, never through the panel', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    expect(within(byId('urn:review-queue')).getByRole('link', { name: 'Decide in Needs review' })).toHaveAttribute('href', '#needs-review');
    expect(document.getElementById('needs-review')).not.toBeNull();
    expect(within(byId('urn:promote')).getByRole('link', { name: 'Propose a promotion' })).toHaveAttribute('href', expect.stringContaining('/proposals?'));
    expect(within(byId('urn:archive')).getByRole('link', { name: 'Propose archiving' })).toHaveAttribute('href', expect.stringContaining('skill=urn%3Aarchive'));
  });

  test('the summary strip counts recommendations and unknown value', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    await healthRows();
    const strip = within(screen.getByRole('list', { name: 'Recommendations in this window' }));
    const count = (label: string) => strip.getByText(label).closest('li')!.querySelector('strong')!.textContent;
    expect(count('promote up')).toBe('1');
    expect(count('keep')).toBe('2');
    expect(count('review')).toBe('2');
    expect(count('archive candidate')).toBe('1');
    expect(count('Value unknown')).toBe('1');
  });
});

describe('Usage route, skill health ranking', () => {
  test('default order: value, then pull, then reach, ties by id; a small sample never outranks an assessed row', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { rows } = await healthRows();
    const ids = rows.map(row => within(row).getByRole('link', { name: /^urn:/ }).textContent);
    // urn:small-high is 5 of 5 (100%) but stays below urn:review-neg at 40% on 25 assessments.
    expect(ids).toEqual(['urn:promote', 'urn:review-queue', 'urn:keep-partial', 'urn:review-neg', 'urn:small-high', 'urn:archive']);
  });

  test('the order toggles through the URL and an unknown order is named, not silently replaced', async () => {
    const { ctx } = renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }), 'sort=reach');
    const { rows } = await healthRows();
    const ids = rows.map(row => within(row).getByRole('link', { name: /^urn:/ }).textContent);
    expect(ids[0]).toBe('urn:keep-partial');
    expect(ids[ids.length - 1]).toBe('urn:archive');
    expect(screen.getByLabelText('Order by')).toHaveValue('reach');
    await userEvent.selectOptions(screen.getByLabelText('Order by'), 'pull');
    expect(ctx.go).toHaveBeenCalledWith('usage', { sort: 'pull' });

    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }), 'sort=bogus');
    expect(await screen.findByText('Unknown order')).toBeInTheDocument();
    expect(screen.getByText(/"bogus" is not one of value, pull or reach/)).toBeInTheDocument();
  });
});

describe('Usage route, skill health unknowns and funnel', () => {
  test('missing data is Unknown with its reason, never 0', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    const row = within(byId('urn:archive'));
    expect(row.getAllByText('Unknown')).toHaveLength(2);
    expect(row.getByText('Never shown, so no card could lead to a body load.')).toBeInTheDocument();
    expect(row.getByText('No helped or hindered assessment in this window; that is not 0%.')).toBeInTheDocument();
    expect(row.getByText('0 exposed → 0 expanded → 0 loaded → no assessment')).toBeInTheDocument();
    expect(row.queryByText('0%')).not.toBeInTheDocument();
  });

  test('the funnel is four numbers per skill', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => healthReport() }));
    const { byId } = await healthRows();
    expect(within(byId('urn:promote')).getByText('50 exposed → 30 expanded → 30 loaded → 30 judged')).toBeInTheDocument();
    expect(within(byId('urn:keep-partial')).getByText('50 exposed → 10 expanded → 14 loaded → 30 judged')).toBeInTheDocument();
  });
});

// A ledger whose six rows land on every gate state and every recommendation of domain/skillHealth.
const ledgerRow = (over: Partial<UsageSkill> & { skill_id: string; scope: string; owner: string }): UsageSkill => ({
  revision: 'rev', card_revision: null, content_sha256: null, harness: 'claude',
  exposures: 0, loads_verified: 0, context_loaded: 0, context_unknown: 0,
  use_reported: 0, use_observed: 0, use_episodes: 0, exposures_expanded: 0, loads_unlinked: 0,
  feedback: null, helped_ratio: null, zero_loads: false,
  ...over,
});
const fullLedger = (): Usage => report({
  totals: { exposures: 222, loads_verified: 122, context_loaded: 114, context_unknown: 8, use_reported: 63, use_observed: 57, use_episodes: 99, exposures_expanded: 117, loads_unlinked: 5, feedback: { helped: 73, hindered: 23, mixed: 3, not_applicable: 0, unknown: 0, n: 99 }, metrics: noMetrics },
  skills: [
    // Promote up: reach, pull, value and health all clear on 30 assessments.
    ledgerRow({ skill_id: 'urn:promote', scope: '_root', owner: 'platform-engineering', exposures: 84, exposures_expanded: 51, loads_verified: 51, context_loaded: 47, context_unknown: 4, use_reported: 22, use_observed: 19, use_episodes: 33, helped_ratio: { numerator: 26, denominator: 30, small_sample: false } }),
    // Keep: value clear, but five unlinked loads make pull a lower bound.
    ledgerRow({ skill_id: 'urn:keep-unlinked', scope: '_root', owner: 'platform-engineering', exposures: 40, exposures_expanded: 9, loads_verified: 14, loads_unlinked: 5, context_loaded: 12, context_unknown: 2, use_reported: 12, use_observed: 10, use_episodes: 22, helped_ratio: { numerator: 15, denominator: 22, small_sample: false } }),
    // Review: a source_changed item is open although 28 assessments favour the skill.
    ledgerRow({ skill_id: 'urn:review-drift', scope: 'atlas.identity', owner: 'identity-team', exposures: 55, exposures_expanded: 30, loads_verified: 30, context_loaded: 30, use_reported: 16, use_observed: 16, use_episodes: 28, helped_ratio: { numerator: 24, denominator: 28, small_sample: false } }),
    // Review: hindered outnumbers helped on a small sample.
    ledgerRow({ skill_id: 'urn:review-hindered', scope: 'forge.ontology', owner: 'ontology-team', exposures: 31, exposures_expanded: 20, loads_verified: 20, context_loaded: 18, context_unknown: 2, use_reported: 9, use_observed: 8, use_episodes: 12, helped_ratio: { numerator: 5, denominator: 12, small_sample: true } }),
    // Keep: every gate is under a floor (12 exposures, 4 assessments); nothing is wrong.
    ledgerRow({ skill_id: 'urn:keep-small', scope: '_root', owner: 'platform-engineering', exposures: 12, exposures_expanded: 7, loads_verified: 7, context_loaded: 7, use_reported: 4, use_observed: 4, use_episodes: 4, helped_ratio: { numerator: 3, denominator: 4, small_sample: true } }),
    // Archive candidate: published, never shown, never loaded, never assessed.
    ledgerRow({ skill_id: 'urn:archive', scope: '_root', owner: 'platform-engineering', zero_loads: true }),
  ],
  queue: [
    { item_id: 'q-drift', skill_id: 'urn:review-drift', revision: 'rev', reason: 'source_changed', since: '2026-09-02T10:15:00Z', evidence: { commit: '88e40456' }, decision: null },
    { item_id: 'q-neg', skill_id: 'urn:review-hindered', revision: 'rev', reason: 'negative_feedback', since: '2026-08-28T08:00:00Z', evidence: { hindered: 7, helped: 5 }, decision: null },
    { item_id: 'q-zero', skill_id: 'urn:archive', revision: 'rev', reason: 'zero_loads', since: '2026-08-16T00:00:00Z', evidence: { exposures: 0, loads: 0 }, decision: null },
  ],
});

describe('Usage route, skill health over a full ledger', () => {
  test('six rows that cover every gate land on every recommendation, each computed from the API report', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => fullLedger() }));
    const { rows, byId } = await healthRows();
    expect(rows).toHaveLength(6);
    expect(within(byId('urn:promote')).getByText('Recommended: promote up')).toBeInTheDocument();
    expect(within(byId('urn:keep-unlinked')).getByText('Recommended: keep')).toBeInTheDocument();
    expect(within(byId('urn:keep-small')).getByText('Recommended: keep')).toBeInTheDocument();
    expect(within(byId('urn:review-drift')).getByText('Recommended: review')).toBeInTheDocument();
    expect(within(byId('urn:review-hindered')).getByText('Recommended: review')).toBeInTheDocument();
    expect(within(byId('urn:archive')).getByText('Recommended: archive candidate')).toBeInTheDocument();
  });

  test('a report with no skill rows renders no health panel and no zero recommendation', async () => {
    renderApi(ApiUsageRoute, fakeSource({ getUsage: async () => empty }));
    expect((await screen.findAllByText('No observations')).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.queryByRole('table', { name: 'Skill health per skill' })).not.toBeInTheDocument());
    expect(screen.queryByText(/Recommended:/)).not.toBeInTheDocument();
  });
});
