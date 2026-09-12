/** Home (Overview): the first screen after sign-in (IA §3, 2026-09-12), rebuilt on the
 * shadcnspace dashboard blocks (owner instruction: "site looks way off" from
 * https://dashboard.shadcnspace.com/ — docs/reports/ui/console-shadcn-20260912.md §9).
 *
 * One read per block, all in parallel, every number a count the API returned. The screen answers
 * three questions in order: what waits for me, how the library is doing, how delivery and value
 * look in the chosen window. A block with nothing to say folds to one line; a page with no
 * organisation or repository shows the one next step instead of eight empty cards.
 */
import {lazy, Suspense, useMemo} from 'react';
import {Link} from 'react-router-dom';
import {BookOpenIcon, ListChecksIcon as LucideListChecksIcon, ThumbsUpIcon as LucideThumbsUpIcon} from 'lucide-react';
import {ArrowRightIcon, BooksIcon, ChartBarIcon, ClockCounterClockwiseIcon, FolderOpenIcon, GitPullRequestIcon, LinkSimpleIcon, ListChecksIcon, PlugsConnectedIcon, PulseIcon, StarIcon, StackIcon, ThumbsUpIcon, UploadSimpleIcon, UserCircleIcon, WarningCircleIcon} from '@phosphor-icons/react';
import {Alert, AlertDescription, AlertTitle} from '@/components/ui/alert';
import {Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle} from '@/components/ui/card';
import {Progress} from '@/components/ui/progress';
import {Table, TableBody, TableCell, TableHead, TableHeader as TableHeadRow, TableRow} from '@/components/ui/table';
import {ActionButton, IconTile, Panel, RouteState, StateBadge} from '../Shared';
import {ApiFailure, DegradedNotice, PartialNotice, formatNumber, readOnly, shortId, useAsync, type ApiProps} from './apiState';
import type {AuditEntry, ImportStatus, Installation, ProposalSummary, SkillPage, Usage} from '../api/decoders';
import type {Facets, MapLayers} from '../api/decoders';
import {adapterRows, coverageOf, delta, funnelSteps, hasObservations, helpedShare, helpedShareDelta, latestImport, libraryBreakdown, nextActions, openQueueCount, proposalsByState, topScopes, topSkills, yourDecisions, type ActionKind, type Delta, type NextAction, type YourDecisions} from '../domain/overview';
import type {GateState, Recommendation} from '../domain/skillHealth';
import {StatisticsMain, StatisticsSecondary, type MainMetric, type StatTrend} from '../components/ui/shadcn-space/blocks/statistics-01/statistics';
import {SkillsTable, GateBadge, type SkillRow} from '../components/ui/shadcn-space/blocks/table-01/table';
import type {DonutSegment} from '../components/ui/shadcn-space/blocks/chart-02/chart';
import {EmptyStateBlock} from '../components/ui/shadcn-space/blocks/empty-state-01/empty-state';
import styles from './HomeRoute.module.css';

const FunnelBarChart = lazy(() => import('../components/ui/shadcn-space/blocks/chart-01/chart').then(m => ({default: m.FunnelBarChart})));
const DonutChart = lazy(() => import('../components/ui/shadcn-space/blocks/chart-02/chart').then(m => ({default: m.DonutChart})));

const usageWindows = ['7d', '30d', '90d'] as const;
const gateTone: Record<GateState, 'neutral' | 'system' | 'warning'> = {clear: 'system', attention: 'warning', low: 'neutral', partial: 'neutral', unknown: 'neutral'};
const recommendationLabels: Record<Recommendation, string> = {promote_up: 'Promote up', keep: 'Keep', review: 'Review', archive_candidate: 'Archive candidate'};
const recommendationTone: Record<Recommendation, 'neutral' | 'system' | 'warning'> = {promote_up: 'system', keep: 'neutral', review: 'warning', archive_candidate: 'warning'};
const actionIcon: Record<ActionKind, typeof ListChecksIcon> = {queue: ListChecksIcon, proposals: GitPullRequestIcon, publish: UploadSimpleIcon, adapter: PlugsConnectedIcon, identity: UserCircleIcon, import: UploadSimpleIcon, rate: ThumbsUpIcon, library: BooksIcon};
const layerLabels: Record<string, string> = {atomic: 'Atomic', task: 'Task', abstract: 'Abstract', unclassified: 'Unclassified'};
const layerFills: Record<string, string> = {abstract: 'var(--chart-4)', task: 'var(--chart-2)', atomic: 'var(--chart-1)', unclassified: 'var(--chart-5)'};
const layerSwatch: Record<string, string> = {abstract: 'bg-chart-4', task: 'bg-chart-2', atomic: 'bg-chart-1', unclassified: 'bg-chart-5'};
const feedbackSegments = [
  {key: 'helped', label: 'Helped', fill: 'var(--chart-1)', swatchClass: 'bg-chart-1'},
  {key: 'hindered', label: 'Hindered', fill: 'var(--chart-5)', swatchClass: 'bg-chart-5'},
  {key: 'mixed', label: 'Mixed', fill: 'var(--chart-3)', swatchClass: 'bg-chart-3'},
  {key: 'not_applicable', label: 'Not applicable', fill: 'var(--muted-foreground)', swatchClass: 'bg-muted-foreground'},
  {key: 'unknown', label: 'Unknown', fill: 'var(--chart-4)', swatchClass: 'bg-chart-4'},
] as const;

const day = (iso: string | null) => iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? iso.slice(0, 10) : 'Unknown';
const skillName = (id: string) => id.split(':').pop() ?? id;

function actionHref(ctx: ApiProps['ctx'], kind: ActionKind): string {
  switch (kind) {
    case 'queue': return ctx.href('usage', {}) + '#needs-review';
    case 'proposals': return ctx.href('proposals', {state: 'draft'});
    case 'publish': return ctx.href('import', {step: 'result'});
    case 'import': return ctx.href('import', {step: 'preview'});
    case 'adapter': return ctx.href('organization', {tab: 'integrations'});
    case 'identity': return ctx.href('organization', {tab: 'members'});
    case 'rate':
    case 'library': return ctx.href('library', {});
  }
}

function ChartFallback() { return <div className={styles.chartFallback} aria-busy="true"><span className="sr-only">Loading chart</span></div>; }

/** `domain/overview.delta`/`helpedShareDelta` stay UI-agnostic; this is the one place that turns
 * a verdict into the `Badge` tone the trend widget understands. `known: false` (no previous
 * window, or — for helped share — nothing comparable on either side) is the only case that
 * renders no trend at all, falling through to `TrendBadge`'s own "No previous window" default; a
 * known `0` previous ("new", "no change") still renders a badge. */
function toTrend(value: Delta): StatTrend | null {
  if (!value.known) return null;
  return {label: value.label, tone: value.direction === 'down' ? 'warning' : value.direction === 'up' ? 'system' : 'neutral'};
}

function NextActions({ctx, actions}: ApiProps & {actions: NextAction[]}) {
  return <Panel title="Your next actions" eyebrow={ctx.role === 'owner' ? 'As an owner of this organization' : 'As a member of this organization'} icon={<ListChecksIcon aria-hidden="true" />}>
    {actions.length ? <ol className={styles.actions} aria-label="Next actions">{actions.map((action, index) => {
      const Icon = actionIcon[action.kind];
      return <li key={action.kind + index}><Link to={actionHref(ctx, action.kind)} className={styles.action} data-tone={action.tone}>
        <IconTile icon={<Icon weight="duotone" />} size="md" tone={action.tone} animate={false} />
        <span className={styles.actionText}><strong>{action.title}</strong><span>{action.detail}</span></span>
        <ArrowRightIcon aria-hidden="true" className={styles.actionArrow} />
      </Link></li>;
    })}</ol>
    : <RouteState compact state="empty" title="Nothing waits for you" description="No open decision, no unpublished import and every adapter reported in the last day." />}
  </Panel>;
}

function Kpis({ctx, usage, skills, windowLabel}: ApiProps & {usage: Usage | null; skills: SkillPage | null; windowLabel: string}) {
  const library = skills ? libraryBreakdown(skills.items, skills.next_cursor) : null;
  const share = helpedShare(usage);
  const open = openQueueCount(usage);
  // 1.3.0: a trend badge compares this window's count with `usage.previous.totals`, when the API
  // reports one; `delta`/`helpedShareDelta` themselves decide when there is nothing to compare.
  const exposuresTrend = usage ? delta(usage.totals.exposures, usage.previous?.totals.exposures ?? null) : null;
  const loadsTrend = usage ? delta(usage.totals.loads_verified, usage.previous?.totals.loads_verified ?? null) : null;
  // Percentage points, never a relative percent of a percent (75% → 82% is "+7 pp", not "+9%").
  const helpedTrend = helpedShareDelta(usage);
  const mainMetrics: [MainMetric, MainMetric] = [
    {label: 'Published skills', value: library ? formatNumber(library.published) + (library.truncated ? '+' : '') : 'Unknown', caption: library ? formatNumber(library.draft) + ' draft · ' + formatNumber(library.needsReview) + ' needs review' : 'The catalogue could not be read.', trend: null},
    {
      label: 'Exposures, ' + windowLabel,
      value: usage ? formatNumber(usage.totals.exposures) : 'Unknown',
      caption: usage ? formatNumber(usage.totals.loads_verified) + ' verified loads' + (loadsTrend && loadsTrend.known ? ' (' + loadsTrend.label + ' from the equal-length window before)' : '') : 'No report for this window.',
      trend: exposuresTrend ? toTrend(exposuresTrend) : null,
    },
  ];
  // The queue is a live count of open decisions, not a windowed total: the contract carries no
  // previous value for it, so its trend badge always reads "No previous window".
  const openTrend: StatTrend | null = null;
  const links = [ctx.href('library', {status: 'published'}), ctx.href('usage', {window: windowLabel}), ctx.href('usage', {window: windowLabel}), ctx.href('usage', {}) + '#needs-review'];
  const cardLabels = [mainMetrics[0].label, mainMetrics[1].label, 'Helped share', 'Needs review'];
  return <section aria-label="Key numbers" className={styles.kpis}>
    <div className={styles.kpiGrid}>
      <div className={styles.kpiMain}><StatisticsMain title={ctx.org && ctx.repo ? ctx.org + ' / ' + ctx.repo : 'This workspace'} description="Published skills and delivery in the chosen window" metrics={mainMetrics} /></div>
      <StatisticsSecondary title="Helped share" value={share ? share.label : 'Unknown'} caption={share ? share.caption : 'No helped or hindered assessment in this window; that is not 0%.'} icon={LucideThumbsUpIcon} tone="system" trend={toTrend(helpedTrend)} />
      <StatisticsSecondary title="Needs review" value={open === null ? 'Unknown' : formatNumber(open)} caption={open === null ? 'The queue could not be read.' : open === 0 ? 'No open owner decision' : (open === 1 ? 'Open owner decision' : 'Open owner decisions')} icon={LucideListChecksIcon} tone={open ? 'warning' : 'neutral'} trend={openTrend} />
    </div>
    <ul className={styles.kpiLinks} aria-label="Open the source of each number">{cardLabels.map((label, index) => <li key={label}><Link to={links[index]}>{label}<ArrowRightIcon aria-hidden="true" /></Link></li>)}</ul>
  </section>;
}

function Funnel({usage}: {usage: Usage}) {
  const steps = funnelSteps(usage);
  return <Suspense fallback={<ChartFallback />}><FunnelBarChart title="Delivery funnel" eyebrow="Every step is its own count; a later step can exceed an earlier one when loads carry no search id" data={steps.map(step => ({category: step.label, value: step.value}))} /></Suspense>;
}

function Feedback({usage}: {usage: Usage}) {
  const feedback = usage.totals.feedback;
  const counted = feedback ? feedbackSegments.map(segment => ({...segment, value: feedback[segment.key]})) : [];
  const total = feedback?.n ?? 0;
  const valid = counted.length > 0 && counted.every(segment => Number.isFinite(segment.value) && segment.value >= 0) && counted.reduce((sum, segment) => sum + segment.value, 0) === total && total > 0;
  if (!feedback || total === 0) return <Card className="h-full rounded-xl border shadow-xs"><CardContent className="flex h-full items-center justify-center p-6"><EmptyStateBlock compact icon={<LucideThumbsUpIcon aria-hidden="true" />} title="No assessment yet" description="Nobody rated a revision in this window. Usefulness is Unknown, not zero." /></CardContent></Card>;
  if (!valid) return <Card className="h-full rounded-xl border p-6 shadow-xs"><p role="status" className={styles.muted}>The verdict counts do not match the assessment total. Showing the reported counts without a chart.</p></Card>;
  const segments: DonutSegment[] = counted.filter(segment => segment.value > 0);
  return <Suspense fallback={<ChartFallback />}><DonutChart title="Feedback" eyebrow={formatNumber(total) + ' assessments in this window'} centerLabel="Assessments" centerValue={formatNumber(total)} segments={segments} /></Suspense>;
}

function TopSkillsPanel({ctx, usage}: ApiProps & {usage: Usage}) {
  const top = useMemo(() => topSkills(usage), [usage]);
  const counts = top.recommendations;
  const rows: SkillRow[] = top.rows.map(row => ({
    skillId: row.skill.skill_id, skillName: skillName(row.skill.skill_id), scope: row.skill.scope ?? 'Unknown scope',
    href: ctx.href('skill', {skill: row.skill.skill_id, from: 'home'}),
    recommendation: {label: recommendationLabels[row.recommendation], tone: recommendationTone[row.recommendation]},
    reach: {label: row.reach.label, tone: gateTone[row.reach.state]},
    pull: {label: row.pull.label, tone: gateTone[row.pull.state]}, pullShare: null,
    value: {label: row.value.label, tone: gateTone[row.value.state]},
    health: {label: row.health.label, tone: gateTone[row.health.state]},
  }));
  return <Card className="rounded-xl border py-6 shadow-xs">
    <CardHeader className="px-6">
      <CardTitle className="text-lg font-medium"><StarIcon aria-hidden="true" className="mr-2 inline align-text-bottom" />Top skills</CardTitle>
      <CardDescription>{top.total ? 'Best ' + Math.min(top.rows.length, top.total) + ' of ' + formatNumber(top.total) + ' observed, by helped share then pull' : 'No skill observed in this window'}</CardDescription>
      <CardAction><ActionButton size="sm" tone="system" href={ctx.href('usage', {})}>Open Usage &amp; quality</ActionButton></CardAction>
    </CardHeader>
    <CardContent className="px-0">
      {top.total ? <>
        <ul className={styles.recommendations} aria-label="Recommendations over every observed skill">
          {(Object.keys(recommendationLabels) as Recommendation[]).map(key => <li key={key}><GateBadge label={recommendationLabels[key]} tone={recommendationTone[key]} /><strong>{formatNumber(counts[key])}</strong></li>)}
        </ul>
        <SkillsTable label="Top skills with their four gates" rows={rows} />
        <p className={styles.muted + ' px-6'}>A recommendation is computed in this browser from the counts in the row; it changes nothing. Load counts alone never promote a skill.</p>
      </> : <div className="px-6"><EmptyStateBlock compact icon={<StarIcon aria-hidden="true" />} title="No skill observed" description="No card of any skill reached a harness in this window." /></div>}
    </CardContent>
  </Card>;
}

function Library({ctx, skills, layers, scopes}: ApiProps & {skills: SkillPage | null; layers: MapLayers | null; scopes: Facets | null}) {
  const breakdown = skills ? libraryBreakdown(skills.items, skills.next_cursor) : null;
  const layerRows = (layers?.layers ?? []).filter(row => row.count > 0);
  const layerTotal = layerRows.reduce((sum, row) => sum + row.count, 0);
  const scopeRows = scopes ? topScopes(scopes.values) : [];
  return <Card className="rounded-xl border py-6 shadow-xs">
    <CardHeader className="px-6">
      <CardTitle className="text-lg font-medium"><BooksIcon aria-hidden="true" className="mr-2 inline align-text-bottom" />Library at a glance</CardTitle>
      <CardDescription>{breakdown ? formatNumber(breakdown.total) + (breakdown.truncated ? '+ skills; the first page only' : ' skills') : 'The catalogue could not be read'}</CardDescription>
      <CardAction><ActionButton size="sm" tone="system" href={ctx.href('library', {})}>Open Library</ActionButton></CardAction>
    </CardHeader>
    <CardContent className="flex flex-col gap-4 px-6">
      {breakdown && <ul className={styles.splits} aria-label="Skills by publication state">
        <li><Link to={ctx.href('library', {status: 'published'})}><StateBadge tone="system">Published</StateBadge><strong>{formatNumber(breakdown.published)}</strong></Link></li>
        <li><Link to={ctx.href('library', {status: 'draft'})}><StateBadge tone="human">Draft</StateBadge><strong>{formatNumber(breakdown.draft)}</strong></Link></li>
        <li><Link to={ctx.href('library', {status: 'needs_review'})}><StateBadge tone="warning">Needs review</StateBadge><strong>{formatNumber(breakdown.needsReview)}</strong></Link></li>
        {breakdown.other > 0 && <li><StateBadge>Other states</StateBadge><strong>{formatNumber(breakdown.other)}</strong></li>}
      </ul>}
      <div className={styles.twoUp}>
        <section aria-labelledby="home-layers" className={styles.subsection}>
          <h3 id="home-layers"><StackIcon aria-hidden="true" />Knowledge layers</h3>
          {layerTotal > 0 ? <Suspense fallback={<ChartFallback />}><DonutChart title="" centerLabel="Skills" centerValue={formatNumber(layerTotal)} segments={layerRows.map(row => ({key: row.layer, label: layerLabels[row.layer] ?? row.layer, value: row.count, fill: layerFills[row.layer] ?? 'var(--chart-4)', swatchClass: layerSwatch[row.layer] ?? 'bg-chart-4'}))} /></Suspense>
          : <p className={styles.muted}>No layer declared. A layer is declared in the skill, never inferred from its folder.</p>}
        </section>
        <section aria-labelledby="home-scopes" className={styles.subsection}>
          <h3 id="home-scopes"><ChartBarIcon aria-hidden="true" />Largest scopes</h3>
          {scopeRows.length ? <ol className={styles.bars} aria-label="Skills per scope, largest first">{scopeRows.map(row => {
            const width = Math.max(4, Math.round((row.count / scopeRows[0].count) * 100));
            return <li key={row.scope}><Link to={ctx.href('library', {scope: row.scope})}><code>{row.scope}</code><svg className={styles.bar} viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true"><rect x="0" y="0" width={width} height="8" rx="2" /></svg><strong>{formatNumber(row.count)}</strong></Link></li>;
          })}</ol> : <p className={styles.muted}>No scope with a skill yet.</p>}
        </section>
      </div>
    </CardContent>
  </Card>;
}

function Pipeline({ctx, imports, proposals, installations, usage, now}: ApiProps & {imports: ImportStatus[] | null; proposals: ProposalSummary[] | null; installations: Installation[] | null; usage: Usage | null; now: number}) {
  const last = imports ? latestImport(imports) : null;
  const states = proposals ? proposalsByState(proposals) : null;
  const statesTotal = states ? states.reduce((sum, row) => sum + row.count, 0) : 0;
  const adapters = installations ? adapterRows(installations, usage?.health?.adapters ?? null, now) : null;
  const publication = last?.publication?.state ?? 'none';
  return <Card className="rounded-xl border py-6 shadow-xs">
    <CardHeader className="px-6"><CardTitle className="text-lg font-medium"><PulseIcon aria-hidden="true" className="mr-2 inline align-text-bottom" />Pipeline</CardTitle><CardDescription>Import, proposals and adapters</CardDescription></CardHeader>
    <CardContent className="px-6">
      <div className={styles.threeUp}>
        <section aria-labelledby="home-import" className={styles.subsection}>
          <h3 id="home-import"><UploadSimpleIcon aria-hidden="true" />Latest import</h3>
          {last ? <dl className={styles.facts}>
            <div><dt>Import</dt><dd><Link to={ctx.href('import', {step: 'result', import_id: last.import_id})}><code>{shortId(last.import_id)}</code></Link></dd></div>
            <div><dt>State</dt><dd><GateBadge label={last.state} tone={last.state === 'ready' ? 'system' : last.state === 'failed' ? 'warning' : 'neutral'} /></dd></div>
            <div><dt>Files</dt><dd>{last.counts ? formatNumber(last.counts.accepted) + ' accepted · ' + formatNumber(last.counts.omitted) + ' omitted · ' + formatNumber(last.counts.failed) + ' failed' : 'Unknown'}</dd></div>
            <div><dt>Publication</dt><dd><GateBadge label={publication} tone={publication === 'published' ? 'system' : publication === 'failed' ? 'warning' : 'neutral'} /></dd></div>
            <div><dt>Created</dt><dd>{day(last.created_at)}</dd></div>
          </dl> : imports ? <p className={styles.muted}>No import yet. <Link to={ctx.href('import', {step: 'preview'})}>Upload your checkout</Link>.</p> : <p className={styles.muted}>Imports could not be read.</p>}
        </section>
        <section aria-labelledby="home-proposals" className={styles.subsection}>
          <h3 id="home-proposals"><GitPullRequestIcon aria-hidden="true" />Proposals by state</h3>
          {states ? <ul className={styles.states} aria-label="Proposals by state">{states.map(row => <li key={row.state}><Link to={ctx.href('proposals', {state: row.state})} className={styles.stateLink}><span className={styles.stateRow}><span>{row.label}</span><strong>{formatNumber(row.count)}</strong></span>{statesTotal > 0 && <Progress value={Math.round((row.count / statesTotal) * 100)} aria-label={row.label + ' share'} />}</Link></li>)}</ul> : <p className={styles.muted}>Proposals could not be read.</p>}
        </section>
        <section aria-labelledby="home-adapters" className={styles.subsection}>
          <h3 id="home-adapters"><PlugsConnectedIcon aria-hidden="true" />Adapters</h3>
          {adapters === null ? <p className={styles.muted}>Installations could not be read.</p>
          : adapters.length === 0 ? <p className={styles.muted}>No installation yet. <Link to={ctx.href('organization', {tab: 'integrations'})}>Create one</Link> so delivery and feedback can reach the ledger.</p>
          : <ul className={styles.adapters} aria-label="Adapter installations">{adapters.map(row => <li key={row.name}><span className={styles.adapterName}><strong>{row.name}</strong><small>{row.harness}{row.version ? ' · ' + row.version : ''}</small></span><GateBadge label={row.label} tone={row.state === 'ok' ? 'system' : row.state === 'stale' ? 'warning' : 'neutral'} /></li>)}</ul>}
        </section>
      </div>
    </CardContent>
  </Card>;
}

/** 1.3.0: proposals and owner-queue items whose latest decision is this reader's own
 * (`domain/overview.yourDecisions`). Folded entirely when the count is zero — an empty "Your
 * decisions" card would say nothing an owner or member does not already know. */
function YourDecisionsPanel({ctx, decisions}: ApiProps & {decisions: YourDecisions}) {
  return <Card className="rounded-xl border py-6 shadow-xs">
    <CardHeader className="px-6">
      <CardTitle className="text-lg font-medium"><ListChecksIcon aria-hidden="true" className="mr-2 inline align-text-bottom" />Your decisions</CardTitle>
      <CardDescription>{formatNumber(decisions.count) + ' decision' + (decisions.count === 1 ? '' : 's') + ' you recorded' + (decisions.count > decisions.items.length ? ', ' + formatNumber(decisions.items.length) + ' most recent shown' : '')}</CardDescription>
    </CardHeader>
    <CardContent className="px-0">
      <ul className={styles.states} aria-label="Your most recent decisions">
        {decisions.items.map(item => <li key={item.kind + ':' + item.id}>
          <Link to={item.kind === 'proposal' ? ctx.href('proposals', {proposal: item.id}) : ctx.href('usage', {}) + '#needs-review'} className={styles.stateLink}>
            <span className={styles.stateRow}><span>{item.kind === 'proposal' ? 'Proposal for ' : 'Queue item for '}{skillName(item.skillId ?? item.label)}</span><StateBadge>{item.detail}</StateBadge></span>
          </Link>
        </li>)}
      </ul>
    </CardContent>
  </Card>;
}

function Activity({ctx, entries, owner}: ApiProps & {entries: AuditEntry[]; owner: boolean}) {
  return <Card className="rounded-xl border py-6 shadow-xs">
    <CardHeader className="px-6">
      <p className="m-0 text-xs font-medium text-muted-foreground">{owner ? 'Organization audit' : 'Your actions'}</p>
      <CardTitle className="text-lg font-medium"><ClockCounterClockwiseIcon aria-hidden="true" className="mr-2 inline align-text-bottom" />Recent activity</CardTitle>
      {/* 1.3.0: the server, not this component, decides which rows a member's read returns
          (contract §4.1) — the description just says whose activity this reader is looking at. */}
      <CardDescription>{owner ? 'Last entries of the organization audit log' : 'Last entries of your own actions in this organization'}</CardDescription>
      <CardAction><ActionButton size="sm" href={ctx.href('organization', {tab: 'audit'})}>Open audit</ActionButton></CardAction>
    </CardHeader>
    <CardContent className="px-0">
      {entries.length ? <div role="region" aria-label="Recent audit entries" className="overflow-x-auto"><Table><TableHeadRow><TableRow><TableHead className="ps-6">At</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead className="pe-6">Entity</TableHead></TableRow></TableHeadRow>
        <TableBody>{entries.slice(0, 8).map((entry, index) => <TableRow key={entry.request_id ?? entry.at + index}><TableCell className="ps-6">{entry.at}</TableCell><TableCell>{entry.actor ?? 'Unknown'}</TableCell><TableCell><code>{entry.action}</code></TableCell><TableCell className="pe-6">{entry.entity ? <code>{shortId(entry.entity)}</code> : 'Unknown'}</TableCell></TableRow>)}</TableBody>
      </Table></div> : <p className={styles.muted + ' px-6'}>No audit entries.</p>}
    </CardContent>
  </Card>;
}

export function ApiHomeRoute({ctx}: ApiProps) {
  const {source, org, repo, me, role} = ctx;
  const at = (key: string) => ctx.params.get(key) ?? '';
  const windowLabel = usageWindows.includes(at('window') as typeof usageWindows[number]) ? at('window') : '30d';
  const target = org && repo ? {org, repo} : null;
  const owner = role === 'owner';
  const now = Date.now();

  const usage = useAsync(() => source.getUsage(target!, {window: windowLabel}), 'home:usage:' + org + '/' + repo + ':' + windowLabel, Boolean(target));
  const skills = useAsync(() => source.listSkills(target!, {limit: 100}), 'home:skills:' + org + '/' + repo, Boolean(target));
  const layers = useAsync(() => source.getMapLayers(target!), 'home:layers:' + org + '/' + repo, Boolean(target));
  const scopes = useAsync(() => source.getFacets(target!, {field: 'scope'}), 'home:scopes:' + org + '/' + repo, Boolean(target));
  const proposals = useAsync(() => source.listProposals(target!, {}), 'home:proposals:' + org + '/' + repo, Boolean(target));
  const imports = useAsync(() => source.listImports(target!), 'home:imports:' + org + '/' + repo, Boolean(target));
  const installations = useAsync(() => source.listInstallations(org!), 'home:installations:' + org, Boolean(org));
  // 1.3.0: `{org_base}/audit` is readable by a member too, scoped server-side to their own rows
  // (contract §4.1) — the client reads it for every signed-in role, not just an owner.
  const audit = useAsync(() => source.getAudit(org!), 'home:audit:' + org, Boolean(org));

  if (!org) return <RouteState state="empty" title="Choose an organization" description="An overview needs an organization and a repository. Start with the import wizard." action={<ActionButton tone="human" href={ctx.href('import', {step: 'organization'})}>Open Import</ActionButton>} />;
  if (!repo) return <EmptyStateBlock icon={<FolderOpenIcon aria-hidden="true" />} title="Choose a repository" description={'No repository is selected for ' + org + '. Pick one, or upload a checkout with the CLI, and the overview fills itself.'} action={{label: 'Choose a repository', href: ctx.href('import', {step: 'preview'}), tone: 'human'}} />;

  const reads = [usage, skills, layers, scopes, proposals, imports, installations];
  // The usage report is the spine of the page: the window, the coverage chip, two of the four
  // numbers and the next actions come from it. The page waits for it alone; every other block
  // arrives on its own and, when it fails, says so in place while the rest stays complete.
  if (usage.phase === 'loading' && usage.value === undefined) return <RouteState state="loading" title="Reading the overview" description="Collecting the usage window, the catalogue, proposals, imports and adapters. No number is shown before it arrives." />;
  if (usage.phase === 'error' && usage.error && usage.value === undefined) return <ApiFailure error={usage.error} onRetry={() => reads.forEach(read => read.reload())} retryLabel="Retry the overview" />;
  const pending = reads.filter(read => read.phase === 'loading' && read.value === undefined);
  const failed = reads.filter(read => read.phase === 'error' && read.value === undefined);

  const usageValue = usage.value ?? null;
  const skillsValue = skills.value ?? null;
  const proposalsValue = proposals.value?.items ?? null;
  const importsValue = imports.value ?? null;
  const installationsValue = installations.value ?? null;
  const coverage = coverageOf(usageValue);
  const observed = hasObservations(usageValue);
  const actions = nextActions({role, me, usage: usageValue, proposals: proposalsValue, imports: importsValue, installations: installationsValue, skillsTotal: skillsValue?.items.length ?? null, now});
  const blocking = actions.find(action => action.kind === 'adapter' || action.kind === 'publish' || action.kind === 'import');
  const decisions = yourDecisions(proposalsValue ?? [], usageValue?.queue ?? [], me);
  const windowText = usageValue ? 'Last ' + windowLabel + ' · ' + day(usageValue.window.from) + ' to ' + day(usageValue.window.to) : 'Last ' + windowLabel;

  return <div className={styles.route} aria-busy={pending.length > 0 || undefined}>
    {readOnly(ctx) && <DegradedNotice>Membership could not be reconfirmed. This overview is the last read of this session; nothing here can be changed until access is confirmed again.</DegradedNotice>}
    {failed.length > 0 && <PartialNotice>{failed.length + (failed.length === 1 ? ' block' : ' blocks') + ' could not be read; the rest of the page is complete. Reading failed for: ' + failed.map(read => read.error?.code ?? 'unknown').join(', ') + '.'}</PartialNotice>}
    {usageValue?.coverage && usageValue.coverage.dropped_reported > 0 && <PartialNotice>{'Adapters reported ' + usageValue.coverage.dropped_reported + ' dropped events in this window. Every count is a lower bound.'}</PartialNotice>}

    <header className={styles.context} aria-label="Window and coverage">
      <nav aria-label="Usage window" className={styles.windows}>{usageWindows.map(value => <Link key={value} to={ctx.href('home', {window: value === '30d' ? null : value})} aria-current={value === windowLabel ? 'true' : undefined} className={styles.windowLink}>{value}</Link>)}</nav>
      <span className={styles.windowText}>{windowText}</span>
      <span className={styles.coverage}><StateBadge tone={coverage.state === 'live' ? 'system' : coverage.state === 'lagging' ? 'warning' : 'neutral'}>{coverage.label}</StateBadge><small>{coverage.detail}</small></span>
      <Link to={ctx.href('usage', {window: windowLabel === '30d' ? null : windowLabel})} className={styles.contextLink}>Open in Usage &amp; quality<ArrowRightIcon aria-hidden="true" /></Link>
    </header>

    {blocking && <Alert className={styles.alert} role="status">
      <WarningCircleIcon aria-hidden="true" />
      <AlertTitle>{blocking.title}</AlertTitle>
      <AlertDescription>{blocking.detail} <Link to={actionHref(ctx, blocking.kind)}>{blocking.kind === 'adapter' ? 'Open Integrations' : blocking.kind === 'publish' ? 'Open the import' : 'Open Import'}</Link></AlertDescription>
    </Alert>}

    <Kpis ctx={ctx} usage={usageValue} skills={skillsValue} windowLabel={windowLabel} />
    <NextActions ctx={ctx} actions={actions} />
    {decisions.count > 0 && <YourDecisionsPanel ctx={ctx} decisions={decisions} />}

    {usageValue && observed ? <div className={styles.twoUp}><Funnel usage={usageValue} /><Feedback usage={usageValue} /></div>
    : <div className="px-1"><EmptyStateBlock icon={<BookOpenIcon aria-hidden="true" />} title={'No telemetry in the last ' + windowLabel} description="No adapter event and no assessment reached the ledger. Usefulness is Unknown, not zero." action={{label: 'Set up an adapter', href: ctx.href('organization', {tab: 'integrations'}), tone: 'system'}} /></div>}
    {usageValue && observed && <TopSkillsPanel ctx={ctx} usage={usageValue} />}

    <Library ctx={ctx} skills={skillsValue} layers={layers.value ?? null} scopes={scopes.value ?? null} />
    <Pipeline ctx={ctx} imports={importsValue} proposals={proposalsValue} installations={installationsValue} usage={usageValue} now={now} />
    {/* 1.3.0: the audit route now scopes a member to their own rows server-side (contract §4.1),
        so "Recent activity" is no longer owner-only; the eyebrow says which scope this reader gets. */}
    {audit.value && <Activity ctx={ctx} entries={audit.value.items} owner={owner} />}
    <p className={styles.muted}><LinkSimpleIcon aria-hidden="true" className={styles.inlineIcon} />Every number above is a count the API returned for this window.{usageValue?.previous ? ' A trend badge compares it with the equal-length window immediately before.' : ' No previous window was reported for this one, so no trend is shown.'}</p>
  </div>;
}
