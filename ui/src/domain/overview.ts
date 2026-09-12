/** Overview (Home): pure aggregation over the contract's own answers, no new API.
 *
 * Every number here is a count the API already returns or a sum of such counts. Nothing is a
 * score, a delta against a previous window (the contract has none) or a rate below the sample
 * floor. Absent data stays absent: a `null` in this module is "Unknown", never zero.
 */
import type {AdapterHealth, ImportStatus, Installation, Me, ProposalState, ProposalSummary, Role, SkillSummary, Usage} from '../api/decoders';
import {assessSkills, countRecommendations, type Recommendation, type SkillHealth} from './skillHealth';

/** The contract's `small_sample` floor: below this many helped-or-hindered assessments, counts only. */
export const RATE_FLOOR = 20;
/** An adapter silent for longer than this is called stale, not broken. */
export const ADAPTER_STALE_MS = 24 * 60 * 60 * 1000;
/** Coverage lag above this is called lagging. */
export const LAG_WARN_S = 3600;
export const TOP_SKILLS = 5;

// ---------------------------------------------------------------------------
// Telemetry
// ---------------------------------------------------------------------------

export type CoverageState = 'live' | 'lagging' | 'none' | 'unknown';
export interface Coverage { state: CoverageState; label: string; detail: string }

export function coverageOf(usage: Usage | null): Coverage {
  const coverage = usage?.coverage;
  if (!usage || !coverage) return {state: 'unknown', label: 'Coverage unknown', detail: 'The report carries no coverage block.'};
  if (coverage.events_received === 0) return {state: 'none', label: 'No adapter events', detail: 'No adapter event reached the ledger in this window.'};
  if (coverage.dropped_reported > 0 || (coverage.oldest_lag_s ?? 0) > LAG_WARN_S) {
    const parts: string[] = [];
    if (coverage.dropped_reported > 0) parts.push(coverage.dropped_reported + ' dropped');
    if ((coverage.oldest_lag_s ?? 0) > LAG_WARN_S) parts.push('lag ' + Math.round(coverage.oldest_lag_s! / 60) + ' min');
    return {state: 'lagging', label: 'Lagging', detail: parts.join(', ') + '; counts are lower bounds.'};
  }
  return {state: 'live', label: 'Live', detail: coverage.events_received + ' events received, lag ' + (coverage.oldest_lag_s ?? 0) + ' s.'};
}

/** helped / (helped + hindered), only from the floor up; below it the counts, never a percent. */
export interface HelpedShare { helped: number; hindered: number; denominator: number; percent: number | null; label: string; caption: string }
export function helpedShare(usage: Usage | null): HelpedShare | null {
  const feedback = usage?.totals.feedback;
  if (!feedback) return null;
  const helped = feedback.helped, hindered = feedback.hindered, denominator = helped + hindered;
  if (denominator === 0) return null;
  if (denominator < RATE_FLOOR) return {helped, hindered, denominator, percent: null, label: helped + ' of ' + denominator, caption: 'Helped over helped plus hindered; below ' + RATE_FLOOR + ' assessments, counts only.'};
  const percent = Math.round((helped / denominator) * 100);
  return {helped, hindered, denominator, percent, label: percent + '%', caption: helped + ' helped of ' + denominator + ' helped-or-hindered assessments.'};
}

export interface FunnelStep { key: string; label: string; value: number; note?: string }
/** Exposed → expanded → loaded → context confirmed → used episodes. Each step is its own count from the
 * totals; steps are not guaranteed monotone because unlinked loads have no exposure to belong to. */
export function funnelSteps(usage: Usage): FunnelStep[] {
  const t = usage.totals;
  return [
    {key: 'exposed', label: 'Exposed', value: t.exposures},
    {key: 'expanded', label: 'Expanded', value: t.exposures_expanded, note: t.loads_unlinked > 0 ? 'lower bound: ' + t.loads_unlinked + ' unlinked loads' : undefined},
    {key: 'loaded', label: 'Loaded', value: t.loads_verified},
    {key: 'context', label: 'Context confirmed', value: t.context_loaded, note: t.context_unknown > 0 ? t.context_unknown + ' unknown' : undefined},
    {key: 'used', label: 'Used episodes', value: t.use_episodes},
  ];
}

export function hasObservations(usage: Usage | null): boolean {
  if (!usage) return false;
  const t = usage.totals;
  return t.exposures > 0 || t.loads_verified > 0 || t.use_reported > 0 || t.use_observed > 0 || (t.feedback?.n ?? 0) > 0;
}

export interface TopSkills { rows: SkillHealth[]; total: number; recommendations: Record<Recommendation, number> }
export function topSkills(usage: Usage, limit = TOP_SKILLS): TopSkills {
  const all = assessSkills(usage.skills, usage.queue, 'value');
  return {rows: all.slice(0, limit), total: all.length, recommendations: countRecommendations(all)};
}

export function openQueueCount(usage: Usage | null): number | null {
  if (!usage) return null;
  return usage.queue.filter(item => !item.decision).length;
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

export interface LibraryBreakdown { published: number; draft: number; needsReview: number; other: number; total: number; truncated: boolean }
/** Counts by publication state over the skills the page returned; `truncated` says the page was not the whole catalogue. */
export function libraryBreakdown(skills: SkillSummary[], nextCursor: string | null): LibraryBreakdown {
  const result: LibraryBreakdown = {published: 0, draft: 0, needsReview: 0, other: 0, total: skills.length, truncated: Boolean(nextCursor)};
  for (const skill of skills) {
    if (skill.publication_status === 'published') result.published += 1;
    else if (skill.publication_status === 'draft') result.draft += 1;
    else if (skill.publication_status === 'needs_review') result.needsReview += 1;
    else result.other += 1;
  }
  return result;
}

export interface ScopeShare { scope: string; count: number }
export function topScopes(values: {value: string; count: number}[], limit = 6): ScopeShare[] {
  return [...values].filter(item => item.count > 0).sort((a, b) => b.count - a.count || (a.value < b.value ? -1 : 1)).slice(0, limit).map(item => ({scope: item.value, count: item.count}));
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export const proposalStateOrder: ProposalState[] = ['draft', 'approved_for_export', 'awaiting_git', 'published', 'rejected', 'superseded'];
export const proposalStateLabels: Record<ProposalState, string> = {
  draft: 'Draft', approved_for_export: 'Approved', awaiting_git: 'Awaiting Git', published: 'Published', rejected: 'Rejected', superseded: 'Superseded',
};
export function proposalsByState(items: ProposalSummary[]): {state: ProposalState; label: string; count: number}[] {
  const counts = new Map<ProposalState, number>();
  for (const item of items) counts.set(item.state, (counts.get(item.state) ?? 0) + 1);
  return proposalStateOrder.map(state => ({state, label: proposalStateLabels[state], count: counts.get(state) ?? 0}));
}

export type AdapterState = 'ok' | 'stale' | 'never';
export interface AdapterRow { name: string; harness: string; state: AdapterState; label: string; lastSeen: string | null; version: string | null }
/** One row per installation; health rows from usage add lag when the harness matches. */
export function adapterRows(installations: Installation[], health: AdapterHealth[] | null, now: number): AdapterRow[] {
  return installations.map(item => {
    const seen = item.last_seen_at ? Date.parse(item.last_seen_at) : NaN;
    const harness = item.harness ?? 'unknown harness';
    const lag = health?.find(row => row.harness === item.harness)?.lag_s ?? null;
    if (Number.isNaN(seen)) return {name: item.name, harness, state: 'never', label: 'Never seen', lastSeen: null, version: item.adapter_version};
    const age = now - seen;
    if (age > ADAPTER_STALE_MS) return {name: item.name, harness, state: 'stale', label: 'Silent ' + Math.floor(age / ADAPTER_STALE_MS) + ' d', lastSeen: item.last_seen_at, version: item.adapter_version};
    return {name: item.name, harness, state: 'ok', label: lag === null ? 'Reporting' : 'Reporting, lag ' + lag + ' s', lastSeen: item.last_seen_at, version: item.adapter_version};
  });
}

export function latestImport(imports: ImportStatus[]): ImportStatus | null {
  if (!imports.length) return null;
  return [...imports].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))[0];
}

// ---------------------------------------------------------------------------
// Next actions (role-aware)
// ---------------------------------------------------------------------------

export type ActionKind = 'queue' | 'proposals' | 'publish' | 'adapter' | 'identity' | 'import' | 'rate' | 'library';
export interface NextAction { kind: ActionKind; title: string; detail: string; tone: 'human' | 'system' | 'neutral' }

export function nextActions(input: {
  role: Role | null; me: Me | null; usage: Usage | null; proposals: ProposalSummary[] | null;
  imports: ImportStatus[] | null; installations: Installation[] | null; skillsTotal: number | null; now: number;
}): NextAction[] {
  const owner = input.role === 'owner';
  const actions: NextAction[] = [];
  const open = openQueueCount(input.usage);
  if (owner && open) actions.push({kind: 'queue', tone: 'human', title: open + (open === 1 ? ' skill needs' : ' skills need') + ' your decision', detail: 'Drift, negative feedback or a missing dependency was recorded. Each waits in Needs review.'});
  const drafts = input.proposals?.filter(item => item.state === 'draft').length ?? 0;
  if (owner && drafts) actions.push({kind: 'proposals', tone: 'human', title: drafts + (drafts === 1 ? ' proposal waits' : ' proposals wait') + ' for a decision', detail: 'A candidate revision is prepared. Approve, edit or reject it before the Git handoff.'});
  const awaiting = input.proposals?.filter(item => item.state === 'approved_for_export' || item.state === 'awaiting_git').length ?? 0;
  if (awaiting) actions.push({kind: 'proposals', tone: 'system', title: awaiting + (awaiting === 1 ? ' approved proposal is' : ' approved proposals are') + ' not in Git yet', detail: 'Export the files and open the pull request; publication is observed after the merge.'});
  const last = input.imports ? latestImport(input.imports) : null;
  if (owner && last && last.state === 'ready' && last.publication?.state !== 'published') actions.push({kind: 'publish', tone: 'human', title: 'The latest import is not published', detail: 'Files are stored; nothing is served until a snapshot is activated.'});
  if (input.imports && input.imports.length === 0) actions.push({kind: 'import', tone: 'human', title: 'No import yet', detail: 'Upload your checkout with the CLI to fill the library.'});
  if (input.installations) {
    if (input.installations.length === 0 && owner) actions.push({kind: 'adapter', tone: 'system', title: 'No adapter installed', detail: 'Without an adapter no delivery or feedback reaches the ledger, so usefulness stays Unknown.'});
    else {
      const silent = adapterRows(input.installations, input.usage?.health?.adapters ?? null, input.now).filter(row => row.state !== 'ok');
      if (silent.length && silent.length === input.installations.length) actions.push({kind: 'adapter', tone: 'system', title: 'Every adapter is silent', detail: silent.map(row => row.name + ': ' + row.label.toLowerCase()).join('; ') + '.'});
    }
  }
  if (input.me && input.me.link_suggestions.length) actions.push({kind: 'identity', tone: 'neutral', title: 'Another sign-in method uses your e-mail', detail: 'Link it so one account keeps every decision and assessment.'});
  if (!owner && input.skillsTotal) actions.push({kind: 'rate', tone: 'system', title: 'Rate a skill you used', detail: 'An assessment on the exact revision is the only evidence of usefulness the ledger accepts.'});
  return actions;
}
