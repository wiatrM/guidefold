import {useEffect, useState, type FormEvent} from 'react';
import {Link} from 'react-router-dom';
import {ArrowDown, ArrowSquareOut, Check, DownloadSimple, FileText, Funnel, GitBranch, ListChecks, ListNumbers, PencilSimple, Pulse, UsersThree, X} from '@phosphor-icons/react';
import {ActionButton, DataTable, Field, MetricRow, Panel, ProvenanceTrail, RouteState, SkillContent, SkillDiff, StateBadge, Urn} from '../Shared';
import {assessSkills, countRecommendations, queueReasonLabels, sortKeys, type Gate, type GateState, type Recommendation, type SkillHealth, type SortKey} from '../domain/skillHealth';
import {isStale} from '../api/client';
import {proposalKinds, proposalStates, queueActions} from '../api/decoders';
import {
  ApiFailure, DegradedNotice, OwnerNote, PartialNotice, RepositoryRequired, asApiError, downloadText,
  formatNumber, readOnly, stableKey, unknown, useAsync, type ApiProps,
} from './apiState';
import type {ExportPayload, FeedbackTotals, HelpedRatio, Publication, QueueAction, QueueItem, UsageSkill} from '../api/decoders';
import type {Params, View} from '../domain';
import styles from './ReviewRoutes.module.css';

// ---------------------------------------------------------------------------
// Usage · Skill health: gates, recommendation, ranking and a per-skill funnel.
// Advice only (ADR-0031 §7): the owner acts in Needs review or Proposals, never here.
// ---------------------------------------------------------------------------

const gateTone: Record<GateState, 'neutral' | 'system' | 'warning'> = {clear: 'system', attention: 'warning', low: 'neutral', partial: 'neutral', unknown: 'neutral'};
const recommendationLabels: Record<Recommendation, string> = {
  promote_up: 'Recommended: promote up', keep: 'Recommended: keep', review: 'Recommended: review', archive_candidate: 'Recommended: archive candidate',
};
const recommendationTone: Record<Recommendation, 'neutral' | 'system' | 'warning'> = {promote_up: 'system', keep: 'neutral', review: 'warning', archive_candidate: 'warning'};
const sortLabels: Record<SortKey, string> = {value: 'Value, then pull, then reach', pull: 'Pull, then reach', reach: 'Reach'};

function GateCell({gate}: {gate: Gate}) {
  return <div className={styles.gate}><span><StateBadge tone={gateTone[gate.state]}>{gate.label}</StateBadge></span><small>{gate.detail}</small></div>;
}

type HealthPanelProps = {
  skills: UsageSkill[]; queue: QueueItem[]; sort: string; eyebrow: string;
  href: (view: View, changes?: Params) => string; go: (view: View, changes?: Params) => void;
  skillHref: (item: UsageSkill) => string;
};

function SkillHealthPanel({skills, queue, sort, eyebrow, href, go, skillHref}: HealthPanelProps) {
  const known = sortKeys.includes(sort as SortKey);
  const key: SortKey = known ? sort as SortKey : 'value';
  const rows = assessSkills(skills, queue, key);
  const counts = countRecommendations(rows);
  const unknownValue = rows.filter(row => row.value.state === 'unknown').length;
  return <Panel title="Skill health" eyebrow={eyebrow} icon={<Pulse aria-hidden="true" />}>
    <ul className={styles.healthSummary} aria-label="Recommendations in this window">
      {(['promote_up', 'keep', 'review', 'archive_candidate'] as const).map(item => <li key={item}>
        <StateBadge tone={recommendationTone[item]}>{recommendationLabels[item].replace('Recommended: ', '')}</StateBadge>
        <strong>{formatNumber(counts[item])}</strong>
      </li>)}
      <li><StateBadge>Value unknown</StateBadge><strong>{formatNumber(unknownValue)}</strong></li>
    </ul>
    <div className={styles.healthOrder}>
      <Field id="health-sort" label="Order by" hint="A small sample never ranks above a row with 20 assessments on its percentage.">
        <select id="health-sort" value={key} onChange={event => go('usage', {sort: event.target.value === 'value' ? null : event.target.value})}>
          {sortKeys.map(option => <option key={option} value={option}>{sortLabels[option]}{option === 'value' ? ' (default)' : ''}</option>)}
        </select>
      </Field>
    </div>
    {sort && !known && <p className={styles.notice} role="status"><StateBadge tone="warning">Unknown order</StateBadge>{'"' + sort + '" is not one of value, pull or reach; rows are in the default order.'}</p>}
    <DataTable caption="Skill health per skill" headings={['Skill', 'Recommendation and why', 'Reach', 'Pull', 'Value', 'Health', 'Exposed → expanded → loaded → judged']}>
      {rows.map(row => <HealthRow key={row.skill.skill_id + ':' + (row.skill.revision ?? '')} row={row} href={href} skillHref={skillHref} />)}
    </DataTable>
    <p className={styles.panelNote}>A recommendation is computed in this browser from the counts in the row; it changes nothing. Promoting, keeping or archiving a skill goes through Needs review or a proposal, and load counts alone never promote a skill. Pull marked "at least" is a lower bound because some loads carry no search_id.</p>
  </Panel>;
}

function HealthRow({row, href, skillHref}: {row: SkillHealth; href: HealthPanelProps['href']; skillHref: HealthPanelProps['skillHref']}) {
  const {skill, funnel} = row;
  const act = row.recommendation === 'review' && row.openItems.length
    ? <a href="#needs-review">Decide in Needs review</a>
    : row.recommendation === 'keep' ? null
      : <Link to={href('proposals', {skill: skill.skill_id, from: 'usage'})}>{row.recommendation === 'promote_up' ? 'Propose a promotion' : 'Propose archiving'}</Link>;
  return <tr>
    <th scope="row" className={styles.skillCell}>
      <Link to={skillHref(skill)}>{skill.skill_id}</Link>
      <span className={styles.cellNote}>{skill.scope ?? 'No scope in catalog'}{skill.helped_ratio?.small_sample ? ' · small sample' : ''}</span>
    </th>
    <td>
      <div className={styles.recommendation}>
        <span><StateBadge tone={recommendationTone[row.recommendation]}>{recommendationLabels[row.recommendation]}</StateBadge></span>
        <ul className={styles.why}>{row.why.map(fact => <li key={fact}>{fact}</li>)}</ul>
        {act && <small>{act}</small>}
      </div>
    </td>
    <td><GateCell gate={row.reach} /></td>
    <td><GateCell gate={row.pull} /></td>
    <td><GateCell gate={row.value} /></td>
    <td><GateCell gate={row.health} /></td>
    <td>
      <div className={styles.funnelCell}>
        <span>{formatNumber(funnel.exposed) + ' exposed → ' + formatNumber(funnel.expanded) + ' expanded → ' + formatNumber(funnel.loaded) + ' loaded → ' + (funnel.judged === null ? 'no assessment' : formatNumber(funnel.judged) + ' judged')}</span>
        {funnel.unlinked > 0 && <small>{formatNumber(funnel.unlinked) + ' loads unlinked to any exposure'}</small>}
        {row.openItems.map(item => <small key={item.item_id}>{'Open: ' + queueReasonLabels[item.reason]}</small>)}
      </div>
    </td>
  </tr>;
}

// ---------------------------------------------------------------------------
// Hosted API routes (F16, F17, F18).
// ---------------------------------------------------------------------------

const proposalKeys = ['state', 'kind', 'scope'];
const decisionChoices = [
  {value: 'approve' as const, label: 'Approve for export', detail: 'Keep the candidate as generated and prepare the Git handoff.', icon: Check},
  {value: 'edit' as const, label: 'Approve an edited candidate', detail: 'Save your own body as the human revision.', icon: PencilSimple},
  {value: 'reject' as const, label: 'Reject', detail: 'Close this proposal; the same input is not generated again.', icon: X},
];
const terminalPublicationStates = ['published', 'superseded'];

function ProposalQueue({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const at = (key: string) => ctx.params.get(key) ?? '';
  const cursor = ctx.params.get('cursor');
  const list = useAsync(
    () => source.listProposals(target, {state: at('state') || undefined, kind: at('kind') || undefined, scope: at('scope') || undefined, cursor: cursor ?? undefined}),
    'proposals:' + org + '/' + repo + ':' + proposalKeys.map(at).join('|') + ':' + (cursor ?? ''),
    Boolean(org && repo),
  );
  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    ctx.go('proposals', {...Object.fromEntries(proposalKeys.map(key => [key, String(form.get(key) ?? '').trim() || null])), cursor: null});
  }
  const value = list.value;
  return <>
    <Panel title="Review queue" eyebrow="Candidates" icon={<ListChecks aria-hidden="true" />}>
      <form id="proposal-filters" className={styles.filters} onSubmit={applyFilters} key={ctx.params.toString()}>
        <Field id="proposal-state" label="State"><select id="proposal-state" name="state" defaultValue={at('state')}>
          <option value="">All states</option>{proposalStates.map(state => <option key={state} value={state}>{state}</option>)}
        </select></Field>
        <Field id="proposal-kind" label="Kind"><select id="proposal-kind" name="kind" defaultValue={at('kind')}>
          <option value="">All kinds</option>{proposalKinds.map(kind => <option key={kind} value={kind}>{kind}</option>)}
        </select></Field>
        <Field id="proposal-scope" label="Scope" hint="Exact scope path, for example forge.pipelines"><input id="proposal-scope" name="scope" defaultValue={at('scope')} /></Field>
        <div className={styles.filterAction}><ActionButton type="submit">Apply filters</ActionButton></div>
      </form>
      {list.phase === 'loading' && !value && <RouteState state="loading" title="Reading proposals" description="Waiting for the candidate list of this repository." />}
      {list.phase === 'error' && list.error && !value && <ApiFailure error={list.error} onRetry={list.reload} retryLabel="Retry the queue" />}
      {value && (value.items.length ? <>
        <DataTable caption="Proposals in this repository" headings={['Proposal', 'Kind', 'State', 'Scope', 'Target file']}>
          {value.items.map(item => <tr key={item.proposal_id}>
            <th scope="row" className={styles.pathCell}><Link to={ctx.href('proposals', {proposal: item.proposal_id})}>{item.proposal_id}</Link></th>
            <td>{item.kind}</td>
            <td><StateBadge tone={item.state === 'published' ? 'system' : item.state === 'rejected' ? 'warning' : 'neutral'}>{item.state}</StateBadge></td>
            <td>{item.scope ?? 'Unknown'}</td>
            <td className={styles.pathCell}><code>{item.path ?? 'Unknown'}</code></td>
          </tr>)}
        </DataTable>
        {value.next_cursor && <div className={styles.actions}><ActionButton onClick={() => ctx.go('proposals', {cursor: value.next_cursor})}>Next page</ActionButton></div>}
      </> : <RouteState state="empty" title="No proposals to review"
        description="No candidate matches these filters. An absence of candidates is a valid result; the imported sources stay readable."
        action={<ActionButton href={ctx.href('library', {})} tone="system">Browse sources</ActionButton>} />)}
    </Panel>
  </>;
}

function ExportPanel({ctx, proposalId, state, onExported}: ApiProps & {proposalId: string; state: string; onExported: () => void}) {
  const {source, org, repo} = ctx;
  const owner = ctx.role === 'owner';
  const [result, setResult] = useState<ExportPayload | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const blocked = !owner || readOnly(ctx) || busy;

  async function runExport() {
    if (blocked || !org || !repo) return;
    setBusy(true);
    setError('');
    try {
      const payload = await source.exportProposal({org, repo}, proposalId, stableKey('export', proposalId));
      setResult(payload);
      onExported();
    } catch (failure) {
      const problem = asApiError(failure);
      setError(problem.code === 'proposal_state_invalid'
        ? 'This proposal is not approved for export. Record a decision first.'
        : 'The export was not created (' + problem.code + '). Nothing was written to Git.');
    } finally {setBusy(false);}
  }

  return <Panel title="Export" eyebrow="Files for your repository" icon={<DownloadSimple aria-hidden="true" />}>
    <div className={styles.stageContent}>
      <p>Export writes nothing to Git. It returns the exact files and a patch for you to apply and review in your own repository.</p>
      {state === 'approved_for_export' && <div className={styles.actions}>
        <ActionButton id="export-patch" tone="human" disabled={blocked} onClick={runExport}><DownloadSimple aria-hidden="true" />{busy ? 'Preparing export…' : 'Create export'}</ActionButton>
      </div>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {result && <>
        <ProvenanceTrail entries={[
          {label: 'Export', value: result.export_id, code: true},
          {label: 'Base commit', value: unknown(result.base_commit), code: true},
          {label: 'Files', value: String(result.files.length)},
          {label: 'Publication', value: 'Awaiting Git', detail: 'Export is not publication; a sync must observe the file in a complete import.'},
        ]} />
        <DataTable caption="Files in this export" headings={['Path', 'SHA-256', 'Bytes']}>
          {result.files.map(file => <tr key={file.path}>
            <th scope="row" className={styles.pathCell}><code>{file.path}</code></th>
            <td className={styles.pathCell}><code>{unknown(file.sha256)}</code></td>
            <td>{new TextEncoder().encode(file.content).length}</td>
          </tr>)}
        </DataTable>
        <div className={styles.actions}>
          {result.files.map(file => <ActionButton key={file.path} onClick={() => downloadText(file.path.split('/').pop() || 'SKILL.md', file.content, 'text/markdown;charset=utf-8')}>Download {file.path.split('/').pop()}</ActionButton>)}
          {result.patch && <ActionButton onClick={() => downloadText(result.export_id + '.patch', result.patch as string, 'text/x-diff;charset=utf-8')}>Download patch</ActionButton>}
        </div>
        <p className={styles.panelNote}>Apply it from your checkout:</p>
        <pre className={styles.raw}><code>{'guidefold proposals apply ' + result.export_id + ' --write'}</code></pre>
      </>}
    </div>
  </Panel>;
}

function PublicationPanel({ctx, proposalId, active}: ApiProps & {proposalId: string; active: boolean}) {
  const {source, org, repo} = ctx;
  const [publication, setPublication] = useState<Publication | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!org || !repo || !active) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const next = await source.getProposalPublication({org, repo}, proposalId);
        if (!live) return;
        setPublication(next);
        setError('');
        // Polling stops on a terminal publication state and on unmount.
        if (!terminalPublicationStates.includes(next.state)) timer = setTimeout(() => {void poll();}, 2000);
      } catch (failure) {
        if (!live || isStale(failure)) return;
        setError('The publication state could not be read (' + asApiError(failure).code + '). Nothing is confirmed as published.');
      }
    };
    void poll();
    return () => {live = false; if (timer) clearTimeout(timer);};
  }, [source, org, repo, proposalId, active]);

  if (!active) return null;
  return <Panel title="Publication" eyebrow="Observed after Git" icon={<GitBranch aria-hidden="true" />}
    action={<StateBadge tone={publication?.state === 'published' ? 'system' : 'warning'}>{publication?.state ?? 'awaiting_git'}</StateBadge>}>
    <div className={styles.stageContent}>
      <p>{publication?.state === 'published'
        ? 'A complete import carried this file with the same SHA-256 and a snapshot was activated.'
        : publication?.state === 'superseded'
          ? 'Another revision replaced this one before it was published.'
          : 'Waiting for your Git review, merge and the next import. Nothing here is published yet.'}</p>
      <ProvenanceTrail entries={[
        {label: 'Published revision', value: unknown(publication?.published_revision_id), code: true},
        {label: 'Import', value: unknown(publication?.import_id), code: true},
        {label: 'Snapshot', value: unknown(publication?.snapshot_id), code: true},
      ]} />
      {error && <p className={styles.error} role="alert">{error}</p>}
    </div>
  </Panel>;
}

function SnapshotsPanel({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const owner = ctx.role === 'owner';
  const snapshots = useAsync(() => source.listSnapshots({org: org ?? '', repo: repo ?? ''}), 'snapshots:' + org + '/' + repo, Boolean(org && repo) && owner);
  const [reason, setReason] = useState('');
  const [confirming, setConfirming] = useState<string | null>(null);
  const [importId, setImportId] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const blocked = !owner || readOnly(ctx) || busy;
  if (!owner) return null;

  async function activate(snapshotId: string) {
    if (blocked || !org || !repo || !reason.trim()) {setError('Give the reason for this rollback before activating another snapshot.'); return;}
    setBusy(true);
    setError('');
    try {
      // The reason travels with the request: §4.4 refuses an activation without one, and it is
      // the audit row that explains the change to everyone reading this repository.
      const result = await source.activateSnapshot({org, repo}, snapshotId, reason.trim(), stableKey('activate', snapshotId, reason.trim()));
      setStatus('Snapshot ' + unknown(result.snapshot_id) + ' is now ' + (result.active ? 'active' : 'not active') + '. The reason was recorded with the activation.');
      setConfirming(null);
      snapshots.reload();
    } catch (failure) {
      const problem = asApiError(failure);
      setError(problem.code === 'graph_cycle' || problem.code === 'missing_dependency'
        ? 'Activation was refused (' + problem.code + '). The previous snapshot stays active.'
        : 'The snapshot was not activated (' + problem.code + '). The previous snapshot stays active.');
    } finally {setBusy(false);}
  }
  async function publishImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (blocked || !org || !repo) return;
    const id = importId.trim();
    if (!id) {setError('Name the import to publish.'); return;}
    setBusy(true);
    setError('');
    try {
      const job = await source.publish({org, repo}, id, stableKey('publish', id));
      setStatus('Publication job ' + job.job_id + ' was queued. A snapshot becomes active only after validation.');
      snapshots.reload();
    } catch (failure) {
      const problem = asApiError(failure);
      setError('The publication was not queued (' + problem.code + '). The active snapshot is unchanged.');
    } finally {setBusy(false);}
  }

  return <Panel title="Snapshots" eyebrow="Owner" icon={<GitBranch aria-hidden="true" />}>
    <div className={styles.stageContent}>
      <p className={styles.muted}>A snapshot is what SEARCH and USE serve. Activating an older one is a rollback; publishing an import builds a new one.</p>
      {snapshots.phase === 'loading' && !snapshots.value && <RouteState state="loading" title="Reading snapshots" description="Waiting for the snapshot list." />}
      {snapshots.phase === 'error' && snapshots.error && !snapshots.value && <ApiFailure error={snapshots.error} onRetry={snapshots.reload} retryLabel="Retry the snapshot list" />}
      {snapshots.value && (snapshots.value.length ? <DataTable caption="Snapshots of this repository" headings={['Snapshot', 'Commit', 'Skills', 'Validation', 'State', 'Action']}>
        {/* Keyed on the publication row: a build that did not finish has no snapshot id yet. */}
        {snapshots.value.map(item => <tr key={item.publication_id}>
          <th scope="row" className={styles.pathCell}>{item.snapshot_id
            ? <code>{item.snapshot_id}</code>
            : <span className={styles.muted}>No snapshot built</span>}</th>
          <td className={styles.pathCell}><code>{unknown(item.commit)}</code></td>
          <td>{item.n_skills}</td>
          <td>{item.validation
            ? (item.validation.ok ? 'Valid' : 'Failed: ' + (item.validation.findings.length ? item.validation.findings.join(', ') : unknown(item.error)))
            : 'Unknown'}</td>
          <td><StateBadge tone={item.active ? 'system' : item.state === 'failed' ? 'error' : 'neutral'}>{item.active ? 'active' : item.state}</StateBadge></td>
          <td>{item.active ? <span className={styles.muted}>Serving now</span>
            : !item.snapshot_id ? <span className={styles.muted}>Nothing to roll back to</span>
              : confirming === item.snapshot_id
                ? <ActionButton tone="human" disabled={blocked} onClick={() => {void activate(item.snapshot_id as string);}}>Confirm rollback</ActionButton>
                : <ActionButton disabled={blocked} onClick={() => {setConfirming(item.snapshot_id); setError('');}}>Roll back to this</ActionButton>}</td>
        </tr>)}
      </DataTable> : <RouteState state="empty" title="No snapshot yet" description="Publish a complete import to build the first snapshot." />)}
      {confirming && <Field id="rollback-reason" label="Reason for this rollback" hint="Kept in this browser; the API records the activation, its actor and its request id in the audit log.">
        <textarea id="rollback-reason" value={reason} onChange={event => {setReason(event.target.value); setError('');}} className={styles.reason} required />
      </Field>}
      <form className={styles.filters} onSubmit={publishImport}>
        <Field id="publish-import" label="Publish an import" hint="The import id whose files should become the next snapshot.">
          <input id="publish-import" name="import_id" value={importId} onChange={event => setImportId(event.target.value)} maxLength={64} disabled={blocked} />
        </Field>
        <div className={styles.filterAction}><ActionButton type="submit" disabled={blocked}>Queue publication</ActionButton></div>
      </form>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <p className={styles.status} role="status">{status}</p>
    </div>
  </Panel>;
}

function ProposalDetailView({ctx, proposalId}: ApiProps & {proposalId: string}) {
  const {source, org, repo} = ctx;
  const owner = ctx.role === 'owner';
  const detail = useAsync(() => source.getProposal({org: org ?? '', repo: repo ?? ''}, proposalId), 'proposal:' + org + '/' + repo + ':' + proposalId, Boolean(org && repo));
  const [decision, setDecision] = useState<'approve' | 'edit' | 'reject'>('approve');
  const [reason, setReason] = useState('');
  const [candidate, setCandidate] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [mustReread, setMustReread] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [exported, setExported] = useState(false);
  const value = detail.value;
  const degraded = readOnly(ctx, detail.phase === 'error' && Boolean(value));
  const blocked = !owner || degraded || busy || mustReread;

  if (detail.phase === 'error' && detail.error && !value) return <ApiFailure error={detail.error} onRetry={detail.reload} retryLabel="Retry this proposal" />;
  if (!value) return <RouteState state="loading" title="Reading the proposal" description="Waiting for the source, the candidate and their provenance." />;

  const body = candidate ?? value.candidate.body;
  const sourceBody = value.source_body ?? '';
  const unconfirmed = value.provenance.filter(entry => entry.needs_confirmation);
  const missingSource = value.source_body === null;

  async function record(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (blocked || !org || !repo) return;
    const text = reason.trim();
    if (!text) {setError('Every decision needs a reason. It is stored with the decision.'); return;}
    if (decision === 'edit' && !body.trim()) {setError('An edited candidate needs a body.'); return;}
    setBusy(true);
    setError('');
    try {
      const result = await source.decideProposal({org, repo}, proposalId, {
        decision, reason: text,
        candidate_body: decision === 'edit' ? body : undefined,
        expected_revision: value!.expected_revision ?? null,
      }, stableKey('decide', proposalId, value!.expected_revision, decision, text, decision === 'edit' ? body : ''));
      setStatus('Recorded: ' + result.state + '. Revision ' + (result.revision_id ?? 'not created') + '.');
      setConflict(null);
      detail.reload();
      window.requestAnimationFrame(() => document.getElementById('decision')?.focus());
    } catch (failure) {
      const problem = asApiError(failure);
      if (problem.code === 'stale_revision') {
        // The source moved on: keep the operator's text, block the save until it is read again.
        setConflict(typeof problem.details?.current_revision === 'string' ? problem.details.current_revision : 'Unknown');
        setMustReread(true);
        setError('The source changed since this candidate was generated. Your text is kept, but the decision was not saved.');
      } else if (problem.code === 'invalid_candidate_change' || problem.code === 'graph_cycle' || problem.code === 'scope_widening_not_approved') {
        setError('The decision was refused (' + problem.code + '). Nothing was saved and your text is unchanged.');
      } else {
        setError('The decision was not saved (' + problem.code + '). Your text is unchanged.');
      }
    } finally {setBusy(false);}
  }

  return <>
    {degraded && <DegradedNotice>Membership could not be reconfirmed. The source and candidate stay readable; decisions and export are unavailable.</DegradedNotice>}
    {missingSource && <PartialNotice>The source body is not part of this proposal, so the diff below compares against an empty file. Export stays available, but read the source in Git before deciding.</PartialNotice>}
    <OwnerNote role={ctx.role} />
    <section className={styles.summary} aria-label="Proposal status and evidence">
      <div className={styles.summaryHeading}>
        <div><span className={styles.eyebrow}>{value.kind} · {value.scope ?? 'Unknown scope'}</span><h2 className={styles.name}>{value.candidate.path}</h2></div>
        <StateBadge tone={value.state === 'published' ? 'system' : value.state === 'rejected' ? 'warning' : 'human'}>{value.state}</StateBadge>
      </div>
      <div className={styles.actions}>
        <a className={styles.jumpLink} href="#decision"><ArrowDown aria-hidden="true" />Jump to the decision</a>
        <Link to={ctx.href('proposals', {proposal: null})}>Back to the queue</Link>
        {value.target_skill_id && <Link to={ctx.href('skill', {skill: value.target_skill_id, revision: value.target_revision_id, tab: 'content', from: 'proposals'})}>Open the target skill</Link>}
      </div>
    </section>

    <div className={styles.comparison}>
      <Panel title="Source" eyebrow="What the candidate was built from" icon={<FileText aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          {label: 'Scope', value: value.scope ?? 'Unknown', code: true},
          {label: 'Owner from source', value: unknown(value.owner)},
          {label: 'Target revision', value: unknown(value.target_revision_id), code: true},
          {label: 'Expected revision', value: unknown(value.expected_revision), code: true, detail: 'A decision is refused if the source moved past this.'},
          {label: 'Recipe', value: value.recipe ? value.recipe.generator + ' · ' + value.recipe.version : 'Unknown', detail: value.recipe?.model ?? 'No model recorded'},
        ]} />
        {value.sources.length > 0 && <DataTable caption="Source fragments used by this candidate" headings={['Path', 'Commit', 'Lines']}>
          {value.sources.map(entry => <tr key={entry.path + ':' + (entry.sha256 ?? '')}>
            <th scope="row" className={styles.pathCell}><code>{entry.path}</code></th>
            <td className={styles.pathCell}><code>{unknown(entry.commit)}</code></td>
            <td>{entry.lines && entry.lines.length ? entry.lines.join('–') : 'Unknown'}</td>
          </tr>)}
        </DataTable>}
        <details className={styles.disclosure}><summary>Read the source body</summary>
          <pre className={styles.raw} tabIndex={0} aria-label="Source body">{sourceBody || 'The source body is not part of this proposal.'}</pre>
        </details>
      </Panel>
      <Panel title="Candidate" eyebrow="Proposed file" icon={<GitBranch aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          {label: 'Candidate path', value: value.candidate.path, code: true},
          {label: 'Candidate SHA-256', value: unknown(value.candidate.sha256), code: true},
          {label: 'Cost', value: value.cost ? value.cost.calls + ' calls · $' + value.cost.usd_certain.toFixed(4) : 'Unknown', detail: value.cost && value.cost.usd_uncertain > 0 ? 'Plus $' + value.cost.usd_uncertain.toFixed(4) + ' charged after a timeout and not counted as certain.' : undefined},
        ]} />
        <details className={styles.disclosure}><summary>Read the candidate body</summary>
          <div className={styles.bodyPreview}><SkillContent content={body} /></div>
        </details>
      </Panel>
    </div>

    <Panel title="Source to candidate" eyebrow="Line diff" icon={<ListChecks aria-hidden="true" />}>
      <SkillDiff source={sourceBody} candidate={body} />
    </Panel>

    <Panel title="Field provenance" eyebrow="Where each field came from" icon={<FileText aria-hidden="true" />}>
      {value.provenance.length ? <>
        {unconfirmed.length > 0 && <PartialNotice>{unconfirmed.length + ' fields have no exact source fragment behind them and are marked as needing confirmation.'}</PartialNotice>}
        <DataTable caption="Provenance of each candidate field" headings={['Field', 'Origin', 'Source reference', 'Confirmation']}>
          {value.provenance.map(entry => <tr key={entry.field}>
            <th scope="row">{entry.field}</th>
            <td>{entry.origin}</td>
            <td className={styles.pathCell}>{entry.source_ref ? Object.entries(entry.source_ref).map(([key, item]) => key + '=' + String(item)).join(' ') : 'Unknown'}</td>
            <td><StateBadge tone={entry.needs_confirmation ? 'warning' : 'neutral'}>{entry.needs_confirmation ? 'Needs confirmation' : 'From source'}</StateBadge></td>
          </tr>)}
        </DataTable>
      </> : <p className={styles.muted}>No field provenance is recorded for this candidate.</p>}
    </Panel>

    <div id="decision" tabIndex={-1} className={styles.decisionAnchor}>
      <Panel title="Decision" eyebrow="Owner" icon={<GitBranch aria-hidden="true" />}>
        <div className={styles.decisionContent}>
          <ol className={styles.lifecycle} aria-label="Publication lifecycle">
            {(['draft', 'approved_for_export', 'awaiting_git', 'published'] as const).map(stage =>
              <li key={stage} aria-current={value.state === stage ? 'step' : undefined}><StateBadge tone={value.state === stage ? 'human' : 'neutral'}>{stage}</StateBadge></li>)}
          </ol>
          {conflict && <div className={styles.notice} role="alert">
            <StateBadge tone="warning">Stale revision</StateBadge>
            <p>{'The source is now at revision ' + conflict + '. Read it again before saving; your text below is untouched.'}</p>
            <ActionButton onClick={() => {detail.reload(); setMustReread(false); setError('');}}>Re-read the source</ActionButton>
          </div>}
          {value.decision && <p className={styles.reasonRecord}><strong>Recorded decision</strong>{value.decision.decision} · {unknown(value.decision.reason)} · {unknown(value.decision.at)}</p>}
          {value.state === 'draft' ? <form id="decision-form" className={styles.form} onSubmit={record}>
            <fieldset disabled={blocked} className={styles.choices}>
              <legend>Review decision</legend>
              {decisionChoices.map(({value: id, label, detail: hint, icon: Icon}) => <label key={id} className={styles.choice}>
                <input type="radio" name="decision" value={id} checked={decision === id} onChange={() => setDecision(id)} />
                <Icon aria-hidden="true" />
                <span><strong>{label}</strong><span>{hint}</span></span>
              </label>)}
            </fieldset>
            {decision === 'edit' && <Field id="candidate-text" label="Candidate body" hint="Saved as a human revision. The frontmatter and scope of the candidate stay as generated.">
              <textarea id="candidate-text" name="candidate" className={styles.bodyEditor} spellCheck={false} value={body} onChange={event => setCandidate(event.target.value)} disabled={blocked} required />
            </Field>}
            <Field id="decision-reason" label="Reason for this decision" hint="Stored with the decision and shown in the audit log." error={error || undefined}>
              <textarea id="decision-reason" name="reason" className={styles.reason} value={reason} onChange={event => {setReason(event.target.value); setError('');}} disabled={blocked} required aria-invalid={Boolean(error)} />
            </Field>
            <div className={styles.actions}><ActionButton tone="human" type="submit" disabled={blocked}>{busy ? 'Saving decision…' : 'Save decision'}</ActionButton></div>
          </form> : <p className={styles.muted}>This proposal is no longer a draft, so no new decision can be recorded on it.</p>}
          <p className={styles.status} role="status">{status}</p>
        </div>
      </Panel>
    </div>

    <ExportPanel ctx={ctx} proposalId={proposalId} state={value.state} onExported={() => {setExported(true); detail.reload();}} />
    <PublicationPanel ctx={ctx} proposalId={proposalId} active={exported || value.state === 'awaiting_git' || value.state === 'published'} />
    <SnapshotsPanel ctx={ctx} />
  </>;
}

export function ApiProposalsRoute({ctx}: ApiProps) {
  const proposalId = ctx.params.get('proposal');
  if (!ctx.org || !ctx.repo) return <RepositoryRequired ctx={ctx} />;
  return <div className={styles.route}>
    {proposalId ? <ProposalDetailView key={proposalId} ctx={ctx} proposalId={proposalId} /> : <><OwnerNote role={ctx.role} /><ProposalQueue ctx={ctx} /></>}
  </div>;
}

const usageKeys = ['window', 'scope', 'skill', 'revision', 'harness'];
const queueActionLabels: Record<QueueAction, string> = {
  reviewed: 'Reviewed, no change needed',
  fixed_in_git: 'Fixed in Git',
  no_change: 'No change, keep as is',
};

/** No denominator is Unknown; a small denominator shows counts, never a percentage. */
function HelpedCell({ratio}: {ratio: HelpedRatio | null}) {
  if (!ratio || ratio.denominator === 0) return <><StateBadge>Unknown</StateBadge><span className={styles.muted}>No eligible assessment</span></>;
  if (ratio.small_sample) return <><span>{ratio.numerator} of {ratio.denominator}</span><span className={styles.muted}>Small sample; no rate is reported below 20 assessments.</span></>;
  return <span>{ratio.numerator} of {ratio.denominator} ({Math.round((ratio.numerator / ratio.denominator) * 100)}%)</span>;
}

function QueueRow({ctx, item, onDecided}: ApiProps & {item: QueueItem; onDecided: () => void}) {
  const {source, org, repo} = ctx;
  const owner = ctx.role === 'owner';
  const [action, setAction] = useState<QueueAction>('reviewed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const blocked = !owner || readOnly(ctx) || busy;

  async function decide() {
    if (blocked || !org || !repo) return;
    const text = reason.trim();
    if (!text) {setError('Say what you did. The reason is stored with the decision.'); return;}
    setBusy(true);
    setError('');
    try {
      await source.decideQueueItem({org, repo}, item.item_id, {action, reason: text}, stableKey('queue', item.item_id, action, text));
      onDecided();
    } catch (failure) {
      setError('The decision was not saved (' + asApiError(failure).code + '). The item stays open.');
    } finally {setBusy(false);}
  }

  return <tr>
    <th scope="row" className={styles.pathCell}>
      <Link to={ctx.href('skill', {skill: item.skill_id, revision: item.revision, scope: ctx.params.get('scope'), tab: 'content', from: 'usage'})}>{item.skill_id}</Link>
      <span className={styles.muted}>{item.revision ? 'Revision ' + item.revision : 'No revision recorded'}</span>
    </th>
    <td>{queueReasonLabels[item.reason]}</td>
    <td>{unknown(item.since)}</td>
    <td className={styles.pathCell}>{item.evidence && Object.keys(item.evidence).length
      ? Object.entries(item.evidence).map(([key, value]) => key + '=' + String(value)).join(' ')
      : 'Unknown'}</td>
    <td>{item.decision
      ? <><StateBadge>{queueActionLabels[item.decision.action]}</StateBadge><span className={styles.muted}>{unknown(item.decision.reason)}</span></>
      : <div className={styles.stack}>
        <Field id={'queue-action-' + item.item_id} label="Owner decision">
          <select id={'queue-action-' + item.item_id} value={action} onChange={event => setAction(event.target.value as QueueAction)} disabled={blocked}>
            {queueActions.map(value => <option key={value} value={value}>{queueActionLabels[value]}</option>)}
          </select>
        </Field>
        <Field id={'queue-reason-' + item.item_id} label="Reason" error={error || undefined}>
          <input id={'queue-reason-' + item.item_id} value={reason} onChange={event => {setReason(event.target.value); setError('');}} disabled={blocked} maxLength={200} aria-invalid={Boolean(error)} />
        </Field>
        <ActionButton disabled={blocked} onClick={() => {void decide();}}>{busy ? 'Saving…' : 'Record decision'}</ActionButton>
      </div>}</td>
  </tr>;
}

/** Usage · Delivery chart: top skills by exposures, ranked so the busiest cards read first. */
const DELIVERY_CHART_LIMIT = 8;
/** Usage · Feedback chart: below this total, `HelpedCell` already refuses a percentage (small
 * sample); the aggregate chart applies the same floor instead of inventing its own threshold. */
const FEEDBACK_SMALL_SAMPLE = 20;

/** Horizontal bar per skill: a neutral track sized to its exposures, a teal fill sized to its
 * verified loads on the same scale, so length compares skills and fill compares delivery within
 * one. Plain inline SVG (no charting library); every bar carries its exact counts as text next
 * to it, and the full numbers stay in the "Per skill" table below for anyone who wants every row. */
// SVG marks below set `fill`/`stroke` as plain presentation attributes (not the `style` prop),
// each one always a `var(--token)` string from tokens.css — never a hex value or an invented size.
function DeliveryChart({skills}: {skills: UsageSkill[]}) {
  const ranked = [...skills].sort((a, b) => b.exposures - a.exposures).slice(0, DELIVERY_CHART_LIMIT);
  const max = Math.max(0, ...ranked.map(item => item.exposures));
  if (max === 0) return null;
  return <div className={styles.deliveryChart} role="group" aria-label="Exposures and verified loads per skill, top skills by exposures">
    <div className={styles.deliveryAxis}><span>0</span><span>{formatNumber(max)} exposures · scale max</span></div>
    <ul className={styles.deliveryRows}>{ranked.map(item => {
      const trackPct = (item.exposures / max) * 100;
      const fillPct = (Math.min(item.loads_verified, item.exposures) / max) * 100;
      return <li key={item.skill_id + ':' + (item.revision ?? '')} className={styles.deliveryRow}>
        <span className={styles.deliveryLabel}>{item.skill_id}</span>
        <span className={styles.deliveryBarLine}>
          <svg className={styles.deliveryBar} viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
            <rect x={0} y={0} width={100} height={10} fill="var(--graphite-800)" />
            <rect x={0} y={0} width={trackPct} height={10} fill="var(--line-strong)" />
            <rect x={0} y={0} width={fillPct} height={10} fill="var(--survey-teal)" />
          </svg>
          <span className={styles.deliveryValue}>{formatNumber(item.loads_verified)} of {formatNumber(item.exposures)} verified</span>
        </span>
      </li>;
    })}</ul>
  </div>;
}

/** Feedback verdicts as one proportioned stacked bar plus a label/count legend. Colours reuse the
 * verdict tones already established for `StateBadge` elsewhere (helped=system, hindered=warning,
 * mixed/not_applicable=neutral) so the chart does not invent a second meaning for an existing hue. */
const feedbackSegments = [
  {key: 'helped', label: 'Helped', fill: 'var(--survey-teal)', swatch: 'legendSwatchHelped'},
  {key: 'hindered', label: 'Hindered', fill: 'var(--warning)', swatch: 'legendSwatchHindered'},
  {key: 'mixed', label: 'Mixed', fill: 'var(--steel)', swatch: 'legendSwatchMixed'},
  {key: 'not_applicable', label: 'Not applicable', fill: 'var(--stone-300)', swatch: 'legendSwatchNotApplicable'},
] as const;

/** Usage · context confirmation chart: verified loads split into confirmed context and
 * unknown context outcome. The denominator is the verified-load count, so an unknown
 * outcome is never rendered as a failed load. The per-row text is the accessible exact
 * representation; the SVG is only the compact comparison aid. */
function ContextChart({skills}: {skills: UsageSkill[]}) {
  const ranked = [...skills]
    .filter(item => item.loads_verified > 0)
    .sort((a, b) => b.loads_verified - a.loads_verified)
    .slice(0, DELIVERY_CHART_LIMIT);
  const max = Math.max(0, ...ranked.map(item => item.loads_verified));
  if (max === 0) return null;
  return <div className={styles.contextChart} role="group" aria-label="Verified loads split into confirmed and unknown context outcome, top skills by verified loads">
    <div className={styles.deliveryAxis}><span>0</span><span>{formatNumber(max)} verified loads · scale max</span></div>
    <ul className={styles.deliveryRows}>{ranked.map(item => {
      const loaded = Math.min(Math.max(item.context_loaded, 0), item.loads_verified);
      const unknownOutcome = Math.min(Math.max(item.context_unknown, 0), Math.max(item.loads_verified - loaded, 0));
      const loadedPct = (loaded / max) * 100;
      const unknownPct = (unknownOutcome / max) * 100;
      return <li key={item.skill_id + ':' + (item.revision ?? '')} className={styles.deliveryRow}>
        <span className={styles.deliveryLabel}>{item.skill_id}</span>
        <span className={styles.deliveryBarLine}>
          <svg className={styles.deliveryBar} viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
            <rect x={0} y={0} width={100} height={10} fill="var(--graphite-800)" />
            <rect x={0} y={0} width={unknownPct} height={10} fill="var(--line-strong)" />
            <rect x={0} y={0} width={loadedPct} height={10} fill="var(--survey-teal)" />
          </svg>
          <span className={styles.deliveryValue}>{formatNumber(loaded)} confirmed · {formatNumber(unknownOutcome)} unknown of {formatNumber(item.loads_verified)}</span>
        </span>
      </li>;
    })}</ul>
    <p className={styles.chartLegend}><strong>Confirmed</strong> means the adapter reported that the card reached model context. <strong>Unknown</strong> means no confirmation was available; it is not a failure.</p>
  </div>;
}

function FeedbackChart({feedback}: {feedback: FeedbackTotals}) {
  const counted = feedbackSegments.map(segment => ({...segment, value: feedback[segment.key]}));
  const total = counted.reduce((sum, segment) => sum + segment.value, 0);
  if (total === 0) return null;
  let cursor = 0;
  const bars = counted.filter(segment => segment.value > 0).map(segment => {
    const width = (segment.value / total) * 100;
    const bar = {...segment, x: cursor, width};
    cursor += width;
    return bar;
  });
  return <div className={styles.feedbackChart}>
    <svg viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label={`Feedback verdicts out of ${total} assessments: ${counted.map(segment => `${segment.label} ${segment.value}`).join(', ')}`}>
      {bars.map(bar => <rect key={bar.key} x={bar.x} y={0} width={bar.width} height={10} fill={bar.fill} stroke="var(--graphite-900)" strokeWidth={0.4} />)}
    </svg>
    <ul className={styles.feedbackLegend}>{counted.map(segment => <li key={segment.key}>
      <span className={[styles.legendSwatch, styles[segment.swatch]].join(' ')} aria-hidden="true" />
      <span>{segment.label}</span><strong>{formatNumber(segment.value)}</strong>
    </li>)}</ul>
    <p className={styles.muted}>{total < FEEDBACK_SMALL_SAMPLE
      ? `${formatNumber(total)} assessments; no rate is reported below ${FEEDBACK_SMALL_SAMPLE}.`
      : `${formatNumber(total)} assessments recorded.`}</p>
  </div>;
}

/** Window values the contract accepts (API-CONTRACT §4.6); anything else is `invalid_request`. */
const usageWindows = ['7d', '30d', '90d'] as const;

/** "n of d" below the floor, "n of d (p%)" from the floor up. The floor is the contract's `small_sample`. */
function shareText(numerator: number, denominator: number, smallSample: boolean): string {
  const counts = formatNumber(numerator) + ' of ' + formatNumber(denominator);
  return smallSample ? counts : counts + ' (' + Math.round((numerator / denominator) * 100) + '%)';
}

/** ISO timestamp to its calendar day; an absent bound stays Unknown. */
function formatDay(iso: string | null): string {
  if (!iso) return 'Unknown';
  const day = iso.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : iso;
}

/** A row with no verified load: the reason differs when nothing was even exposed. */
function zeroLoadsLabel(item: UsageSkill): string {
  return item.exposures > 0 ? 'Exposed but never loaded' : 'No verified load in this window';
}

/** Ranking rule (PRODUCT-PIVOT §9 AC3): only rows with a helped share on at least 20 helped-or-hindered
 * assessments are ranked; the order is helped share, then the larger denominator, then the URN. Rows
 * with fewer assessments are not "worse", they are unranked, and the page says how many there are. */
export function rankSkills(skills: UsageSkill[]): {ranked: UsageSkill[]; unranked: UsageSkill[]} {
  const ranked = skills.filter(item => item.helped_ratio && !item.helped_ratio.small_sample && item.helped_ratio.denominator > 0)
    .sort((a, b) => {
      const ra = a.helped_ratio!, rb = b.helped_ratio!;
      const share = rb.numerator / rb.denominator - ra.numerator / ra.denominator;
      if (share !== 0) return share;
      if (rb.denominator !== ra.denominator) return rb.denominator - ra.denominator;
      return a.skill_id.localeCompare(b.skill_id);
    });
  const unranked = skills.filter(item => item.helped_ratio && item.helped_ratio.small_sample);
  return {ranked, unranked};
}

export interface TeamRow {
  scope: string | null; owners: string[]; skills: number;
  exposures: number; loads_verified: number; context_loaded: number; use_episodes: number;
  helped: number; hindered: number; attention: number;
}

/** One row per scope, which is the unit a team owns (a scope has one CODEOWNER). Sums are sums of
 * the rows shown; helped and hindered are added so the team share uses the same floor as a skill. */
export function groupByScope(skills: UsageSkill[]): TeamRow[] {
  const groups = new Map<string | null, TeamRow>();
  for (const item of skills) {
    let row = groups.get(item.scope);
    if (!row) {
      row = {scope: item.scope, owners: [], skills: 0, exposures: 0, loads_verified: 0, context_loaded: 0, use_episodes: 0, helped: 0, hindered: 0, attention: 0};
      groups.set(item.scope, row);
    }
    row.skills += 1;
    row.exposures += item.exposures;
    row.loads_verified += item.loads_verified;
    row.context_loaded += item.context_loaded;
    row.use_episodes += item.use_episodes;
    row.helped += item.feedback?.helped ?? 0;
    row.hindered += item.feedback?.hindered ?? 0;
    if (item.zero_loads && item.exposures > 0) row.attention += 1;
    if ((item.feedback?.hindered ?? 0) > 0) row.attention += 1;
    if (item.owner && !row.owners.includes(item.owner)) row.owners.push(item.owner);
  }
  return [...groups.values()].sort((a, b) => b.exposures - a.exposures || (a.scope ?? '').localeCompare(b.scope ?? ''));
}

function TeamShare({helped, hindered}: {helped: number; hindered: number}) {
  const denominator = helped + hindered;
  if (denominator === 0) return <><StateBadge>Unknown</StateBadge><span className={styles.muted}>No helped or hindered assessment</span></>;
  return <span>{shareText(helped, denominator, denominator < FEEDBACK_SMALL_SAMPLE)}</span>;
}

function skillHref(ctx: ApiProps['ctx'], item: UsageSkill) {
  return ctx.href('skill', {skill: item.skill_id, revision: item.revision, scope: ctx.params.get('scope') || null, tab: 'content', from: 'usage'});
}

/** Top skills of this repository in the window. A rank is earned by assessed helpfulness, never by
 * exposure or load counts: being served often is delivery, not value (PRODUCT-PIVOT §9). */
function TopSkillsPanel({ctx, skills, window}: ApiProps & {skills: UsageSkill[]; window: string}) {
  const {ranked, unranked} = rankSkills(skills);
  const withoutFeedback = skills.length - ranked.length - unranked.length;
  return <Panel title="Top skills" eyebrow={'Helped share on 20 or more assessments · last ' + window} icon={<ListNumbers aria-hidden="true" />}
    action={<StateBadge tone={ranked.length ? 'system' : 'neutral'}>{ranked.length} ranked</StateBadge>}>
    {ranked.length ? <DataTable caption="Skills ranked by helped share" headings={['Rank', 'Skill', 'Team', 'Owner', 'Helped', 'Applied episodes', 'Context confirmed']}>
      {ranked.map((item, index) => <tr key={item.skill_id + ':' + (item.revision ?? '')}>
        <td>{index + 1}</td>
        <th scope="row" className={styles.pathCell}><Link to={skillHref(ctx, item)}>{item.skill_id}</Link></th>
        <td>{item.scope ?? 'No scope in catalog'}</td>
        <td>{unknown(item.owner)}</td>
        <td>{shareText(item.helped_ratio!.numerator, item.helped_ratio!.denominator, false)}</td>
        <td>{formatNumber(item.use_episodes)}</td>
        <td>{formatNumber(item.context_loaded)} of {formatNumber(item.loads_verified)}</td>
      </tr>)}
    </DataTable> : <div className={styles.queueEmpty}>
      <StateBadge>No rank yet</StateBadge>
      <p>No skill has 20 helped-or-hindered assessments in this window, so no rank is earned. Counts per skill are in the table below; a small sample is not a low score.</p>
    </div>}
    <p className={styles.panelNote}>
      {formatNumber(unranked.length)} {unranked.length === 1 ? 'skill has' : 'skills have'} assessments below the 20 floor and no rank. {formatNumber(withoutFeedback)} {withoutFeedback === 1 ? 'has' : 'have'} no assessment at all. A rank compares assessed episodes, not people (no per-person breakdown exists).
    </p>
  </Panel>;
}

/** What each team sees first: its own scope, in one row, with the two things that need attention. */
function ByTeamPanel({skills}: {skills: UsageSkill[]}) {
  const rows = groupByScope(skills);
  return <Panel title="By team" eyebrow="One row per scope; a scope has one owner" icon={<UsersThree aria-hidden="true" />}>
    <DataTable caption="Delivery and feedback per scope" headings={['Team (scope)', 'Owner', 'Skills', 'Exposed', 'Loaded', 'Context confirmed', 'Applied episodes', 'Helped', 'Needs attention']}>
      {rows.map(row => <tr key={row.scope ?? ' '}>
        <th scope="row" className={styles.pathCell}>{row.scope ?? <span className={styles.muted}>No scope in catalog</span>}</th>
        <td>{row.owners.length ? row.owners.join(', ') : 'Unknown'}</td>
        <td>{formatNumber(row.skills)}</td>
        <td>{formatNumber(row.exposures)}</td>
        <td>{formatNumber(row.loads_verified)}</td>
        <td>{formatNumber(row.context_loaded)}</td>
        <td>{formatNumber(row.use_episodes)}</td>
        <td><TeamShare helped={row.helped} hindered={row.hindered} /></td>
        <td>{row.attention ? <StateBadge tone="warning">{formatNumber(row.attention)}</StateBadge> : <span className={styles.muted}>None observed</span>}</td>
      </tr>)}
    </DataTable>
    <p className={styles.panelNote}>Needs attention counts skills exposed but never loaded and skills with a hindered assessment. Unknown scope means the ledger saw a skill the catalog does not know.</p>
  </Panel>;
}

export function ApiUsageRoute({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const at = (key: string) => ctx.params.get(key) ?? '';
  const report = useAsync(
    () => source.getUsage(target, {
      window: at('window') || undefined, scope: at('scope') || undefined, skillId: at('skill') || undefined,
      revision: at('revision') || undefined, harness: at('harness') || undefined,
    }),
    'usage:' + org + '/' + repo + ':' + usageKeys.map(at).join('|'),
    Boolean(org && repo),
  );
  const [exportStatus, setExportStatus] = useState('');
  const value = report.value;
  const degraded = readOnly(ctx, report.phase === 'error' && Boolean(value));

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    ctx.go('usage', Object.fromEntries(usageKeys.map(key => [key, String(form.get(key) ?? '').trim() || null])));
  }
  async function exportReport(format: 'csv' | 'json') {
    if (!org || !repo) return;
    setExportStatus('');
    try {
      const text = await source.exportUsage({org, repo}, {format, window: at('window') || undefined});
      downloadText('usage-' + repo + '.' + format, text, format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8');
      setExportStatus('Downloaded the ' + format.toUpperCase() + ' report for the current window. Filters other than the window are not applied to the export.');
    } catch (failure) {
      setExportStatus('The export failed (' + asApiError(failure).code + '). Nothing was downloaded.');
    }
  }

  if (!org || !repo) return <RepositoryRequired ctx={ctx} />;
  if (report.phase === 'error' && report.error && !value) return <ApiFailure error={report.error} onRetry={report.reload} retryLabel="Retry this report" />;
  if (!value) return <RouteState state="loading" title="Reading the usage report" description="Waiting for the aggregate over the selected window. No number is shown before it arrives." />;

  const totals = value.totals;
  const feedback = totals.feedback;
  // Feedback recorded in the UI arrives without any adapter event, so "nothing observed" must
  // include it: a judged skill is an observation even when no card was ever delivered.
  const noObservations = totals.exposures === 0 && totals.loads_verified === 0 && totals.use_reported === 0
    && totals.use_observed === 0 && (feedback?.n ?? 0) === 0;
  const open = value.queue.filter(item => !item.decision);
  const windowLabel = at('window') || '30d';
  const taskIds = value.coverage?.task_ids_present ?? false;
  const helpedDenominator = (feedback?.helped ?? 0) + (feedback?.hindered ?? 0);
  const activeFilters: {label: string; value: string}[] = [];
  if (at('scope')) activeFilters.push({label: 'Scope', value: at('scope')});
  if (at('skill')) activeFilters.push({label: 'Skill', value: at('skill')});
  if (at('revision')) activeFilters.push({label: 'Revision', value: at('revision')});
  if (at('harness')) activeFilters.push({label: 'Harness', value: at('harness')});

  return <div className={styles.route}>
    {degraded && <DegradedNotice>Membership could not be reconfirmed. This is the last report read in this session and no owner decision can be recorded.</DegradedNotice>}
    {value.coverage && value.coverage.dropped_reported > 0 && <PartialNotice>{'Adapters reported ' + value.coverage.dropped_reported + ' dropped events in this window. Every count below is a lower bound.'}</PartialNotice>}
    <Panel id="needs-review" title="Needs review" icon={<ListChecks aria-hidden="true" />} action={<StateBadge tone={open.length ? 'warning' : 'neutral'}>{open.length} open</StateBadge>}>
      {value.queue.length ? <DataTable caption="Skills that need an owner decision" headings={['Skill and revision', 'Reason', 'Since', 'Evidence', 'Owner decision']}>
        {value.queue.map(item => <QueueRow key={item.item_id} ctx={ctx} item={item} onDecided={report.reload} />)}
      </DataTable> : <div className={styles.queueEmpty}>
        <StateBadge>No observations</StateBadge>
        <p>No drift, feedback or dependency problem is recorded for this repository. Missing telemetry does not prove a skill is unused or correct.</p>
      </div>}
      <OwnerNote role={ctx.role} />
    </Panel>

    <Panel title="From delivery to value" eyebrow={'Last ' + windowLabel + ' · ' + formatDay(value.window.from) + ' to ' + formatDay(value.window.to)} icon={<Funnel aria-hidden="true" />}>
      {noObservations ? <div className={styles.queueEmpty}>
        <StateBadge>No observations</StateBadge>
        <p>No adapter event and no assessment reached the ledger for this window and these filters. Every step below is Unknown, not zero.</p>
      </div> : <MetricRow layout="funnel" items={[
          {label: 'Exposed', value: formatNumber(totals.exposures), detail: 'Cards an adapter placed into harness context. A SEARCH response alone is not an exposure.'},
          {label: 'Loaded', value: formatNumber(totals.loads_verified), detail: totals.exposures > 0 ? shareText(totals.loads_verified, totals.exposures, false) + ' of exposed cards had a verified body load' : 'Verified body loads; nothing was exposed in this window'},
          {label: 'Context confirmed', value: formatNumber(totals.context_loaded), detail: formatNumber(totals.context_unknown) + ' verified loads have an unknown context outcome; unknown is not a failure'},
          {label: 'Applied · reported / observed', value: formatNumber(totals.use_reported) + ' / ' + formatNumber(totals.use_observed), detail: taskIds ? formatNumber(totals.use_episodes) + ' task-linked episodes; an HTTP 200 on USE is neither' : 'No task identifiers in this window, so episodes cannot be counted'},
          {label: 'Helped', value: helpedDenominator > 0 ? shareText(feedback!.helped, helpedDenominator, helpedDenominator < FEEDBACK_SMALL_SAMPLE) : 'Unknown', detail: feedback
            ? (taskIds && totals.use_episodes > 0
              ? formatNumber(feedback.n) + ' assessed of ' + formatNumber(totals.use_episodes) + ' applied episodes; helped over helped plus hindered'
              : formatNumber(feedback.n) + ' assessments; feedback coverage needs task identifiers')
            : 'No assessment recorded; not 0%'},
        ]} />}
    </Panel>

    {!noObservations && <TopSkillsPanel ctx={ctx} skills={value.skills} window={windowLabel} />}
    {!noObservations && value.skills.length > 0 && <SkillHealthPanel skills={value.skills} queue={value.queue} sort={at('sort')} href={ctx.href} go={ctx.go} skillHref={item => skillHref(ctx, item)} eyebrow={'Last ' + windowLabel + ' · four gates and a recommendation per skill'} />}
    {!noObservations && value.skills.length > 0 && <ByTeamPanel skills={value.skills} />}

    {!noObservations && <Panel title="Delivery and feedback" eyebrow="Exposures, verified loads and verdicts" icon={<ListChecks aria-hidden="true" />}>
      <ContextChart skills={value.skills} />
      <DeliveryChart skills={value.skills} />
      {feedback && <FeedbackChart feedback={feedback} />}
      {!feedback && <p className={styles.muted}>No feedback assessment is recorded for this window.</p>}
    </Panel>}

    <Panel title="Observation context" eyebrow="Window, scope, skill, revision and harness" icon={<FileText aria-hidden="true" />}>
      <form key={ctx.params.toString()} id="usage-filters" className={styles.filters} onSubmit={applyFilters}>
        <Field id="usage-window" label="Window" hint="Counted back from the newest event the ledger received">
          <select id="usage-window" name="window" defaultValue={usageWindows.includes(at('window') as typeof usageWindows[number]) ? at('window') : ''}>
            <option value="">30d (default)</option>
            {usageWindows.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </Field>
        <Field id="usage-scope" label="Scope"><input id="usage-scope" name="scope" defaultValue={at('scope')} /></Field>
        <Field id="usage-skill" label="Skill" hint="Skill URN"><input id="usage-skill" name="skill" defaultValue={at('skill')} /></Field>
        <Field id="usage-revision" label="Revision" hint="Catalog or card revision"><input id="usage-revision" name="revision" defaultValue={at('revision')} spellCheck={false} /></Field>
        <Field id="usage-harness" label="Harness"><input id="usage-harness" name="harness" defaultValue={at('harness')} /></Field>
        <div className={styles.filterAction}><ActionButton type="submit">Apply filters</ActionButton></div>
      </form>
      {activeFilters.length > 0 && <div className={styles.contextSummary}>
        <p role="status">Filtered to {activeFilters.map(entry => `${entry.label} ${entry.value}`).join(', ')}.</p>
        <ActionButton href={ctx.href('usage', {scope: null, skill: null, revision: null, harness: null})}>Clear filters</ActionButton>
      </div>}
      <ProvenanceTrail entries={[
        {label: 'Window', value: formatDay(value.window.from) + ' to ' + formatDay(value.window.to), detail: 'Watermark ' + unknown(value.window.watermark) + ': the newest event received; a late event lands in the window it occurred in.'},
        {label: 'Events received', value: value.coverage ? formatNumber(value.coverage.events_received) : 'Unknown', detail: value.coverage && value.coverage.dropped_reported > 0 ? formatNumber(value.coverage.dropped_reported) + ' reported dropped by adapters' : 'No drops reported'},
        {label: 'Oldest lag', value: value.coverage?.oldest_lag_s != null ? value.coverage.oldest_lag_s + ' s' : 'Unknown', detail: 'Worst lag any adapter reported; Unknown without a health row.'},
        {label: 'Task identifiers', value: value.coverage ? (taskIds ? 'Present' : 'Absent') : 'Unknown', detail: 'Without them, episodes and feedback coverage cannot be counted.'},
      ]} />
      <div className={styles.actions}>
        <ActionButton onClick={() => {void exportReport('csv');}}>Export CSV</ActionButton>
        <ActionButton onClick={() => {void exportReport('json');}}>Export JSON</ActionButton>
      </div>
      <p className={styles.status} role="status">{exportStatus}</p>
    </Panel>

    <Panel title="Per skill" eyebrow="Every count, one row per skill and revision" icon={<ListChecks aria-hidden="true" />}>
      {value.skills.length ? <DataTable caption="Delivery and outcome per skill" headings={['Skill', 'Team (scope)', 'Owner', 'Revision', 'Exposed', 'Loaded', 'Context confirmed', 'Applied reported / observed', 'Helped']}>
        {value.skills.map(item => <tr key={item.skill_id + ':' + (item.revision ?? '')}>
          <th scope="row" className={styles.pathCell}>
            <Link to={skillHref(ctx, item)}>{item.skill_id}</Link>
            {item.zero_loads && <span className={styles.muted}>{zeroLoadsLabel(item)}</span>}
          </th>
          <td>{item.scope ?? <span className={styles.muted}>No scope in catalog</span>}</td>
          <td>{unknown(item.owner)}</td>
          <td className={styles.pathCell}><code>{unknown(item.revision)}</code></td>
          <td>{formatNumber(item.exposures)}</td>
          <td>{formatNumber(item.loads_verified)}</td>
          <td>{formatNumber(item.context_loaded)}</td>
          <td>{formatNumber(item.use_reported)} / {formatNumber(item.use_observed)}</td>
          <td><HelpedCell ratio={item.helped_ratio} /></td>
        </tr>)}
      </DataTable> : <div className={styles.queueEmpty}>
        <StateBadge>No observations</StateBadge>
        <p>No adapter event arrived for this window and these filters. Usefulness is Unknown, not zero.</p>
      </div>}
    </Panel>

    <Panel title="Adapter health" eyebrow="Reported by installations" icon={<GitBranch aria-hidden="true" />}>
      {value.health && value.health.adapters.length ? <DataTable caption="Adapter health per harness" headings={['Harness', 'Adapter version', 'Capabilities', 'Last seen', 'Lag', 'Dropped']}>
        {value.health.adapters.map(adapter => <tr key={adapter.harness}>
          <th scope="row">{adapter.harness}</th>
          <td>{unknown(adapter.adapter_version)}</td>
          <td>{adapter.capabilities && adapter.capabilities.length ? adapter.capabilities.join(', ') : 'Unknown'}</td>
          <td>{unknown(adapter.last_seen_at)}</td>
          <td>{adapter.lag_s != null ? adapter.lag_s + ' s' : 'Unknown'}</td>
          <td>{adapter.dropped != null ? formatNumber(adapter.dropped) : 'Unknown'}</td>
        </tr>)}
      </DataTable> : <p className={styles.muted}>No adapter reported health for this repository. An absent row is Unknown, not healthy.</p>}
    </Panel>
  </div>;
}
