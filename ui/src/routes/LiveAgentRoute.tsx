import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { LightningIcon, ListChecksIcon, PlayIcon, SparkleIcon, TerminalIcon } from '@phosphor-icons/react';
import { ActionButton, DataTable, Field, Panel, ProvenanceTrail, RouteState, StateBadge } from '../Shared';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { isStale, type ApiError } from '../api/client';
import { ApiFailure, DegradedNotice, OwnerNote, PartialNotice, asApiError, shortId, stableKey, unknown, useAsync, type ApiProps } from './apiState';
import { orgCredentialProviders } from '../api/decoders';
import type { LiveRun, LiveRunEvent, LiveRunState, LiveRunTarget, LiveRunTargetState, OrgCredentialProvider } from '../api/decoders';
import styles from './LiveAgentRoute.module.css';

/** Native selects (keyboard-simplest, tests use selectOptions); classes match shadcn Input. */
const selectClass = 'min-h-(--control-height) w-full rounded-md border border-input bg-graphite-950 px-2 text-stone-100 shadow-(--shadow-control) focus-visible:border-ring';
const inputClass = 'min-h-(--control-height) rounded-md bg-graphite-950 text-[length:var(--font-size-body)] shadow-(--shadow-control) dark:bg-graphite-950';
const textareaClass = 'rounded-md bg-graphite-950 text-[length:var(--font-size-body)] leading-(--line-height-body) shadow-(--shadow-control) dark:bg-graphite-950';

const runStateTone: Record<LiveRunState, 'neutral' | 'system' | 'warning' | 'error'> = {
  queued: 'neutral', running: 'system', succeeded: 'system', partial: 'warning', failed: 'error', cancelled: 'neutral',
};
const targetStateTone: Record<LiveRunTargetState, 'neutral' | 'system' | 'warning' | 'error'> = {
  queued: 'neutral', running: 'system', done: 'system', failed: 'error', skipped: 'warning',
};
const cancellableStates: LiveRunState[] = ['queued', 'running'];

/**
 * One line of transcript text per event. `finding` is deliberately blank here: contract §5.5a
 * says it is "the only type the UI shows outside the transcript", so it is rendered by the
 * Findings panel instead. The `live_run_log_truncated` error is also blank: it drives the
 * banner above the transcript, not a line inside it.
 */
function transcriptLine(event: LiveRunEvent): string {
  switch (event.type) {
    case 'run.started': return 'Run started.';
    case 'repo.started': return (event.repo_id ?? 'Repository') + ': started.';
    case 'model.delta': return typeof event.payload.text === 'string' ? event.payload.text : '';
    case 'repo.finished': return (event.repo_id ?? 'Repository') + ': finished.';
    case 'run.finished': return 'Run finished.';
    case 'finding': return '';
    case 'error': {
      if (event.payload.reason === 'live_run_log_truncated') return '';
      const reason = typeof event.payload.reason === 'string' ? event.payload.reason : null;
      return 'Error' + (reason ? ': ' + reason : '.') + (event.repo_id ? ' (' + event.repo_id + ')' : '');
    }
    default: return '';
  }
}

/**
 * The active or most recently opened run: its own panel plus a transcript beside a
 * per-repository status list, polled from `GET …/live/runs/{id}/events` (contract §4.9).
 * Keyed by `runId` from the parent, so switching runs remounts this with a fresh cursor.
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

  const findings = events.filter(event => event.type === 'finding');
  const truncated = events.some(event => event.type === 'error' && event.payload.reason === 'live_run_log_truncated');
  const lines = events.filter(event => transcriptLine(event) !== '');

  return <>
    {error && <DegradedNotice>{'Showing the last read status; the next update could not be read (' + error.code + ').'}</DegradedNotice>}
    {run.state === 'partial' && <PartialNotice>{run.counts.failed + ' of ' + run.counts.targets + ' repositories failed and ' + run.counts.skipped + ' were skipped.'}</PartialNotice>}
    <Panel title={'Run ' + shortId(run.run_id)} eyebrow="Live Agent" icon={<LightningIcon weight="regular" aria-hidden="true" />}
      action={<>
        <StateBadge tone={runStateTone[run.state]}>{run.state}</StateBadge>
        {owner && cancellableStates.includes(run.state) && <ActionButton size="sm" disabled={busy} onClick={() => { void cancel(); }}>Cancel run</ActionButton>}
      </>}>
      <p className={styles.help}>{run.prompt}</p>
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
    <div className={styles.twoColumns}>
      <Panel title="Transcript" eyebrow={done ? 'Finished' : 'Updating roughly every second'} tone="quiet" icon={<TerminalIcon weight="regular" aria-hidden="true" />}>
        {truncated && <PartialNotice>The transcript log reached its 20,000-event ceiling and was truncated. The run itself was not interrupted; repository and finding events keep recording.</PartialNotice>}
        {lines.length === 0
          ? <p className={styles.help}>No transcript lines yet.</p>
          : <pre className={styles.transcript}>{lines.map(event => <code key={event.seq} className={styles.transcriptLine}>{transcriptLine(event)}</code>)}</pre>}
      </Panel>
      <div className={styles.stack}>
        <Panel title="Repositories" eyebrow="Per-repository result" tone="quiet" icon={<ListChecksIcon weight="regular" aria-hidden="true" />}>
          {targets.length === 0
            ? <p className={styles.help}>No repository is in scope for this run.</p>
            : <DataTable flush caption="Repositories in this run" headings={['Repository', 'State', 'Findings', 'Detail']}>
              {targets.map(target => <tr key={target.repo_id}>
                <th scope="row"><code>{target.repo_id}</code></th>
                <td><StateBadge tone={targetStateTone[target.state]}>{target.state}</StateBadge></td>
                <td>{target.findings}</td>
                <td>{target.state === 'skipped' && target.error === 'github_app_not_configured' ? 'No GitHub App installed for this repository.' : unknown(target.error)}</td>
              </tr>)}
            </DataTable>}
        </Panel>
        <Panel title="Findings" eyebrow={String(findings.length)} tone="quiet" icon={<SparkleIcon weight="regular" aria-hidden="true" />}>
          {findings.length === 0
            ? <p className={styles.help}>No findings reported yet.</p>
            : <ul className={styles.findings}>{findings.map(event => {
              const summary = typeof event.payload.summary === 'string' ? event.payload.summary : '';
              const severe = event.payload.severity === 'warn';
              const path = typeof event.payload.path === 'string' ? event.payload.path : null;
              return <li key={event.seq} className={styles.finding}>
                <StateBadge tone={severe ? 'warning' : 'neutral'}>{severe ? 'warn' : 'info'}</StateBadge>
                <span>{event.repo_id ? event.repo_id + (path ? ':' + path : '') + ' — ' : ''}{summary}</span>
              </li>;
            })}</ul>}
        </Panel>
      </div>
    </div>
  </>;
}

/** Contract §4.9 (ADR-0046): a composer plus, once a run exists, its transcript and result. */
export function ApiLiveAgentRoute({ ctx }: ApiProps) {
  const { source, org, role } = ctx;
  const owner = role === 'owner';
  const runId = ctx.params.get('run');
  const credentials = useAsync(() => source.listCredentials(org ?? ''), 'credentials:' + org, Boolean(org));
  const repos = useAsync(() => source.listRepos(org ?? ''), 'repos:' + org, Boolean(org));
  const runs = useAsync(() => source.listLiveRuns(org ?? ''), 'live-runs:' + org, Boolean(org));

  const [prompt, setPrompt] = useState('');
  const [provider, setProvider] = useState<OrgCredentialProvider>(orgCredentialProviders[0]);
  const [model, setModel] = useState('');
  const [selectedRepos, setSelectedRepos] = useState<string[]>([]);
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  function toggleRepo(repoId: string) {
    setSelectedRepos(current => current.includes(repoId) ? current.filter(item => item !== repoId) : [...current, repoId]);
  }

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || busy) return;
    const text = prompt.trim();
    if (!text) { setFormError('Enter what the agent should do.'); return; }
    if (text.length > 4000) { setFormError('The prompt is limited to 4000 characters.'); return; }
    setBusy(true);
    setFormError('');
    try {
      const created = await source.startLiveRun(
        org,
        { prompt: text, provider, model: model.trim() || undefined, repos: selectedRepos.length ? selectedRepos : undefined },
        stableKey('live-run', org, provider, model.trim(), text, [...selectedRepos].sort().join(',')),
      );
      setPrompt('');
      runs.reload();
      ctx.go('live', { run: created.run_id });
    } catch (error) {
      const failure = asApiError(error);
      setFormError(
        failure.code === 'live_run_already_active'
          ? 'This organization already has a run in progress. Open it below, or cancel it before starting another.'
          : failure.code === 'model_credential_missing'
            ? 'This organization has no stored key for ' + provider + ' any more. Add one in Model keys before starting a run.'
            : failure.code === 'invalid_prompt' ? 'The prompt was refused: it is empty or over 4000 characters.'
              : failure.code === 'invalid_model' ? 'This model is not on the allowed list for this organization.'
                : 'The run was not started (' + failure.code + ').',
      );
    } finally { setBusy(false); }
  }

  if (!org) return <RouteState state="empty" title="No organization selected" description="Choose an organization before running the Live Agent." action={<ActionButton href={ctx.href('import', { step: 'organization' })} tone="system">Choose an organization</ActionButton>} />;

  // Only a *confirmed* absence replaces the Start button: while the key list is still loading or
  // failed to read, the button stays (disabled during loading) so a slow read never flashes
  // "No key" for a provider that in fact has one; the server's own `model_credential_missing`
  // still catches a key removed in the gap between this read and the submit.
  const noKeyConfirmed = credentials.phase === 'ready' && !(credentials.value?.some(item => item.provider === provider) ?? false);

  return <div className={styles.route}>
    <OwnerNote role={role} />
    <Panel title="Start a run" eyebrow="Live Agent" icon={<PlayIcon weight="regular" aria-hidden="true" />}>
      <p>Runs one prompt against connected repositories in the background. Its transcript and per-repository result appear below once it starts.</p>
      {!owner ? null : <form className={styles.form} onSubmit={start}>
        <Field id="live-prompt" label="Prompt" hint="Up to 4000 characters.">
          <Textarea id="live-prompt" value={prompt} onChange={event => { setPrompt(event.target.value); setFormError(''); }} maxLength={4000} required className={textareaClass} />
        </Field>
        <div className={styles.twoColumns}>
          <Field id="live-provider" label="Provider">
            <select id="live-provider" className={selectClass} value={provider} onChange={event => setProvider(event.target.value as OrgCredentialProvider)}>
              {orgCredentialProviders.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
          <Field id="live-model" label="Model" hint="Leave blank to use this provider's default model.">
            <Input id="live-model" value={model} onChange={event => setModel(event.target.value)} className={inputClass} />
          </Field>
        </div>
        <fieldset className={styles.providers}>
          <legend>Repository scope</legend>
          {repos.phase === 'loading' && <p className={styles.help}>Reading repositories&hellip;</p>}
          {repos.phase === 'ready' && (repos.value?.length
            ? repos.value.map(repo => <label key={repo.repo_id} className={styles.provider}>
              <Checkbox checked={selectedRepos.includes(repo.repo_id)} onCheckedChange={() => toggleRepo(repo.repo_id)} className="size-5 border-line-strong bg-graphite-900 data-checked:border-system data-checked:bg-system data-checked:text-graphite-950" />
              <span>{repo.repo_id}</span>
            </label>)
            : <p className={styles.help}>No repositories are registered for this organization.</p>)}
        </fieldset>
        <p className={styles.help}>Leaving every repository unchecked runs against every repository with a GitHub App installation. One without an installation is skipped, not silently dropped.</p>
        {formError && <p className={styles.feedback} role="alert">{formError}</p>}
        {noKeyConfirmed
          ? <div className={styles.notice} role="status">
            <StateBadge tone="warning">No key</StateBadge>
            <p>This organization has no stored key for {provider}. <Link to={ctx.href('organization', { tab: 'keys' })}>Add one in Model keys</Link> before starting a run.</p>
          </div>
          : <ActionButton type="submit" tone="human" disabled={busy || !prompt.trim() || credentials.phase === 'loading'}>Start run</ActionButton>}
      </form>}
    </Panel>

    <Panel title="Recent runs" eyebrow="This organization" tone="quiet" icon={<ListChecksIcon weight="regular" aria-hidden="true" />}>
      {runs.phase === 'loading' && <RouteState state="loading" title="Reading recent runs" description="Waiting for this organization's run history." />}
      {runs.phase === 'error' && runs.error && <ApiFailure error={runs.error} onRetry={runs.reload} retryLabel="Retry recent runs" />}
      {runs.phase === 'ready' && (runs.value?.items.length
        ? <DataTable flush caption="Recent Live Agent runs" headings={['Run', 'State', 'Provider', 'Model', 'Started']}>
          {runs.value.items.map(item => <tr key={item.run_id}>
            <th scope="row"><Link to={ctx.href('live', { run: item.run_id })}>{shortId(item.run_id)}</Link></th>
            <td><StateBadge tone={runStateTone[item.state]}>{item.state}</StateBadge></td>
            <td>{item.provider}</td>
            <td>{item.model}</td>
            <td>{unknown(item.started_at)}</td>
          </tr>)}
        </DataTable>
        : <RouteState state="empty" title="No runs yet" description="A run started above appears here, with its transcript kept for anyone who opens it later." />)}
    </Panel>

    {runId && <LiveRunPanel key={runId} ctx={ctx} runId={runId} />}
  </div>;
}
