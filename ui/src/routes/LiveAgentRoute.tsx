import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { LightningIcon, ListChecksIcon, PlayIcon, TerminalIcon } from '@phosphor-icons/react';
import { ActionButton, DataTable, IconTile, Panel, ProvenanceTrail, RouteState, StateBadge } from '../Shared';
import { isStale, type ApiError } from '../api/client';
import { ApiFailure, DegradedNotice, OwnerNote, PartialNotice, asApiError, shortId, unknown, useAsync, type ApiProps } from './apiState';
import type { LiveRun, LiveRunEvent, LiveRunState, LiveRunTarget, LiveRunTargetPhase, LiveRunTargetState } from '../api/decoders';
import styles from './LiveAgentRoute.module.css';

const runStateTone: Record<LiveRunState, 'neutral' | 'system' | 'warning' | 'error'> = {
  queued: 'neutral', running: 'system', succeeded: 'system', partial: 'warning', failed: 'error', cancelled: 'neutral',
};
const targetStateTone: Record<LiveRunTargetState, 'neutral' | 'system' | 'warning' | 'error'> = {
  queued: 'neutral', running: 'system', done: 'system', failed: 'error', skipped: 'warning',
};
const phaseLabel: Record<LiveRunTargetPhase, string> = { fetch: 'Fetching', parse: 'Parsing', propose: 'Proposing', done: 'Done' };
const cancellableStates: LiveRunState[] = ['queued', 'running'];
/** A run that ended without succeeding, so a plain badge must never read as a green tick. */
const unsuccessfulStates: LiveRunState[] = ['partial', 'failed', 'cancelled'];

/**
 * The active or most recently opened run: its per-repository state beside the event log, polled
 * from `GET …/live/runs/{id}/events` (contract §4.9). Keyed by `runId` from the parent, so
 * switching runs remounts this with a fresh cursor.
 */
function LiveRunPanel({ ctx, runId }: ApiProps & { runId: string }) {
  const { source, org, role } = ctx;
  const owner = role === 'owner';
  const [run, setRun] = useState<LiveRun | null>(null);
  const [targets, setTargets] = useState<LiveRunTarget[]>([]);
  const [events, setEvents] = useState<LiveRunEvent[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [cancelStatus, setCancelStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const afterRef = useRef(0);

  useEffect(() => {
    if (!org) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const [detail, page] = await Promise.all([
          source.getLiveRun(org, runId),
          source.getLiveRunEvents(org, runId, afterRef.current),
        ]);
        if (!live) return;
        setRun(detail.run);
        setTargets(detail.targets);
        // An empty page is normal (contract §4.9) and neither stops the poll nor renders as an
        // error; only the response's own `done` does that.
        if (page.items.length) setEvents(current => [...current, ...page.items]);
        afterRef.current = page.next_after;
        setError(null);
        setDone(page.done);
        if (!page.done) timer = setTimeout(() => { void poll(); }, 1000);
      } catch (failure) {
        if (!live || isStale(failure)) return;
        setError(asApiError(failure));
      }
    };
    void poll();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [source, org, runId, attempt]);

  async function cancel() {
    if (!org || busy || !run) return;
    setBusy(true);
    try {
      const updated = await source.cancelLiveRun(org, runId, 'live-run-cancel:' + org + ':' + runId);
      setRun(updated);
      setCancelStatus('Run cancelled.');
    } catch (failure) {
      const code = asApiError(failure).code;
      setCancelStatus(code === 'live_run_not_cancellable' ? 'This run already finished; cancelling changed nothing.' : 'The run was not cancelled (' + code + ').');
    } finally { setBusy(false); }
  }

  if (!run && error) return <ApiFailure error={error} onRetry={() => setAttempt(current => current + 1)} retryLabel="Retry this run" />;
  if (!run) return <RouteState state="loading" title="Reading the run" description="Waiting for the first status of this run." />;

  const finished = Boolean(run.finished_at);

  return <>
    {error && <DegradedNotice>{'Showing the last read status; the next update could not be read (' + error.code + ').'}</DegradedNotice>}
    {run.state === 'partial' && <PartialNotice>{run.counts.failed + ' of ' + run.counts.targets + ' repositories failed and ' + run.counts.skipped + ' were skipped.'}</PartialNotice>}
    {run.state === 'cancelled' && <PartialNotice>This run was cancelled before it finished. Repositories it had not yet reached were left untouched.</PartialNotice>}
    {run.state === 'failed' && <PartialNotice>{'This run failed' + (run.error ? ' (' + run.error + ')' : '') + '. Nothing further ran after the point of failure.'}</PartialNotice>}
    <Panel title={'Run ' + shortId(run.run_id)} eyebrow="Live Agent" icon={<LightningIcon weight="regular" aria-hidden="true" />}
      action={<>
        <StateBadge tone={runStateTone[run.state]}>{run.state}</StateBadge>
        {owner && cancellableStates.includes(run.state) && <ActionButton size="sm" disabled={busy} onClick={() => { void cancel(); }}>Cancel run</ActionButton>}
      </>}>
      <ProvenanceTrail entries={[
        { label: 'Provider', value: run.provider },
        { label: 'Model', value: run.model, code: true },
        { label: 'Started', value: unknown(run.started_at) },
        { label: 'Finished', value: unknown(run.finished_at) },
        { label: 'Cost', value: (run.cost.usd_estimated ? '~' : '') + '$' + run.cost.usd.toFixed(4), detail: run.cost.usd_estimated ? 'At least one provider response carried no usage figure; this is an estimate.' : 'Measured from provider usage.' },
        { label: 'Error', value: unknown(run.error) },
      ]} />
      {cancelStatus && <p className={styles.feedback} role="status">{cancelStatus}</p>}
    </Panel>
    {finished && <Panel title="What this run left behind" eyebrow="Summary" tone="quiet" icon={<ListChecksIcon weight="regular" aria-hidden="true" />}>
      {run.summary.skills_indexed === 0 && run.summary.proposals_created === 0
        ? <p className={styles.help}>{unsuccessfulStates.includes(run.state)
          ? 'This run did not finish successfully and left nothing behind: no skills were indexed and no proposals were created.'
          : 'This run indexed no skills and created no consolidation proposals. The skill library and the proposal queue are unchanged.'}</p>
        : <>
          <p>
            <strong>{run.summary.skills_indexed}</strong> skill{run.summary.skills_indexed === 1 ? '' : 's'} indexed into the catalog
            {run.summary.proposals_created > 0
              ? <>, and <strong>{run.summary.proposals_created}</strong> consolidation proposal{run.summary.proposals_created === 1 ? '' : 's'} {run.summary.proposals_created === 1 ? 'is' : 'are'} waiting in review.</>
              : ', and no consolidation proposals were created.'}
          </p>
          {run.summary.proposals_created > 0 && <ActionButton href={ctx.href('proposals', { kind: 'consolidation' })} tone="human">Review proposals</ActionButton>}
        </>}
    </Panel>}
    <div className={styles.twoColumns}>
      <Panel title="Repositories" eyebrow="Per-repository progress" tone="quiet" icon={<ListChecksIcon weight="regular" aria-hidden="true" />}>
        {targets.length === 0
          ? <p className={styles.help}>No repository is in scope for this run.</p>
          : <DataTable flush caption="Repositories in this run" headings={['Repository', 'Phase', 'Skills', 'Proposals', 'State', 'Detail']}>
            {targets.map(target => <tr key={target.repo_id}>
              <th scope="row"><code>{target.repo_id}</code></th>
              <td>{phaseLabel[target.phase]}</td>
              <td>{target.skills}</td>
              <td>{target.proposals}</td>
              <td><StateBadge tone={targetStateTone[target.state]}>{target.state}</StateBadge></td>
              <td>{target.state === 'skipped' && target.error === 'github_app_not_configured' ? 'No GitHub App installed for this repository.' : unknown(target.error)}</td>
            </tr>)}
          </DataTable>}
      </Panel>
      <Panel title="Event log" eyebrow={done ? 'Finished' : 'Updating roughly every second'} tone="quiet" icon={<TerminalIcon weight="regular" aria-hidden="true" />}>
        {events.length === 0
          ? <p className={styles.help}>No events reported yet.</p>
          // Each event's `payload.text` is a server-composed, ready-to-print sentence (contract
          // §5.5a): printed verbatim, never reconstructed from `event.type` on the client, so a
          // second person reading the same run through the API sees the same words.
          : <pre className={styles.transcript}>{events.map(event => <code key={event.seq} className={styles.transcriptLine}>{event.payload.text}</code>)}</pre>}
      </Panel>
    </div>
  </>;
}

/** Contract §4.9 (ADR-0046, 1.6.0): one button, no fields; while it runs, a per-repository
 * status list and event log; once it finishes, what it left in the catalog and the review queue. */
export function ApiLiveAgentRoute({ ctx }: ApiProps) {
  const { source, org, role } = ctx;
  const owner = role === 'owner';
  const runId = ctx.params.get('run');
  const credentials = useAsync(() => source.listCredentials(org ?? ''), 'credentials:' + org, Boolean(org));
  const runs = useAsync(() => source.listLiveRuns(org ?? ''), 'live-runs:' + org, Boolean(org));

  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  async function start() {
    if (!org || busy) return;
    setBusy(true);
    setFormError('');
    try {
      // No payload varies between presses (the request body is always `{}`), so the idempotency
      // key itself has to be unique per press — a stable, content-derived key would make every
      // run after the first replay the first run's stored response byte for byte (contract §3).
      const key = 'live-run:' + org + ':' + Date.now().toString(36) + Math.random().toString(36).slice(2);
      const created = await source.startLiveRun(org, key);
      runs.reload();
      ctx.go('live', { run: created.run_id });
    } catch (error) {
      const failure = asApiError(error);
      setFormError(
        failure.code === 'live_run_already_active'
          ? 'This organization already has a run in progress. Open it below, or cancel it before starting another.'
          : failure.code === 'model_credential_missing'
            ? 'This organization has no stored model key any more. Add one in Model keys before starting a run.'
            : 'The run was not started (' + failure.code + ').',
      );
    } finally { setBusy(false); }
  }

  if (!org) return <RouteState state="empty" title="No organization selected" description="Choose an organization before running the Live Agent." action={<ActionButton href={ctx.href('import', { step: 'organization' })} tone="system">Choose an organization</ActionButton>} />;

  // Only a *confirmed* absence replaces the Start button: while the key list is still loading or
  // failed to read, the button stays (disabled during loading) so a slow read never flashes
  // "No key" for an organization that in fact has one; the server's own `model_credential_missing`
  // still catches a key removed in the gap between this read and the submit.
  const noKeyConfirmed = credentials.phase === 'ready' && (credentials.value?.length ?? 0) === 0;

  return <div className={styles.route}>
    <OwnerNote role={role} />
    <Panel title="Live Agent" eyebrow="ADR-0046">
      <div className={styles.lead}>
        <IconTile icon={<LightningIcon weight="duotone" />} size="xl" tone="system" />
        <div className={styles.leadBody}>
          <p>Reads every connected repository, refreshes the skill library, and proposes consolidations where skills duplicate or contradict each other. Nothing to fill in &mdash; it always does the same thing, for all connected repositories.</p>
          {!owner ? null : noKeyConfirmed
            ? <div className={styles.notice} role="status">
              <StateBadge tone="warning">No key</StateBadge>
              <p>This organization has no stored model key. <Link to={ctx.href('organization', { tab: 'keys' })}>Add one in Model keys</Link> before starting a run.</p>
            </div>
            : <ActionButton tone="human" disabled={busy || credentials.phase === 'loading'} onClick={() => { void start(); }}>
              <PlayIcon weight="regular" aria-hidden="true" />Start run
            </ActionButton>}
          {formError && <p className={styles.feedback} role="alert">{formError}</p>}
        </div>
      </div>
    </Panel>

    <Panel title="Recent runs" eyebrow="This organization" tone="quiet" icon={<ListChecksIcon weight="regular" aria-hidden="true" />}>
      {runs.phase === 'loading' && <RouteState state="loading" title="Reading recent runs" description="Waiting for this organization's run history." />}
      {runs.phase === 'error' && runs.error && <ApiFailure error={runs.error} onRetry={runs.reload} retryLabel="Retry recent runs" />}
      {runs.phase === 'ready' && (runs.value?.items.length
        ? <DataTable flush caption="Recent Live Agent runs" headings={['Run', 'State', 'Skills', 'Proposals', 'Started']}>
          {runs.value.items.map(item => <tr key={item.run_id}>
            <th scope="row"><Link to={ctx.href('live', { run: item.run_id })}>{shortId(item.run_id)}</Link></th>
            <td><StateBadge tone={runStateTone[item.state]}>{item.state}</StateBadge></td>
            <td>{item.summary.skills_indexed}</td>
            <td>{item.summary.proposals_created}</td>
            <td>{unknown(item.started_at)}</td>
          </tr>)}
        </DataTable>
        : <RouteState state="empty" title="No runs yet" description="A run started above appears here, with its per-repository result and event log kept for anyone who opens it later." />)}
    </Panel>

    {runId && <LiveRunPanel key={runId} ctx={ctx} runId={runId} />}
  </div>;
}
