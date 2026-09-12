import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRightIcon, BuildingsIcon, CaretRightIcon, CheckCircleIcon, CheckIcon, CopyIcon, FileCodeIcon, GitBranchIcon, GithubLogoIcon, GoogleLogoIcon, KeyIcon, LinkSimpleIcon, ListChecksIcon, PlugsConnectedIcon, PulseIcon, ShieldCheckIcon, SparkleIcon, TerminalIcon, UsersIcon } from '@phosphor-icons/react';
import { ActionButton, DataTable, Field, IconTile, MetricRow, Panel, ProvenanceTrail, RouteState, StateBadge, Tabs, Urn } from '../Shared';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { BeamCard } from '../components/spectrumui/beam-card';
import { cn } from '@/lib/utils';
import { isStale, type ApiError } from '../api/client';
import { ApiFailure, OwnerNote, PartialNotice, asApiError, formatList, formatNumber, shortId, unknown, useAsync, type ApiProps } from './apiState';
import { formatDay, ScorecardPanel } from './ReviewRoutes';
import { proposalKinds, orgCredentialProviders } from '../api/decoders';
import type { AuditEntry, Job, ImportStatus, Installation, InvitationLifecycle, Member, Org, OrgCredential, OrgCredentialProvider, ProposalKind, ProposalLimits, Repo, RepoAccessLevel, Team, GitHubInstallation } from '../api/decoders';
import type { AccessState } from '../api/access';
import type { DataSource } from '../data/source';
import type { Me } from '../api/decoders';
import styles from './OnboardingRoutes.module.css';

type ImportStep = 'organization' | 'preview' | 'result';
/** shadcn Input on the product's control height; the native select is styled to match (tests use selectOptions). */
const inputClass = 'min-h-(--control-height) rounded-md border-input bg-graphite-950 px-2.5 text-[length:var(--font-size-body)] shadow-(--shadow-control) focus-visible:ring-0 focus-visible:outline-2 focus-visible:outline-offset-(--focus-offset) focus-visible:outline-human focus-visible:border-input';
const selectClass = 'min-h-(--control-height) w-full rounded-md border border-input bg-graphite-950 px-2 text-[length:var(--font-size-body)] shadow-(--shadow-control)';

/** Browser landing page for the one-time invitation capability returned by the API. */
export function ApiInvitationRoute({ source, access, me, token, onRecheck, onAccepted }: {
  source: DataSource; access: AccessState; me: Me | null; token: string;
  onRecheck: () => Promise<unknown>; onAccepted: (orgID: string) => void;
}) {
  const providers = useAsync(() => source.getAuthProviders(), 'invitation-providers');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const acceptKey = useRef('accept-invitation:' + Math.random().toString(36).slice(2));

  async function signIn(provider: string) {
    setBusy(true);
    try {
      const redirect = await source.startLogin(provider, window.location.pathname);
      if (!redirect.loginUrl) throw new Error('missing login redirect');
      window.location.assign(redirect.loginUrl);
    } catch (error) {
      setMessage('Sign-in could not start (' + asApiError(error).code + '). The invitation remains unused.');
      setBusy(false);
    }
  }
  async function accept() {
    setBusy(true);
    setMessage('');
    try {
      const result = await source.acceptInvitation(token, acceptKey.current);
      await onRecheck();
      onAccepted(result.org_id);
    } catch (error) {
      setMessage('The invitation was not accepted (' + asApiError(error).code + '). Nothing was changed.');
      setBusy(false);
    }
  }

  return <div className={styles.route}>
    <Panel title="Join your organization" eyebrow="Invitation" icon={<UsersIcon weight="regular" aria-hidden="true" />}>
      {!me ? <>
        <p>Sign in with the account that should join this organization. The invitation is not consumed until you confirm it.</p>
        {providers.phase === 'loading' && <RouteState state="loading" title="Reading providers" description="Asking the API which identity providers are configured." />}
        {providers.phase === 'error' && providers.error && <ApiFailure error={providers.error} onRetry={providers.reload} retryLabel="Retry the provider list" />}
        {providers.phase === 'ready' && (providers.value?.providers.length
          ? <div className={styles.providers}>{providers.value.providers.map(provider => <ActionButton key={provider.id} tone="human" onClick={() => { void signIn(provider.id); }} disabled={busy}>
            {provider.id === 'github' ? <GithubLogoIcon weight="regular" aria-hidden="true" /> : <GoogleLogoIcon weight="regular" aria-hidden="true" />}Continue with {provider.label}
          </ActionButton>)}</div>
          : <p className={styles.help}>No identity provider is configured on this API.</p>)}
      </> : access.status !== 'confirmed' ? <RouteState state="loading" title="Confirming access" description="Checking your membership before the invitation can be accepted." action={<ActionButton onClick={() => { void onRecheck(); }}>Check access now</ActionButton>} />
        : <>
          <p>You are signed in as <strong>{me.user.email}</strong>. Accepting adds this account to the organization with the role chosen by its owner.</p>
          <ActionButton tone="human" onClick={() => { void accept(); }} disabled={busy}>Accept invitation<CheckCircleIcon weight="regular" aria-hidden="true" /></ActionButton>
        </>}
      {message && <p className={styles.feedback} role="alert">{message}</p>}
    </Panel>
  </div>;
}

function CommandBlock({ commands }: { commands: string }) {
  const [status, setStatus] = useState('');
  const codeRef = useRef<HTMLElement>(null);
  async function copyCommands() {
    try {
      await navigator.clipboard.writeText(commands);
      setStatus('Copied text only. No command was executed.');
    } catch {
      const buffer = document.createElement('textarea');
      buffer.className = styles.clipboardBuffer;
      buffer.value = commands;
      buffer.setAttribute('aria-hidden', 'true');
      buffer.tabIndex = -1;
      document.body.append(buffer);
      buffer.select();
      let copied = false;
      try { copied = document.execCommand('copy'); } catch { /* Use the visible selection below. */ }
      buffer.remove();
      if (copied) setStatus('Copied text only. No command was executed.');
      else {
        const range = document.createRange();
        if (codeRef.current) {
          range.selectNodeContents(codeRef.current);
          const selection = window.getSelection();
          selection?.removeAllRanges();
          selection?.addRange(range);
        }
        setStatus('Clipboard is unavailable. Command text is selected; use your browser Copy action.');
      }
    }
  }
  return <div className={styles.stack}>
    <pre className={styles.command}><code ref={codeRef}>{commands}</code></pre>
    <ActionButton size="sm" onClick={copyCommands}><CopyIcon weight="regular" aria-hidden="true" />Copy proposed commands</ActionButton>
    <p className={styles.feedback} role="status">{status}</p>
  </div>;
}

// ---------------------------------------------------------------------------
// Hosted API routes (F11, F12, F19).
// ---------------------------------------------------------------------------

const terminalImportStates = ['ready', 'partial', 'failed', 'cancelled'];
/** `proposal.generate` job states that stop the generation panel's own poll (contract §6). */
const terminalJobStates = ['done', 'failed', 'skipped', 'cancelled'];
/* Sign-in is no longer a step of this wizard: every management route is private, so an
   unauthenticated request never reaches it — the shell redirects it to /login (app.tsx).
   A stale `?step=login` bookmark therefore falls through to the first real step below. */
const apiSteps: { id: ImportStep; label: string; detail: string; icon: typeof BuildingsIcon }[] = [
  { id: 'organization', label: 'Organization', detail: 'Choose or create one', icon: BuildingsIcon },
  { id: 'preview', label: 'Repository', detail: 'Pick what the CLI uploads', icon: GitBranchIcon },
  { id: 'result', label: 'Import status', detail: 'Files, jobs and publication', icon: ListChecksIcon },
];
type StepState = 'done' | 'current' | 'next';
const stepStatusLabel: Record<StepState, string> = { done: 'Done', current: 'Current step', next: 'Next' };

/**
 * The quickstart: three large step cards, numbered because the flow is a sequence. "Done" is
 * derived from what the URL already carries (an organization, a repository, an import), not
 * from anything the server confirmed. The current card is the only one that moves.
 */
function ImportSteps({ current, done, href }: { current: number; done: (index: number) => boolean; href: (step: ImportStep) => string }) {
  const reduce = useReducedMotion();
  return <ol className={styles.quickstart} aria-label="Import progress">
    {apiSteps.map((item, index) => {
      const state: StepState = index === current ? 'current' : done(index) ? 'done' : 'next';
      const Icon = item.icon;
      const body = <>
        <IconTile icon={<Icon weight="duotone" />} size="xl" tone={state === 'current' ? 'system' : 'neutral'} animate={false} />
        <div className={styles.stepText}>
          <span className={styles.stepNumber} aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
          <strong>{item.label}</strong>
          <span className={styles.stepDetail}>{item.detail}</span>
        </div>
        <span className={styles.stepStatus} data-state={state}>{state === 'done' && <CheckIcon weight="bold" aria-hidden="true" />}{stepStatusLabel[state]}</span>
      </>;
      const link = <Link className={styles.stepLink} to={href(item.id)} aria-label={item.label + ': ' + item.detail + ' (' + stepStatusLabel[state].toLowerCase() + ')'}>{body}</Link>;
      return <motion.li key={item.id} data-state={state} aria-current={state === 'current' ? 'step' : undefined}
        initial={reduce ? false : { opacity: 0, transform: 'translateY(8px)' }} animate={{ opacity: 1, transform: 'translateY(0)' }}
        transition={{ duration: reduce ? 0 : 0.32, delay: reduce ? 0 : 0.05 * index, ease: [0.16, 1, 0.3, 1] }}>
        {state === 'current'
          ? <BeamCard active theme="dark" colorVariant="mono" size="md" className={styles.stepCard} contentClassName="p-0">{link}</BeamCard>
          : link}
      </motion.li>;
    })}
  </ol>;
}

/** A named disclosure on shadcn Collapsible. The panel stays mounted so its rows are reachable to search and assistive tech; only its height animates. */
function Disclosure({ summary, children }: { summary: string; children: ReactNode }) {
  return <Collapsible className={styles.disclosure}>
    <CollapsibleTrigger className={styles.disclosureTrigger}><CaretRightIcon weight="bold" aria-hidden="true" />{summary}</CollapsibleTrigger>
    <CollapsibleContent keepMounted className={styles.disclosurePanel}><div className={styles.disclosureBody}>{children}</div></CollapsibleContent>
  </Collapsible>;
}

/** Values the API returns once and never again. Kept in component state, never persisted. */
function ShownOnce({ title, label, value, note }: { title: string; label: string; value: string; note: string }) {
  const [status, setStatus] = useState('');
  return <Panel title={title} eyebrow="Shown once" icon={<KeyIcon weight="regular" aria-hidden="true" />} action={<StateBadge tone="warning">Not stored</StateBadge>}>
    <div className={styles.shownOnce}>
      <IconTile icon={<KeyIcon weight="duotone" />} size="lg" tone="human" />
      <div className={styles.shownOnceBody}>
        <p>{note}</p>
        <pre className={styles.secret}><code aria-label={label}>{value}</code></pre>
        <div><ActionButton size="sm" onClick={async () => {
          try { await navigator.clipboard.writeText(value); setStatus('Copied. This value is not shown again after you leave this view.'); }
          catch { setStatus('Clipboard is unavailable. Select the text above and use your browser Copy action.'); }
        }}><CopyIcon weight="regular" aria-hidden="true" />Copy value</ActionButton></div>
        <p className={styles.feedback} role="status">{status}</p>
      </div>
    </div>
  </Panel>;
}

/**
 * The Model keys table's Model column, editable in place (contract §4.8's `PATCH`, ADR-0045):
 * free text, no dropdown of model names, saved without touching the key. Owns its own draft and
 * error state so one row's in-progress edit or failure never bleeds into another row's.
 */
function CredentialModelCell({ entry, owner, onSave }: { entry: OrgCredential; owner: boolean; onSave: (model: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(entry.model);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const shown = entry.model ? <code>{entry.model}</code> : <span className={styles.linkHint}>Provider default</span>;
  if (!owner) return shown;
  if (!editing) return <div className={styles.modelCell}>
    {shown}
    <ActionButton size="sm" onClick={() => { setValue(entry.model); setError(''); setEditing(true); }}>Edit</ActionButton>
  </div>;
  return <form className={styles.modelCell} onSubmit={async event => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try { await onSave(value.trim()); setEditing(false); }
    catch (failure) { setError('The model was not saved (' + asApiError(failure).code + ').'); }
    finally { setSaving(false); }
  }}>
    <Input aria-label={'Model for ' + entry.provider} value={value} onChange={event => setValue(event.target.value)} maxLength={120} className={inputClass} disabled={saving} />
    <ActionButton size="sm" type="submit" tone="human" disabled={saving}>Save</ActionButton>
    <ActionButton size="sm" type="button" disabled={saving} onClick={() => { setEditing(false); setError(''); }}>Cancel</ActionButton>
    {error && <p className={styles.feedback} role="alert">{error}</p>}
  </form>;
}

const generationPanelId = 'generate-proposals';
const createInstallationPanelId = 'create-installation';

/**
 * The Integrations tab's "Set up an adapter" guide (Task 7): the owner asked what an adapter
 * is after seeing "No adapter installed" on Overview. Every command here is quoted verbatim
 * from `skills/guidefold/scripts/guidefold` — its usage block, `cmd_install`, `cmd_login`,
 * `cmd_doctor`, `cmd_telemetry_flush` and the argparse definitions for those subcommands — never
 * invented. `docs/HOWTO-adapter.md` carries the same five steps for a reader outside the UI,
 * plus a troubleshooting table.
 */
const ADAPTER_STEPS: { title: string; detail: string; command: string }[] = [
  {
    title: 'Install the adapter',
    detail: 'Run this from your checkout: it copies the CLI and wires the harness hook into .agents/skills/guidefold/ (harness is claude, copilot or gemini).',
    command: 'guidefold install --harness claude',
  },
  {
    title: 'Sign in',
    detail: 'Starts the device flow; open the printed link and approve the code it shows, right here under Organization › Integrations.',
    command: 'guidefold login',
  },
  {
    title: 'Store the installation token',
    detail: 'Paste the token an owner creates below into a file only you can read, then point the adapter at it.',
    command: 'printf \'%s\' "<paste the installation token>" > ~/.config/guidefold/search-token '
      + '&& chmod 600 ~/.config/guidefold/search-token '
      + '&& export GUIDEFOLD_SEARCH_TOKEN_FILE=~/.config/guidefold/search-token',
  },
  {
    title: 'Check the setup',
    detail: 'Confirms org, repo, auth, API and the installed adapter, and prints a fix for anything still wrong.',
    command: 'guidefold doctor',
  },
  {
    title: 'Send telemetry',
    detail: 'Posts queued SEARCH/USE events to /v1/events:batch; run this by hand or from CI, never from the hook.',
    command: 'guidefold telemetry flush --url <api>',
  },
];

function ImportStatusView({ ctx, importId }: ApiProps & { importId: string }) {
  const { source, org, repo, role } = ctx;
  const owner = role === 'owner';
  const [status, setStatus] = useState<ImportStatus | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!org || !repo) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const next = await source.getImport({ org, repo }, importId);
        if (!live) return;
        setStatus(next);
        setError(null);
        // Polling stops on a terminal state and on unmount; the same import_id is kept.
        if (!terminalImportStates.includes(next.state)) timer = setTimeout(() => { void poll(); }, 2000);
      } catch (failure) {
        if (!live || isStale(failure)) return;
        setError(asApiError(failure));
      }
    };
    void poll();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [source, org, repo, importId, attempt]);

  if (!status && error) return <ApiFailure error={error} onRetry={() => setAttempt(current => current + 1)} retryLabel="Retry this import status" />;
  if (!status) return <RouteState state="loading" title="Reading import status" description="Waiting for the first status of this import." />;
  const counts = status.counts;
  const files = status.files;
  const group = (state: string) => files.filter(file => file.status === state);
  const failedJobs = status.jobs.filter(item => item.state === 'failed');
  const publication = status.publication;
  const degraded = Boolean(error) || failedJobs.length > 0 || publication?.state === 'failed';
  return <>
    {status.state === 'partial' && <div className={styles.notice} role="status"><StateBadge tone="warning">Partial</StateBadge><p>{group('accepted').length} of {files.length} files were accepted. Omitted and failed paths are listed below; completeness is not established.</p></div>}
    {/* §5.2: the API cuts the file list. The counts above still cover the whole import, so the
        two numbers differ on purpose and the shorter one is named as incomplete. */}
    {status.files_truncated && <PartialNotice>{'The API returned a shortened file list: ' + files.length + ' of ' + (counts?.files ?? files.length) + ' files are shown below. The counts above cover the whole import; the lists do not.'}</PartialNotice>}
    {degraded && <div className={styles.notice} role="status"><StateBadge tone="warning">Degraded</StateBadge><p>{error ? 'Showing the last status read at ' + unknown(status.updated_at) + '. The status could not be refreshed.' : 'Import files were read, but ' + (failedJobs.length ? failedJobs.length + ' job(s) failed.' : 'the publication step failed.')}</p></div>}
    <Panel title="Import result" eyebrow={'Import ' + shortId(status.import_id)} icon={<FileCodeIcon weight="regular" aria-hidden="true" />}
      action={<>
        <StateBadge tone={status.state === 'failed' ? 'error' : status.state === 'partial' ? 'warning' : 'system'}>{status.state}</StateBadge>
        {owner && publication?.state === 'published'
          ? <ActionButton tone="system" href={'#' + generationPanelId}>Generate proposals</ActionButton>
          : <ActionButton tone="system" href={ctx.href('library', {})}>Open Library</ActionButton>}
      </>}>
      {/* The counts stay exact and labelled; the rest of the evidence folds below them. */}
      <dl className={styles.statStrip}>
        {([['Accepted', counts?.accepted ?? group('accepted').length], ['Omitted', counts?.omitted ?? group('omitted').length], ['Failed', counts?.failed ?? group('failed').length]] as const).map(([label, value]) => <div key={label} className={styles.stat}><dt>{label}</dt><dd>{String(value)}</dd></div>)}
        <div className={styles.stat}><dt>Publication</dt><dd><StateBadge tone={publication?.state === 'failed' ? 'error' : publication?.state === 'published' ? 'system' : 'neutral'}>{publication?.state ?? 'none'}</StateBadge></dd></div>
      </dl>
      <ProvenanceTrail entries={[
        { label: 'Import', value: <Urn value={status.import_id} /> },
        { label: 'Manifest digest', value: unknown(status.manifest_digest), code: true },
        { label: 'Commit', value: unknown(status.commit), code: true },
        { label: 'Manifest completeness', value: status.complete ? 'Complete scan' : 'Partial scan', detail: 'A partial scan never produces deletions.' },
      ]} />
      {(['accepted', 'omitted', 'failed'] as const).map(state => <Disclosure key={state} summary={state[0].toUpperCase() + state.slice(1) + ' files (' + group(state).length + ')'}>
        {group(state).length === 0 ? <p className={styles.help}>No files in this group.</p> : <DataTable flush caption={'Files with status ' + state} headings={['Source path', 'Kind', 'Reason']}>
          {group(state).map(file => <tr key={file.path}><td className={styles.pathCell}><code>{file.path}</code></td><td>{unknown(file.kind)}</td><td>{unknown(file.reason)}</td></tr>)}
        </DataTable>}
      </Disclosure>)}
    </Panel>
    <Panel title="Jobs" eyebrow="Worker" tone="quiet" icon={<TerminalIcon weight="regular" aria-hidden="true" />} action={failedJobs.length ? <StateBadge tone="error">{failedJobs.length + ' failed'}</StateBadge> : undefined}>
      {status.jobs.length === 0 ? <p className={styles.help}>No jobs are recorded for this import.</p> : <DataTable flush caption="Jobs for this import" headings={['Job', 'Kind', 'State', 'Attempts', 'Error']}>
        {status.jobs.map(item => <tr key={item.job_id}><th scope="row" className={styles.pathCell}><code>{item.job_id}</code></th><td>{item.kind}</td><td><StateBadge tone={item.state === 'failed' ? 'error' : item.state === 'done' ? 'system' : 'neutral'}>{item.state}</StateBadge></td><td>{item.attempts}</td><td>{unknown(item.error)}</td></tr>)}
      </DataTable>}
    </Panel>
    {/* Folded once published: the summary strip already says so. Anything else stays open because it needs a look. */}
    <Panel title="Publication" eyebrow="Separate from import" tone="quiet" collapsible defaultOpen={publication?.state !== 'published'} icon={<CheckCircleIcon weight="regular" aria-hidden="true" />} action={<StateBadge tone={publication?.state === 'failed' ? 'error' : publication?.state === 'published' ? 'system' : 'neutral'}>{publication?.state ?? 'none'}</StateBadge>}>
      <ProvenanceTrail entries={[
        { label: 'Publication state', value: publication?.state ?? 'none', detail: 'Import stores files; publication activates a snapshot.' },
        { label: 'Snapshot', value: unknown(publication?.snapshot_id), code: true },
        { label: 'Error', value: unknown(publication?.error) },
      ]} />
    </Panel>
    <ProposalGenerationPanel ctx={ctx} importId={importId} />
  </>;
}

/** `ImportPlan.groups_skipped` counts, per kind, the scopes `max_groups` cut from the plan (§5.2). */
const skippedGroups = (skipped: Record<string, number>): number =>
  Object.values(skipped).reduce((total, count) => total + count, 0);
const describeSkipped = (skipped: Record<string, number>): string =>
  Object.entries(skipped).filter(([, count]) => count > 0).map(([kind, count]) => count + ' ' + kind).join(', ');

/**
 * Read-before-start proposal generation (contract §4.2). `GET …/plan` is owner-only, so a member
 * sees the existing owner notice instead of an attempted read; `POST …/proposals:generate` opens
 * one `proposal.generate` job per requested kind, then this panel polls just those jobs by id
 * (the shared import poll above already stopped once the import itself reached a terminal state).
 */
function ProposalGenerationPanel({ ctx, importId }: ApiProps & { importId: string }) {
  const { source, org, repo, role } = ctx;
  const owner = role === 'owner';
  const [kinds, setKinds] = useState<ProposalKind[]>([...proposalKinds]);
  const [limitInputs, setLimitInputs] = useState({ max_tokens: '', max_calls: '', max_usd: '' });
  const [limitError, setLimitError] = useState('');
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [jobIds, setJobIds] = useState<string[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const kindsKey = proposalKinds.filter(kind => kinds.includes(kind)).join(',');
  const plan = useAsync(
    () => source.getImportPlan({ org: org ?? '', repo: repo ?? '' }, importId, kinds),
    'import-plan:' + org + '/' + repo + '/' + importId + ':' + kindsKey,
    owner && Boolean(org && repo) && kinds.length > 0,
  );

  useEffect(() => {
    if (!jobIds || !org || !repo) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const status = await source.getImport({ org, repo }, importId);
        if (!live) return;
        const matched = status.jobs.filter(item => jobIds.includes(item.job_id));
        setJobs(matched);
        const complete = matched.length === jobIds.length && matched.every(item => terminalJobStates.includes(item.state));
        if (!complete) timer = setTimeout(() => { void poll(); }, 2000);
      } catch (failure) {
        if (!live || isStale(failure)) return;
      }
    };
    void poll();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [jobIds, source, org, repo, importId]);

  function toggleKind(kind: ProposalKind) {
    if (busy || jobIds) return;
    setKinds(current => current.includes(kind) ? current.filter(item => item !== kind) : [...current, kind]);
  }
  function updateLimit(key: 'max_tokens' | 'max_calls' | 'max_usd', raw: string) {
    setLimitInputs(current => ({ ...current, [key]: raw }));
    setLimitError('');
  }
  async function generate() {
    if (!org || !repo || busy || jobIds || kinds.length === 0) return;
    const labels: Record<'max_tokens' | 'max_calls' | 'max_usd', string> = { max_tokens: 'Max tokens', max_calls: 'Max model calls', max_usd: 'Max spend' };
    const limits: Partial<ProposalLimits> = {};
    for (const key of ['max_tokens', 'max_calls', 'max_usd'] as const) {
      const raw = limitInputs[key].trim();
      if (!raw) continue;
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) { setLimitError(labels[key] + ' must be a non-negative number.'); return; }
      const ceiling = plan.value?.limits[key];
      if (ceiling != null && value > ceiling) { setLimitError(labels[key] + ' cannot exceed the plan estimate of ' + ceiling + '.'); return; }
      limits[key] = value;
    }
    setLimitError('');
    setFormError('');
    setBusy(true);
    try {
      const result = await source.generateProposals(
        { org, repo }, importId, { kinds, limits },
        'generate-proposals:' + org + ':' + repo + ':' + importId + ':' + kindsKey + ':' + JSON.stringify(limits),
      );
      setJobIds(result.job_ids);
      setJobs([]);
    } catch (error) { setFormError('Generation was not started (' + asApiError(error).code + '). No job was queued and nothing was spent.'); }
    finally { setBusy(false); }
  }

  if (!owner) return <Panel id={generationPanelId} title="Generate proposals" eyebrow="Owner" icon={<SparkleIcon weight="regular" aria-hidden="true" />}>
    <OwnerNote role={role} />
  </Panel>;

  return <Panel id={generationPanelId} title="Generate proposals" eyebrow="Optional" icon={<SparkleIcon weight="regular" aria-hidden="true" />} action={jobIds ? <StateBadge tone="system">Started</StateBadge> : undefined}>
    <p>Runs as a background job. Nothing in Proposals changes until it finishes.</p>
    {plan.phase === 'loading' && <RouteState state="loading" title="Reading the plan" description="Estimating groups, inputs and cost before any generation starts." />}
    {plan.phase === 'error' && plan.error && <ApiFailure error={plan.error} onRetry={plan.reload} retryLabel="Retry the plan" />}
    {plan.phase === 'ready' && plan.value && <>
      <MetricRow items={[
        { label: 'Groups', value: String(plan.value.groups.length), detail: 'Inputs the next run would cover' },
        { label: 'Estimated max cost', value: '$' + plan.value.estimated_usd_max.toFixed(2), detail: 'Upper bound, not a charge' },
        { label: 'Generator', value: plan.value.generator.name, detail: plan.value.generator.configured ? 'Configured' : 'Not configured' },
      ]} />
      {!plan.value.generator.configured && <div className={styles.notice} role="status"><StateBadge tone="warning">No generator configured</StateBadge><p>This API has no LLM generator configured. Generation jobs finish as skipped, not failed; this is expected until an operator configures one.</p></div>}
      {/* `max_groups` cuts scopes out of the plan; the list below is then not every scope. */}
      {skippedGroups(plan.value.groups_skipped) > 0 && <PartialNotice>{'The plan limit of ' + plan.value.limits.max_groups + ' groups left out ' + skippedGroups(plan.value.groups_skipped) + ' scope(s): ' + describeSkipped(plan.value.groups_skipped) + '. The list below is not every scope of this import, and a run now covers only what it shows.'}</PartialNotice>}
      <Disclosure summary={'Groups and inputs (' + plan.value.groups.length + ')'}>
        {plan.value.groups.length === 0 ? <p className={styles.help}>No groups are available for the selected kinds.</p> : <DataTable flush caption="Plan groups" headings={['Group', 'Kind', 'Inputs', 'Estimated tokens']}>
          {plan.value.groups.map(group => <tr key={group.group_id}><th scope="row"><code>{group.group_id}</code></th><td>{group.kind}</td><td className={styles.pathCell}>{formatList(group.inputs)}</td><td>{group.estimated_tokens ?? 'Unknown'}</td></tr>)}
        </DataTable>}
      </Disclosure>
      <fieldset className={styles.providers} disabled={busy || Boolean(jobIds)}>
        <legend>Proposal kinds</legend>
        {proposalKinds.map(kind => <label key={kind} className={styles.provider}>
          <Checkbox checked={kinds.includes(kind)} disabled={busy || Boolean(jobIds)} onCheckedChange={() => toggleKind(kind)} className="size-5 border-line-strong bg-graphite-900 data-checked:border-system data-checked:bg-system data-checked:text-graphite-950" />
          <span>{kind}</span>
        </label>)}
      </fieldset>
      {kinds.length === 0 && <p className={styles.help}>Select at least one proposal kind.</p>}
      <p className={styles.help}>Fixed by the API: at most {plan.value.limits.max_groups} groups, {plan.value.limits.max_proposals_per_group} proposals per group, {plan.value.limits.max_neighbours} neighbours.</p>
      <Disclosure summary="Limits">
        <p className={styles.help}>Optional. Empty fields use the plan ceilings shown as placeholders.</p>
        <div className={styles.twoColumns}>
          <Field id="limit-max-tokens" label="Max tokens" hint={plan.value.limits.max_tokens != null ? 'Plan allows up to ' + plan.value.limits.max_tokens + '.' : 'No ceiling from the plan.'}>
            <Input id="limit-max-tokens" inputMode="numeric" value={limitInputs.max_tokens} placeholder={plan.value.limits.max_tokens != null ? String(plan.value.limits.max_tokens) : undefined} disabled={busy || Boolean(jobIds)} onChange={event => updateLimit('max_tokens', event.target.value)} className={inputClass} />
          </Field>
          <Field id="limit-max-calls" label="Max model calls" hint={plan.value.limits.max_calls != null ? 'Plan allows up to ' + plan.value.limits.max_calls + '.' : 'No ceiling from the plan.'}>
            <Input id="limit-max-calls" inputMode="numeric" value={limitInputs.max_calls} placeholder={plan.value.limits.max_calls != null ? String(plan.value.limits.max_calls) : undefined} disabled={busy || Boolean(jobIds)} onChange={event => updateLimit('max_calls', event.target.value)} className={inputClass} />
          </Field>
          <Field id="limit-max-usd" label="Max spend (USD)" hint={plan.value.limits.max_usd != null ? 'Plan allows up to ' + plan.value.limits.max_usd + '.' : 'No ceiling from the plan.'}>
            <Input id="limit-max-usd" inputMode="decimal" value={limitInputs.max_usd} placeholder={plan.value.limits.max_usd != null ? String(plan.value.limits.max_usd) : undefined} disabled={busy || Boolean(jobIds)} onChange={event => updateLimit('max_usd', event.target.value)} className={inputClass} />
          </Field>
        </div>
      </Disclosure>
      {limitError && <p className={styles.feedback} role="alert">{limitError}</p>}
      {formError && <p className={styles.feedback} role="alert">{formError}</p>}
      <ActionButton tone="human" disabled={busy || kinds.length === 0 || Boolean(jobIds)} onClick={() => { void generate(); }}>
        {jobIds ? 'Generation started' : 'Generate proposals'}
      </ActionButton>
    </>}
    {jobIds && <DataTable flush caption="Generation jobs" headings={['Job', 'State', 'Error']}>
      {jobIds.map(id => {
        const job = jobs.find(item => item.job_id === id);
        const state = job?.state ?? 'queued';
        return <tr key={id}>
          <th scope="row"><code>{id}</code></th>
          <td><StateBadge tone={state === 'failed' ? 'error' : state === 'skipped' ? 'warning' : state === 'done' ? 'system' : 'neutral'}>{state}</StateBadge></td>
          <td>{unknown(job?.error)}</td>
        </tr>;
      })}
    </DataTable>}
    {jobs.some(item => item.state === 'skipped' && item.error === 'llm_not_configured') && <div className={styles.notice} role="status"><StateBadge tone="warning">Skipped</StateBadge><p>No generator is configured on this API. This is not a failure: existing skills stay usable, and generation can run again once a generator is configured.</p></div>}
    {jobIds && jobs.length === jobIds.length && jobs.every(item => terminalJobStates.includes(item.state)) && <p className={styles.help}>Generation finished. Open <Link to={ctx.href('proposals', {})}>Proposals</Link> to review the result.</p>}
  </Panel>;
}

export function ApiImportRoute({ ctx }: ApiProps) {
  const { source, me, org, repo, role } = ctx;
  const signedIn = Boolean(me);
  const owner = role === 'owner';
  const requested = ctx.params.get('step');
  const fallbackStep: ImportStep = !org ? 'organization' : !repo ? 'preview' : 'result';
  const step = apiSteps.some(item => item.id === requested) ? requested as ImportStep : fallbackStep;
  // A signed-in visit to a step this wizard no longer has (`?step=login` from a bookmark) renders
  // the first real step, so the address is corrected to match it instead of lingering as the name
  // of a screen that does not exist. Replaced, never pushed: it is not a navigation.
  useEffect(() => {
    if (requested === null || apiSteps.some(item => item.id === requested)) return;
    const url = new URL(window.location.href);
    url.searchParams.set('step', step);
    window.history.replaceState(null, '', url.pathname + url.search + url.hash);
  }, [requested, step]);
  const current = apiSteps.findIndex(item => item.id === step);
  const orgs = useAsync(() => source.listOrgs(), 'orgs:' + (me?.user.id ?? ''), signedIn && step === 'organization');
  const repos = useAsync(() => source.listRepos(org ?? ''), 'repos:' + (org ?? ''), Boolean(org) && (step === 'preview' || step === 'result'));
  const members = useAsync(() => source.listMembers(org ?? ''), 'repo-members:' + (org ?? ''), owner && Boolean(org) && step === 'preview');
  const repoAccess = useAsync(() => source.listRepoAccess({ org: org ?? '', repo: repo ?? '' }), 'repo-access:' + org + '/' + repo, owner && Boolean(org && repo) && step === 'preview');
  const reviewers = useAsync(() => source.listReviewers({ org: org ?? '', repo: repo ?? '' }), 'repo-reviewers:' + org + '/' + repo, owner && Boolean(org && repo) && step === 'preview');
  const imports = useAsync(() => source.listImports({ org: org ?? '', repo: repo ?? '' }), 'imports:' + org + '/' + repo, Boolean(org && repo) && step === 'result');
  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [repoId, setRepoId] = useState('');
  const [gitUrl, setGitUrl] = useState('');
  const [accessUserId, setAccessUserId] = useState('');
  const [accessLevel, setAccessLevel] = useState<RepoAccessLevel>('read');
  const [reviewerUserId, setReviewerUserId] = useState('');
  const [accessStatus, setAccessStatus] = useState('');
  const [localPackage, setLocalPackage] = useState<File[]>([]);
  const [localPackageError, setLocalPackageError] = useState('');
  const [localPackageStatus, setLocalPackageStatus] = useState('');
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const importId = ctx.params.get('import_id') ?? imports.value?.[0]?.import_id ?? null;
  const commands = 'guidefold login\nguidefold org use ' + (org ?? '<organization>') + '\nguidefold scan . --dry-run\nguidefold import .';

  async function signIn(provider: string) {
    try {
      const redirect = await source.startLogin(provider, '/import?step=organization');
      if (redirect.loginUrl) window.location.assign(redirect.loginUrl);
    } catch (error) { setFormError('Sign-in could not start (' + asApiError(error).code + '). You are not signed in and nothing was sent to the provider.'); }
  }
  async function createOrg(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const slug = orgSlug.trim();
    if (!/^[a-z0-9-]{2,40}$/.test(slug)) { setFormError('The slug must be 2 to 40 characters of a-z, 0-9 or hyphen.'); return; }
    setBusy(true);
    try {
      const created: Org = await source.createOrg({ name: orgName.trim() || slug, slug }, 'create-org:' + slug);
      setFormError('');
      // Membership is derived from the access controller's cached /me, not this response;
      // without a forced re-check the very next screen reads "Organization unavailable" for
      // up to ~25 s (the normal cadence) even though creation just succeeded.
      await ctx.recheckAccess?.();
      ctx.go('import', { org: created.slug, step: 'preview' });
    } catch (error) { setFormError('The organization was not created (' + asApiError(error).code + '). Nothing was saved; the name and slug above are kept.'); }
    finally { setBusy(false); }
  }
  async function createRepo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !org) return;
    const id = repoId.trim();
    if (!/^[A-Za-z0-9_.-]{1,64}$/.test(id)) { setFormError('The repository id may use letters, digits, dot, underscore and hyphen, up to 64 characters.'); return; }
    setBusy(true);
    try {
      const created: Repo = await source.createRepo(org, { repo_id: id, git_host_url: gitUrl.trim() || null }, 'create-repo:' + org + ':' + id);
      setFormError('');
      ctx.go('import', { repo: created.repo_id, step: 'result' });
    } catch (error) { setFormError('The repository was not registered (' + asApiError(error).code + '). Nothing was saved and no import was started.'); }
    finally { setBusy(false); }
  }
  async function saveRepoAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || !repo || !accessUserId || busy) return;
    setBusy(true); setAccessStatus('');
    try {
      await source.setRepoAccess({ org, repo }, accessUserId, accessLevel, 'repo-access:' + org + ':' + repo + ':' + accessUserId + ':' + accessLevel);
      setAccessStatus('Repository access saved.');
      repoAccess.reload();
    } catch (error) { setAccessStatus('Access was not saved (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function removeRepoAccess(userId: string) {
    if (!org || !repo || busy) return;
    setBusy(true); setAccessStatus('');
    try {
      await source.removeRepoAccess({ org, repo }, userId, 'repo-access-remove:' + org + ':' + repo + ':' + userId);
      setAccessStatus('Repository access removed.');
      repoAccess.reload();
    } catch (error) { setAccessStatus('Access was not removed (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function assignRepoReviewer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || !repo || !reviewerUserId || busy) return;
    setBusy(true); setAccessStatus('');
    try {
      await source.assignReviewer({ org, repo }, reviewerUserId, 'repo-reviewer:' + org + ':' + repo + ':' + reviewerUserId);
      setAccessStatus('Reviewer assigned.');
      reviewers.reload();
    } catch (error) { setAccessStatus('Reviewer was not assigned (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function removeRepoReviewer(userId: string) {
    if (!org || !repo || busy) return;
    setBusy(true); setAccessStatus('');
    try {
      await source.removeReviewer({ org, repo }, userId, 'repo-reviewer-remove:' + org + ':' + repo + ':' + userId);
      setAccessStatus('Reviewer removed.');
      reviewers.reload();
    } catch (error) { setAccessStatus('Reviewer was not removed (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function importLocalPackage() {
    if (!org || !repo || !localPackage.length || busy) return;
    setBusy(true); setLocalPackageError(''); setLocalPackageStatus('Reading files locally…');
    try {
      const entries: { path: string; sha256: string; size: number; kind: string; mode: string; source?: null }[] = [];
      const bytesByDigest = new Map<string, Uint8Array>();
      const seenPaths = new Set<string>();
      for (const file of localPackage) {
        const path = (file.webkitRelativePath || file.name).replaceAll('\\', '/').replace(/^\/+/, '');
        if (!path || path.split('/').some(part => part === '..' || part === '.') || path.includes('\u0000') || path.length > 1024) throw new Error('unsafe path: ' + path);
        if (seenPaths.has(path)) throw new Error('duplicate path: ' + path);
        seenPaths.add(path);
        const basename = path.split('/').pop()?.toLowerCase() ?? '';
        if (basename === '.env' || basename.startsWith('.env.') || basename.endsWith('.pem') || basename.endsWith('.key') || basename === 'id_rsa' || basename === 'id_ed25519') {
          throw new Error('sensitive file rejected: ' + path);
        }
        const bytes = new Uint8Array(await file.arrayBuffer());
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(value => value.toString(16).padStart(2, '0')).join('');
        const lower = path.toLowerCase();
        const kind = lower.endsWith('skill.md') || lower.endsWith('.skill.md') ? 'skill' : lower.endsWith('.md') || lower.endsWith('.txt') ? 'document' : lower.endsWith('.json') || lower.endsWith('.yaml') || lower.endsWith('.yml') ? 'config' : 'resource';
        entries.push({ path, sha256: digest, size: bytes.byteLength, kind, mode: '100644', source: null });
        bytesByDigest.set(digest, bytes);
      }
      const total = entries.reduce((sum, entry) => sum + entry.size, 0);
      if (entries.length > 10000 || total > 100 * 1024 * 1024) throw new Error('the browser package is larger than the 10,000 file / 100 MiB limit');
      const manifest = { format: 'guidefold-import-manifest-v1', org, repo, commit: null, complete: true, dirty: false, publish: true, cli_version: 'browser', scan_profile: 'default', root: '.', files: entries, excluded: [], aliases: [], suggestions: [], limits: { max_files: 10000, max_bytes: 104857600 } };
      const created = await source.createImport({ org, repo }, manifest, 'browser-import:' + org + ':' + repo + ':' + entries.map(entry => entry.sha256).join(','));
      for (const digest of created.missing_blobs) {
        const bytes = bytesByDigest.get(digest);
        if (!bytes) throw new Error('API requested a blob that was not in the local package');
        await source.uploadImportBlob({ org, repo }, created.import_id, digest, bytes);
      }
      await source.finalizeImport({ org, repo }, created.import_id, 'browser-finalize:' + created.import_id);
      setLocalPackageStatus('Package uploaded. Reading import status.');
      ctx.go('import', { step: 'result', import_id: created.import_id });
    } catch (error) {
      setLocalPackageError(error instanceof Error ? error.message : 'The browser package could not be imported.');
      setLocalPackageStatus('Nothing was published. Fix the package and retry.');
    } finally { setBusy(false); }
  }

  const stepDone = (index: number) => index === 0 ? Boolean(org) : index === 1 ? Boolean(org && repo) : Boolean(org && repo && importId);
  return <div className={styles.route}>
    <ImportSteps current={current} done={stepDone} href={target => ctx.href('import', { step: target })} />
    {signedIn && <OwnerNote role={role} />}
    {formError && <p className={styles.feedback} role="alert">{formError}</p>}

    {step === 'organization' && <div className={styles.asideColumns}>
      <Panel title="Your organizations" eyebrow="Organization" icon={<BuildingsIcon weight="regular" aria-hidden="true" />}>
        {orgs.phase === 'loading' && <RouteState state="loading" title="Reading organizations" description="Waiting for the membership list." />}
        {orgs.phase === 'error' && orgs.error && <ApiFailure error={orgs.error} onRetry={orgs.reload} retryLabel="Retry the organization list" />}
        {orgs.phase === 'ready' && (orgs.value?.length
          ? <DataTable flush caption="Organizations you belong to" headings={['Organization', 'Role', 'Action']}>
            {orgs.value.map(entry => <tr key={entry.org_id}><th scope="row">{entry.name}<span className={styles.linkHint}>{entry.slug}</span></th><td><StateBadge tone={entry.my_role === 'owner' ? 'human' : 'neutral'}>{entry.my_role ?? 'member'}</StateBadge></td><td><Link to={ctx.href('import', { org: entry.slug, repo: null, step: 'preview' })}>Use this organization</Link></td></tr>)}
          </DataTable>
          : <RouteState state="empty" title="No organization yet" description="Create one to hold a repository, its skills and its members." />)}
      </Panel>
      <Panel title="Create an organization" eyebrow="Owner" icon={<BuildingsIcon weight="regular" aria-hidden="true" />}>
        <form className={styles.form} onSubmit={createOrg}>
          <Field id="new-org-name" label="Organization name" hint="Shown in the header and in member invitations."><Input id="new-org-name" name="name" value={orgName} onChange={event => setOrgName(event.target.value)} maxLength={80} className={inputClass} /></Field>
          <Field id="new-org-slug" label="Slug" hint="2 to 40 characters: a-z, 0-9 and hyphen."><Input id="new-org-slug" name="slug" value={orgSlug} onChange={event => { setOrgSlug(event.target.value); setFormError(''); }} required maxLength={40} className={inputClass} /></Field>
          <ActionButton type="submit" tone="human" disabled={busy}>Create organization<ArrowRightIcon weight="regular" aria-hidden="true" /></ActionButton>
        </form>
      </Panel>
    </div>}

    {step === 'preview' && <div className={styles.asideColumns}>
      {owner && !repo && <Panel title="Register a repository" eyebrow="Repository" icon={<FileCodeIcon weight="regular" aria-hidden="true" />}>
        <p>Give this organization a stable repository id before uploading a local package. This only registers the target; it does not read or execute anything from your checkout.</p>
        <form className={styles.form} onSubmit={createRepo}>
          <Field id="repository-id" label="Repository id" hint="1 to 64 letters, digits, dot, underscore or hyphen.">
            <Input id="repository-id" name="repo_id" value={repoId} onChange={event => { setRepoId(event.target.value); setFormError(''); }} maxLength={64} required className={inputClass} />
          </Field>
          <Field id="git-host-url" label="Git host URL (optional)" hint="Used only as provenance for a registered source.">
            <Input id="git-host-url" name="git_host_url" value={gitUrl} onChange={event => setGitUrl(event.target.value)} className={inputClass} />
          </Field>
          <ActionButton tone="human" type="submit" disabled={busy}>Register repository<ArrowRightIcon weight="regular" aria-hidden="true" /></ActionButton>
        </form>
      </Panel>}
      <Panel title="Repositories" eyebrow="Repository" icon={<GitBranchIcon weight="regular" aria-hidden="true" />}>
        {repos.phase === 'loading' && <RouteState state="loading" title="Reading repositories" description="Waiting for the repository list of this organization." />}
        {repos.phase === 'error' && repos.error && <ApiFailure error={repos.error} onRetry={repos.reload} retryLabel="Retry the repository list" />}
        {repos.phase === 'ready' && (repos.value?.length
          ? <DataTable flush caption="Repositories in this organization" headings={['Repository', 'Git host', 'Action']}>
            {repos.value.map(entry => <tr key={entry.repo_id}><th scope="row"><code>{entry.repo_id}</code></th><td className={styles.pathCell}>{unknown(entry.git_host_url)}</td><td><Link to={ctx.href('import', { repo: entry.repo_id, step: 'result', import_id: null })}>Open import status</Link></td></tr>)}
          </DataTable>
          : <RouteState state="empty" title="Connect GitHub to import a repository" description="Guidefold will show repositories you can access, read the selected revision server-side and build the manifest for review." action={<ActionButton tone="human" onClick={() => { void signIn('github'); }}><GithubLogoIcon weight="regular" aria-hidden="true" />Connect GitHub</ActionButton>} />)}
        {owner && <div className={cn(styles.notice, styles.noticeSystem)} role="note">
          <StateBadge tone="system">Automatic import</StateBadge>
          <p>Repository registration is handled by GitHub. Select a repository and revision after connecting; no repository id or local CLI upload is required.</p>
          <ActionButton size="sm" onClick={() => { void signIn('github'); }}><GithubLogoIcon weight="regular" aria-hidden="true" />Connect GitHub</ActionButton>
        </div>}
      </Panel>
      {owner && repo && <Panel title="Repository access" eyebrow="Owner controls" icon={<UsersIcon weight="regular" aria-hidden="true" />}>
        <p>Limit this repository to named organization members and assign who can review proposals. Owners always retain access.</p>
        {accessStatus && <p className={styles.feedback} role="status">{accessStatus}</p>}
        {members.phase === 'loading' && <RouteState state="loading" title="Reading members" description="Waiting for the organization membership list." />}
        {members.phase === 'error' && members.error && <ApiFailure error={members.error} onRetry={members.reload} retryLabel="Retry the member list" />}
        {members.phase === 'ready' && <div className={styles.stack}>
          <form className={styles.form} onSubmit={saveRepoAccess}>
            <Field id="repo-access-user" label="Member" hint="Grant read or write access to one organization member.">
              <select id="repo-access-user" className={selectClass} value={accessUserId} onChange={event => setAccessUserId(event.target.value)} required>
                <option value="">Choose a member</option>
                {members.value?.map(member => <option key={member.user_id} value={member.user_id}>{member.name || member.email} ({member.role})</option>)}
              </select>
            </Field>
            <Field id="repo-access-level" label="Access level"><select id="repo-access-level" className={selectClass} value={accessLevel} onChange={event => setAccessLevel(event.target.value as RepoAccessLevel)}><option value="read">Read</option><option value="write">Write</option></select></Field>
            <ActionButton tone="human" type="submit" disabled={busy || !accessUserId}>Save repository access</ActionButton>
          </form>
          {repoAccess.phase === 'loading' && <RouteState state="loading" title="Reading repository access" description="Waiting for the access policy." />}
          {repoAccess.phase === 'error' && repoAccess.error && <ApiFailure error={repoAccess.error} onRetry={repoAccess.reload} retryLabel="Retry repository access" />}
          {repoAccess.phase === 'ready' && <DataTable flush caption="Repository access grants" headings={['Member', 'Access', 'Action']}>
            {repoAccess.value?.map(entry => <tr key={entry.user_id}><th scope="row">{entry.name || entry.email}<span className={styles.linkHint}>{entry.email}</span></th><td><StateBadge tone={entry.access === 'write' ? 'human' : 'neutral'}>{entry.access}</StateBadge></td><td><ActionButton size="sm" disabled={busy} onClick={() => { void removeRepoAccess(entry.user_id); }}>Remove</ActionButton></td></tr>)}
          </DataTable>}
          <form className={styles.form} onSubmit={assignRepoReviewer}>
            <Field id="repo-reviewer-user" label="Reviewer" hint="Reviewers can decide and export proposals for this repository.">
              <select id="repo-reviewer-user" className={selectClass} value={reviewerUserId} onChange={event => setReviewerUserId(event.target.value)} required>
                <option value="">Choose a reviewer</option>
                {members.value?.map(member => <option key={member.user_id} value={member.user_id}>{member.name || member.email}</option>)}
              </select>
            </Field>
            <ActionButton type="submit" disabled={busy || !reviewerUserId}>Assign reviewer</ActionButton>
          </form>
          {reviewers.phase === 'loading' && <RouteState state="loading" title="Reading reviewers" description="Waiting for reviewer assignments." />}
          {reviewers.phase === 'error' && reviewers.error && <ApiFailure error={reviewers.error} onRetry={reviewers.reload} retryLabel="Retry reviewers" />}
          {reviewers.phase === 'ready' && <DataTable flush caption="Assigned reviewers" headings={['Reviewer', 'Action']}>
            {reviewers.value?.map(entry => <tr key={entry.user_id}><th scope="row">{entry.name || entry.email}<span className={styles.linkHint}>{entry.email}</span></th><td><ActionButton size="sm" disabled={busy} onClick={() => { void removeRepoReviewer(entry.user_id); }}>Remove</ActionButton></td></tr>)}
          </DataTable>}
        </div>}
      </Panel>}
      <Panel title="Upload from your checkout" eyebrow="CLI" icon={<TerminalIcon weight="regular" aria-hidden="true" />}>
        <p>The browser never reads your repository. The CLI builds the manifest and uploads it for <strong>{org ?? 'your organization'}</strong>.</p>
        <CommandBlock commands={commands} />
      </Panel>
      <Panel title="Import a local package" eyebrow="Browser fallback" icon={<FileCodeIcon weight="regular" aria-hidden="true" />}>
        <p>Select files from a local checkout when GitHub App access and the CLI are unavailable. The browser sends file bytes only after showing the selection; it never follows symlinks or runs package code.</p>
        <Field id="local-package" label="Files" hint="Up to 10,000 files and 100 MiB. Paths containing . or .. are rejected."><input id="local-package" type="file" multiple onChange={event => { setLocalPackage(Array.from(event.target.files ?? [])); setLocalPackageError(''); setLocalPackageStatus(''); }} /></Field>
        {localPackage.length > 0 && <p className={styles.feedback} role="status">{localPackage.length} file(s) selected.</p>}
        {localPackageError && <p className={styles.feedback} role="alert">{localPackageError}</p>}
        {localPackageStatus && <p className={styles.feedback} role="status">{localPackageStatus}</p>}
        <ActionButton tone="human" disabled={!localPackage.length || busy} onClick={() => { void importLocalPackage(); }}>Import selected files</ActionButton>
      </Panel>
    </div>}

    {step === 'result' && (!repo
      ? <RouteState state="empty" title="No repository selected" description="Choose a repository before reading an import status." action={<ActionButton href={ctx.href('import', { step: 'preview' })} tone="system">Choose a repository</ActionButton>} />
      : <>
        {imports.phase === 'loading' && <RouteState state="loading" title="Reading imports" description="Waiting for the import list of this repository." />}
        {imports.phase === 'error' && imports.error && <ApiFailure error={imports.error} onRetry={imports.reload} retryLabel="Retry the import list" />}
        {imports.phase === 'ready' && (imports.value?.length
          ? <Panel title="Imports" eyebrow={imports.value.length + ' for this repository, newest first'} tone={imports.value.length === 1 && ctx.params.get('import_id') ? 'quiet' : 'card'} collapsible={imports.value.length === 1 && Boolean(ctx.params.get('import_id'))} defaultOpen={!(imports.value.length === 1 && ctx.params.get('import_id'))} icon={<FileCodeIcon weight="regular" aria-hidden="true" />}>
            <DataTable flush caption="Imports for this repository" headings={['Import', 'State', 'Commit', 'Action']}>
              {imports.value.map(entry => <tr key={entry.import_id}><th scope="row"><code>{entry.import_id}</code></th><td><StateBadge tone={entry.state === 'failed' ? 'error' : entry.state === 'partial' ? 'warning' : 'neutral'}>{entry.state}</StateBadge></td><td className={styles.hashCell}><code>{unknown(entry.commit)}</code></td><td><Link to={ctx.href('import', { step: 'result', import_id: entry.import_id })}>Read this import</Link></td></tr>)}
            </DataTable>
          </Panel>
          : <RouteState state="empty" title="No import yet" description="Run the CLI from your checkout; this view then reports accepted, omitted and failed files." action={<ActionButton href={ctx.href('import', { step: 'preview' })} tone="system">Show the CLI commands</ActionButton>} />)}
        {importId && <ImportStatusView ctx={ctx} importId={importId} />}
      </>)}
  </div>;
}

export function ApiOrganizationRoute({ ctx }: ApiProps) {
  const { source, org, role, me } = ctx;
  const owner = role === 'owner';
  const tabParam = ctx.params.get('tab');
  const tab = tabParam === 'integrations' ? 'integrations' : tabParam === 'audit' ? 'audit' : tabParam === 'telemetry' ? 'telemetry' : tabParam === 'keys' ? 'keys' : 'members';
  const deviceCode = ctx.params.get('device');
  const auditCursor = ctx.params.get('cursor');
  const members = useAsync(() => source.listMembers(org ?? ''), 'members:' + org, Boolean(org) && tab === 'members');
  const teams = useAsync(() => source.listTeams(org ?? ''), 'teams:' + org, Boolean(org) && tab === 'members');
  const invitations = useAsync(() => source.listInvitations(org ?? ''), 'invitations:' + org, owner && Boolean(org) && tab === 'members');
  const installations = useAsync(() => source.listInstallations(org ?? ''), 'installations:' + org, Boolean(org) && tab === 'integrations');
  const githubInstallations = useAsync(() => source.listGitHubInstallations(org ?? ''), 'github-installations:' + org, owner && Boolean(org) && tab === 'integrations');
  // 1.3.0: `{org_base}/audit` is readable by any member (server-scoped to their own rows, §4.1),
  // not just an owner.
  const audit = useAsync(
    () => source.getAudit(org ?? '', auditCursor ?? undefined),
    'audit:' + org + ':' + (auditCursor ?? ''),
    Boolean(org) && tab === 'audit',
  );
  const telemetry = useAsync(
    () => source.getUsage({ org: org ?? '', repo: ctx.repo ?? '' }, { window: ctx.params.get('window') || undefined }),
    'organization-telemetry:' + org + '/' + (ctx.repo ?? '') + ':' + (ctx.params.get('window') ?? ''),
    Boolean(org && ctx.repo && tab === 'telemetry'),
  );
  const credentials = useAsync(() => source.listCredentials(org ?? ''), 'credentials:' + org, Boolean(org) && tab === 'keys');
  const [linkStatus, setLinkStatus] = useState('');
  const [profileName, setProfileName] = useState(me?.user.name ?? '');
  const [profileStatus, setProfileStatus] = useState('');
  const [email, setEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'owner' | 'member'>('member');
  const [inviteError, setInviteError] = useState('');
  const [acceptUrl, setAcceptUrl] = useState('');
  const [rowError, setRowError] = useState<{ userId: string; message: string } | null>(null);
  const [memberStatus, setMemberStatus] = useState('');
  const [teamName, setTeamName] = useState('');
  const [teamMemberId, setTeamMemberId] = useState('');
  const [teamStatus, setTeamStatus] = useState('');
  const [installationName, setInstallationName] = useState('');
  const [harness, setHarness] = useState('claude');
  const [secret, setSecret] = useState('');
  const [integrationStatus, setIntegrationStatus] = useState('');
  const [deviceStatus, setDeviceStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [keyProvider, setKeyProvider] = useState<OrgCredentialProvider>(orgCredentialProviders[0]);
  const [keyName, setKeyName] = useState('');
  // No closed list (§4.8): the provider owns its model catalogue, and it changes weekly; a
  // hardcoded dropdown here would refuse an organization's own fine-tune. Free text, checked by
  // the provider itself when the key is saved. The organization's first stored credential
  // becomes preferred automatically, so this form never asks for `preferred` at creation time —
  // that field only ever moves through `PATCH` (below), which never asks for the key.
  const [keyModel, setKeyModel] = useState('');
  // Never rendered back and cleared once the request settles, success or failure alike (§4.8).
  const [keyValue, setKeyValue] = useState('');
  const [keyFormError, setKeyFormError] = useState('');
  const [keyStatus, setKeyStatus] = useState('');

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = profileName.trim();
    if (!name || busy) return;
    setBusy(true);
    setProfileStatus('');
    try {
      await source.updateProfile(name, 'profile:' + (me?.user.id ?? '') + ':' + name);
      await ctx.recheckAccess?.();
      setProfileStatus('Profile name saved.');
    } catch (error) {
      setProfileStatus('The profile was not saved (' + asApiError(error).code + ').');
    } finally { setBusy(false); }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || busy) return;
    const value = email.trim();
    if (!value.includes('@')) { setInviteError('Enter the e-mail address the invitation is sent to.'); return; }
    setBusy(true);
    try {
      const invitation = await source.inviteMember(org, { email: value, role: inviteRole }, 'invite:' + org + ':' + value + ':' + inviteRole);
      setAcceptUrl(invitation.accept_url);
      setEmail('');
      setInviteError('');
      setMemberStatus('Invitation created for ' + value + '. The link below is shown once.');
      members.reload();
      invitations.reload();
    } catch (error) { setInviteError('The invitation was not created (' + asApiError(error).code + '). Nobody was invited and the address above is kept.'); }
    finally { setBusy(false); }
  }
  async function revokeInvitation(invitation: InvitationLifecycle) {
    if (!org || invitation.status !== 'pending') return;
    try {
      await source.revokeInvitation(org, invitation.invitation_id, 'revoke-invitation:' + org + ':' + invitation.invitation_id);
      setMemberStatus('Invitation for ' + invitation.email + ' was revoked.');
      invitations.reload();
    } catch (error) {
      setMemberStatus('The invitation was not revoked (' + asApiError(error).code + '). It remains unchanged.');
    }
  }
  async function changeRole(target: Member, next: 'owner' | 'member') {
    if (!org || next === target.role) return;
    setRowError(null);
    try {
      await source.changeMemberRole(org, target.user_id, next, 'role:' + org + ':' + target.user_id + ':' + next);
      setMemberStatus(target.email + ' is now ' + next + '.');
      members.reload();
    } catch (error) {
      const failure = asApiError(error);
      setRowError({
        userId: target.user_id,
        message: failure.code === 'last_owner_protected'
          ? 'The last owner keeps the owner role. Add another owner first.'
          : 'The role was not changed (' + failure.code + '). This membership is unchanged.',
      });
    }
  }
  async function remove(target: Member) {
    if (!org) return;
    setRowError(null);
    try {
      await source.removeMember(org, target.user_id, 'remove:' + org + ':' + target.user_id);
      setMemberStatus(target.email + ' was removed from this organization.');
      members.reload();
    } catch (error) {
      const failure = asApiError(error);
      setRowError({
        userId: target.user_id,
        message: failure.code === 'last_owner_protected'
          ? 'The last owner cannot be removed. Add another owner first.'
          : 'The member was not removed (' + failure.code + '). This membership is unchanged.',
      });
    }
  }
  async function createTeam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || !owner || busy || !teamName.trim()) return;
    setBusy(true); setTeamStatus('');
    try {
      await source.createTeam(org, teamName.trim(), 'team:' + org + ':' + teamName.trim());
      setTeamName(''); setTeamStatus('Team created.'); teams.reload();
    } catch (error) { setTeamStatus('The team was not created (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function addMemberToTeam(team: Team) {
    if (!org || !owner || !teamMemberId || busy) return;
    setBusy(true); setTeamStatus('');
    try {
      await source.addTeamMember(org, team.team_id, teamMemberId, 'team-member:' + org + ':' + team.team_id + ':' + teamMemberId);
      setTeamStatus('Member added to ' + team.name + '.'); setTeamMemberId(''); teams.reload();
    } catch (error) { setTeamStatus('The team membership was not changed (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function removeMemberFromTeam(team: Team, userId: string) {
    if (!org || !owner || busy) return;
    setBusy(true); setTeamStatus('');
    try {
      await source.removeTeamMember(org, team.team_id, userId, 'team-member-remove:' + org + ':' + team.team_id + ':' + userId);
      setTeamStatus('Member removed from ' + team.name + '.'); teams.reload();
    } catch (error) { setTeamStatus('The team membership was not changed (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function createInstallation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || busy) return;
    const name = installationName.trim();
    if (!name) { setIntegrationStatus('Enter a name so the token can be recognised later.'); return; }
    setBusy(true);
    try {
      const created: Installation = await source.createInstallation(org, { name, repo_id: ctx.repo, scopes: ['search', 'use', 'events'], harness }, 'installation:' + org + ':' + name);
      setSecret(created.token ?? '');
      setInstallationName('');
      setIntegrationStatus(created.token ? 'Installation created. Its token is shown once below.' : 'Installation created. The API returned no token value.');
      installations.reload();
    } catch (error) { setIntegrationStatus('The installation was not created (' + asApiError(error).code + '). No token was issued.'); }
    finally { setBusy(false); }
  }
  async function revoke(installationId: string) {
    if (!org) return;
    try {
      await source.revokeInstallation(org, installationId, 'revoke:' + org + ':' + installationId);
      setSecret('');
      setIntegrationStatus('Installation revoked. Adapters using that token stop being served.');
      installations.reload();
    } catch (error) { setIntegrationStatus('The installation was not revoked (' + asApiError(error).code + '). Its token still works.'); }
  }
  async function removeGitHubInstallation(installation: GitHubInstallation) {
    if (!org || !owner || busy) return;
    setBusy(true); setIntegrationStatus('');
    try {
      await source.deleteGitHubInstallation(org, installation.installation_id, 'github-installation:' + org + ':' + installation.installation_id);
      setIntegrationStatus('GitHub installation removed. Future webhook updates are ignored until it is installed again.');
      githubInstallations.reload();
    } catch (error) { setIntegrationStatus('The GitHub installation was not removed (' + asApiError(error).code + ').'); }
    finally { setBusy(false); }
  }
  async function saveCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!org || busy) return;
    const provider = keyProvider;
    const value = keyValue.trim();
    const name = keyName.trim();
    const model = keyModel.trim();
    if (!value) { setKeyFormError('Enter the key value.'); return; }
    setBusy(true);
    setKeyFormError('');
    try {
      await source.setCredential(org, provider, { api_key: value, name: name || undefined, model: model || undefined }, 'credential:' + org + ':' + provider);
      setKeyName('');
      setKeyModel('');
      setKeyStatus('Key saved for ' + provider + '.');
      credentials.reload();
    } catch (error) {
      const failure = asApiError(error);
      // §4.8's closed error list for this endpoint has exactly these named failures plus
      // `invalid_provider`/`invalid_body` (already refused client-side above); anything else is
      // shown by its own code, never folded into one generic word.
      setKeyFormError(
        failure.code === 'credential_invalid' ? 'The provider rejected this key. Nothing was saved.'
          : failure.code === 'invalid_model' ? 'This model identifier was refused (it must be free of whitespace and at most 120 characters). Nothing was saved.'
            : failure.code === 'secret_encryption_unavailable' ? 'This deployment cannot store model keys right now: no secret-encryption key is configured. Nothing was saved.'
              : 'The key was not saved (' + failure.code + ').',
      );
    } finally {
      // Cleared here, not only on success: the typed value never outlives the request.
      setKeyValue('');
      setBusy(false);
    }
  }
  async function removeCredential(provider: OrgCredentialProvider) {
    if (!org || busy) return;
    setBusy(true);
    try {
      await source.deleteCredential(org, provider, 'credential-remove:' + org + ':' + provider);
      setKeyStatus('Key removed for ' + provider + '.');
      credentials.reload();
    } catch (error) {
      setKeyStatus('The key was not removed (' + asApiError(error).code + ').');
    } finally { setBusy(false); }
  }
  /**
   * One click, contract §4.8's `PATCH`: `{preferred: true}`, no key. The server clears the mark
   * from whichever credential held it, so this never needs to send `preferred: false` anywhere —
   * there is no "unprefer" action, only "prefer another one" or "delete this one".
   */
  async function makePreferred(provider: OrgCredentialProvider) {
    if (!org || busy) return;
    setBusy(true);
    try {
      await source.patchCredential(org, provider, { preferred: true }, 'credential-patch:' + org + ':' + provider + ':preferred');
      setKeyStatus(provider + ' is now the preferred credential.');
      credentials.reload();
    } catch (error) {
      setKeyStatus('The preferred credential was not changed (' + asApiError(error).code + ').');
    } finally { setBusy(false); }
  }
  /** Inline model edit, contract §4.8's `PATCH`: `{model: "..."}`, no key. Thrown errors are
   * shown by the row itself (`CredentialModelCell`), not folded into the shared `keyStatus` line. */
  async function patchModel(provider: OrgCredentialProvider, model: string) {
    if (!org) throw new Error('no organization selected');
    await source.patchCredential(org, provider, { model }, 'credential-patch:' + org + ':' + provider + ':model');
    credentials.reload();
  }
  async function decideDevice(approve: boolean) {
    if (!deviceCode) return;
    try {
      const result = await source.decideDevice(deviceCode, approve, 'device:' + deviceCode + ':' + (approve ? 'approve' : 'deny'));
      setDeviceStatus('Device request ' + deviceCode + ' is now ' + result.state + '.');
    } catch (error) { setDeviceStatus('The device request was not decided (' + asApiError(error).code + '). It stays as it was, and no device was authorized.'); }
  }
  /** Never auto-linked: the operator picks the provider, then the API redirects to confirm it. */
  async function startLink(provider: string) {
    try {
      const redirect = await source.startIdentityLink(provider, 'identity-link:' + (me?.user.id ?? '') + ':' + provider);
      if (redirect.loginUrl) window.location.assign(redirect.loginUrl);
      else setLinkStatus('The API returned no redirect for ' + provider + '.');
    } catch (error) { setLinkStatus('The identity link could not start (' + asApiError(error).code + '). No identity was linked to your account.'); }
  }

  if (!org) return <RouteState state="empty" title="No organization selected" description="Choose an organization before reading its membership or integrations." action={<ActionButton href={ctx.href('import', { step: 'organization' })} tone="system">Choose an organization</ActionButton>} />;

  return <div className={styles.route}>
    <p className={styles.intro}>Membership and adapter installations for <strong>{org}</strong>.</p>
    <Tabs label="Organization sections" current={tab} items={[
      { id: 'members', label: 'Members', href: ctx.href('organization', { tab: 'members', cursor: null }) },
      { id: 'integrations', label: 'Integrations', href: ctx.href('organization', { tab: 'integrations', cursor: null }) },
      { id: 'telemetry', label: 'Telemetry', href: ctx.href('organization', { tab: 'telemetry', cursor: null }) },
      { id: 'audit', label: 'Audit', href: ctx.href('organization', { tab: 'audit', cursor: null }) },
      { id: 'keys', label: 'Model keys', href: ctx.href('organization', { tab: 'keys', cursor: null }) },
    ]} />
    <OwnerNote role={role} />

    {tab === 'keys' ? <Panel title="Model keys" eyebrow="ADR-0045, ADR-0046" icon={<KeyIcon weight="regular" aria-hidden="true" />}>
      <p>The organization's own key for each model provider, and the provider/model choice background work — Live Agent today — reads. Guidefold checks a key with the provider before storing it and never returns it once saved &mdash; only the last four characters are kept visible. Exactly one credential is <strong>preferred</strong> at a time; that is the one used.</p>
      {credentials.phase === 'loading' && <RouteState state="loading" title="Reading model keys" description="Waiting for the stored key metadata for this organization." />}
      {credentials.phase === 'error' && credentials.error && <ApiFailure error={credentials.error} onRetry={credentials.reload} retryLabel="Retry model keys" />}
      {credentials.phase === 'ready' && <DataTable flush caption="Model provider keys" headings={['Provider', 'Name', 'Model', 'Last 4', 'Stored', 'Preferred', 'Action']}>
        {orgCredentialProviders.map(provider => {
          const entry: OrgCredential | undefined = credentials.value?.find(item => item.provider === provider);
          return <tr key={provider}>
            <th scope="row">{provider}</th>
            {/* No row for a provider means the organization has no key for it — the contract is
                explicit that there is no "has a key, but unknown" state (§5.5a). "No key stored"
                on the Name column already says that once; every other cell of the same row stays
                empty rather than repeating "Unknown" as if the data existed but could not be read. */}
            <td>{entry ? entry.name : <span className={styles.linkHint}>No key stored</span>}</td>
            <td>{entry && <CredentialModelCell entry={entry} owner={owner} onSave={model => patchModel(provider, model)} />}</td>
            <td>{entry && <code>&hellip;{entry.last4}</code>}</td>
            <td>{entry ? formatDay(entry.created_at) : null}</td>
            <td>{entry
              ? (entry.preferred
                ? <StateBadge tone="system">Preferred</StateBadge>
                // No "unprefer" control: the server keeps exactly one preferred credential
                // while any exist, so the only ways to stop using one are preferring another
                // or deleting it (§4.8).
                : owner ? <ActionButton size="sm" disabled={busy} onClick={() => { void makePreferred(provider); }}>Make preferred</ActionButton> : unknown(null))
              : null}</td>
            <td>{owner && entry
              ? <ActionButton size="sm" disabled={busy} onClick={() => { void removeCredential(provider); }}>Delete</ActionButton>
              : null}</td>
          </tr>;
        })}
      </DataTable>}
      {owner ? <form className={styles.memberForm} onSubmit={saveCredential}>
        <Field id="key-provider" label="Provider" hint="Storing a key for a provider that already has one replaces it.">
          <select id="key-provider" className={selectClass} value={keyProvider} onChange={event => { setKeyProvider(event.target.value as OrgCredentialProvider); setKeyFormError(''); }}>
            {orgCredentialProviders.map(provider => <option key={provider} value={provider}>{provider}</option>)}
          </select>
        </Field>
        <Field id="key-name" label="Name" hint="A label for this key, for example which account it belongs to.">
          <Input id="key-name" value={keyName} onChange={event => setKeyName(event.target.value)} maxLength={80} className={inputClass} />
        </Field>
        <Field id="key-model" label="Model" hint="Free text, checked by the provider itself; leave blank for this provider's default model. There is no fixed list here — the provider owns its catalogue. To change the model on a credential that already exists, edit it in the table above instead — that does not require the key.">
          <Input id="key-model" value={keyModel} onChange={event => { setKeyModel(event.target.value); setKeyFormError(''); }} maxLength={120} className={inputClass} />
        </Field>
        <Field id="key-value" label="API key" hint="Checked with the provider before it is saved; not shown again after this request." error={keyFormError || undefined}>
          <Input id="key-value" type="password" autoComplete="off" value={keyValue} onChange={event => { setKeyValue(event.target.value); setKeyFormError(''); }} required aria-invalid={Boolean(keyFormError)} className={inputClass} />
        </Field>
        <ActionButton type="submit" tone="human" disabled={busy}>
          {credentials.value?.some(item => item.provider === keyProvider) ? 'Replace key' : 'Store key'}
        </ActionButton>
      </form> : null}
      <p className={styles.feedback} role="status">{keyStatus}</p>
    </Panel> : tab === 'telemetry' ? <>
      {!ctx.repo && <RouteState state="empty" title="No repository selected" description="Choose a repository before reading task and harness telemetry." action={<ActionButton href={ctx.href('import', { step: 'organization' })} tone="system">Choose a repository</ActionButton>} />}
      {ctx.repo && telemetry.phase === 'loading' && <RouteState state="loading" title="Reading telemetry" description="Waiting for the execution metrics for this repository." />}
      {ctx.repo && telemetry.phase === 'error' && telemetry.error && <ApiFailure error={telemetry.error} onRetry={telemetry.reload} retryLabel="Retry telemetry" />}
      {ctx.repo && telemetry.value && <>
        <ScorecardPanel metrics={telemetry.value.totals.metrics} />
        <Panel title="Telemetry context" eyebrow={'Repository ' + ctx.repo} icon={<PulseIcon weight="regular" aria-hidden="true" />}>
          <ProvenanceTrail entries={[
            { label: 'Window', value: (ctx.params.get('window') || '30d') + ' · ' + formatDay(telemetry.value.window.from) + ' to ' + formatDay(telemetry.value.window.to), detail: 'The period is anchored to the ledger watermark, not this browser clock.' },
            { label: 'Events received', value: telemetry.value.coverage ? formatNumber(telemetry.value.coverage.events_received) : 'Unknown', detail: telemetry.value.coverage?.dropped_reported ? formatNumber(telemetry.value.coverage.dropped_reported) + ' reported dropped events; counts are lower bounds.' : 'No drops reported by adapters.' },
            { label: 'Task identifiers', value: telemetry.value.coverage ? (telemetry.value.coverage.task_ids_present ? 'Present' : 'Absent') : 'Unknown', detail: 'Without task IDs, task-level success and episode rates remain Unknown.' },
            { label: 'Detail', value: 'Usage & quality', href: ctx.href('usage', { window: ctx.params.get('window') || null }) },
          ]} />
          <p className={styles.help}>These cards help an owner decide whether the integration is producing usable evidence. They do not certify that a model followed a skill or that a successful task was caused by retrieval.</p>
        </Panel>
      </>}
    </> : tab === 'audit' ? <Panel title="Audit log" eyebrow={owner ? 'Owner' : 'Your own actions'} icon={<ShieldCheckIcon weight="regular" aria-hidden="true" />}>
      {/* 1.3.0: `{org_base}/audit` is readable by any member, not just an owner — the server
          scopes a member to the rows whose actor is their own principal (contract §4.1); an
          owner still reads every row. The eyebrow above says which scope this reader gets. */}
      <>
        {audit.phase === 'loading' && <RouteState state="loading" title="Reading audit entries" description="Waiting for the audit log of this organization." />}
        {audit.phase === 'error' && audit.error && <ApiFailure error={audit.error} onRetry={audit.reload} retryLabel="Retry the audit log" />}
        {audit.phase === 'ready' && (audit.value?.items.length
          ? <>
            <DataTable flush dense caption="Audit entries for this organization" headings={['At', 'Actor', 'Action', 'Entity', 'Revision', 'Request']}>
              {audit.value.items.map((entry: AuditEntry, index: number) => <tr key={entry.request_id ?? index}>
                <td>{unknown(entry.at)}</td>
                <td>{unknown(entry.actor)}</td>
                <td>{entry.action}</td>
                <td className={styles.pathCell}><code>{unknown(entry.entity)}</code></td>
                <td className={styles.hashCell}><code>{unknown(entry.revision)}</code></td>
                <td className={styles.hashCell}><code>{unknown(entry.request_id)}</code></td>
              </tr>)}
            </DataTable>
            {audit.value?.next_cursor && <div className={styles.actions}><ActionButton onClick={() => ctx.go('organization', { tab: 'audit', cursor: audit.value?.next_cursor })}>Next page</ActionButton></div>}
          </>
          : <RouteState state="empty" title="No audit entries yet" description="No action has been recorded for this organization yet." />)}
      </>
    </Panel> : tab === 'members' ? <>
      <Panel title="Your profile" eyebrow="Account" icon={<UsersIcon weight="regular" aria-hidden="true" />}>
        <form className={styles.memberForm} onSubmit={saveProfile}>
          <Field id="profile-name" label="Display name" hint="Your e-mail and provider identities remain managed by the identity provider."><Input id="profile-name" className={inputClass} value={profileName} onChange={event => setProfileName(event.target.value)} maxLength={120} required /></Field>
          <ActionButton type="submit" tone="human" disabled={busy}>Save profile</ActionButton>
        </form>
        {profileStatus && <p className={styles.feedback} role="status">{profileStatus}</p>}
      </Panel>
      <div className={styles.asideColumns}>
      <Panel title="Members" eyebrow="Organization access" icon={<UsersIcon weight="regular" aria-hidden="true" />}>
        {members.phase === 'loading' && <RouteState state="loading" title="Reading members" description="Waiting for the membership list." />}
        {members.phase === 'error' && members.error && <ApiFailure error={members.error} onRetry={members.reload} retryLabel="Retry the member list" />}
        {members.phase === 'ready' && members.value && <DataTable flush caption="Members of this organization" headings={['Member', 'Role', 'Joined', 'Action']}>
          {members.value.map(entry => <tr key={entry.user_id}>
            <th scope="row" className={styles.pathCell}>{entry.email}<span className={styles.linkHint}>{unknown(entry.name)}</span></th>
            <td>{owner
              ? <select aria-label={'Role of ' + entry.email} className={selectClass} value={entry.role} onChange={event => { void changeRole(entry, event.target.value === 'owner' ? 'owner' : 'member'); }}><option value="owner">owner</option><option value="member">member</option></select>
              : <StateBadge tone={entry.role === 'owner' ? 'human' : 'neutral'}>{entry.role}</StateBadge>}</td>
            <td>{unknown(entry.joined_at)}</td>
            <td><ActionButton size="sm" disabled={!owner} onClick={() => { void remove(entry); }}>Remove</ActionButton>
              {rowError?.userId === entry.user_id && <span className={styles.feedback} role="alert">{rowError.message}</span>}</td>
          </tr>)}
        </DataTable>}
        <p className={styles.feedback} role="status">{memberStatus}</p>
        {me?.link_suggestions.map(suggestion => <div key={suggestion.provider} className={styles.notice} role="status">
          <LinkSimpleIcon weight="regular" aria-hidden="true" />
          <span>Another sign-in method uses this e-mail.</span>
          <ActionButton size="sm" onClick={() => { void startLink(suggestion.provider); }}>Link {suggestion.provider}</ActionButton>
        </div>)}
        {linkStatus && <p className={styles.feedback} role="alert">{linkStatus}</p>}
      </Panel>
      <Panel title="Teams" eyebrow="Grouping only" icon={<UsersIcon weight="regular" aria-hidden="true" />}>
        <p className={styles.help}>Teams organize work for this organization. Team membership does not grant access.</p>
        {owner && <form className={styles.memberForm} onSubmit={createTeam}>
          <Field id="team-name" label="Team name"><Input id="team-name" className={inputClass} value={teamName} onChange={event => setTeamName(event.target.value)} maxLength={80} required /></Field>
          <ActionButton type="submit" tone="human" disabled={busy}>Create team</ActionButton>
        </form>}
        {teams.phase === 'loading' && <RouteState state="loading" title="Reading teams" description="Waiting for the organization teams." />}
        {teams.phase === 'error' && teams.error && <ApiFailure error={teams.error} onRetry={teams.reload} retryLabel="Retry teams" />}
        {teams.phase === 'ready' && teams.value && <div className={styles.stack}>
          {owner && members.value && members.value.length > 0 && <div className={styles.memberForm}>
            <Field id="team-member" label="Add member to a team"><select id="team-member" className={selectClass} value={teamMemberId} onChange={event => setTeamMemberId(event.target.value)}><option value="">Choose a member</option>{members.value.map(member => <option key={member.user_id} value={member.user_id}>{member.email}</option>)}</select></Field>
          </div>}
          {teams.value.length === 0 ? <p className={styles.help}>No teams yet.</p> : teams.value.map(team => <div key={team.team_id} className={styles.notice}>
            <strong>{team.name}</strong>
            {owner && <ActionButton size="sm" disabled={!teamMemberId || busy} onClick={() => { void addMemberToTeam(team); }}>Add selected member</ActionButton>}
            {team.members.length ? <span>{team.members.map(member => <span key={member.user_id} className={styles.linkHint}>{member.email}{owner && <ActionButton size="sm" onClick={() => { void removeMemberFromTeam(team, member.user_id); }} disabled={busy}>Remove</ActionButton>}</span>)}</span> : <span className={styles.linkHint}>No members</span>}
          </div>)}
        </div>}
        {teamStatus && <p className={styles.feedback} role="status">{teamStatus}</p>}
      </Panel>
      <Panel title="Invite a member" eyebrow="Owner" icon={<ShieldCheckIcon weight="regular" aria-hidden="true" />}>
        <form className={styles.memberForm} onSubmit={invite}>
          <Field id="invite-email" label="E-mail address" hint="The invitation link is returned once and is not stored here." error={inviteError || undefined}><Input id="invite-email" name="email" type="email" value={email} onChange={event => { setEmail(event.target.value); setInviteError(''); }} required maxLength={200} disabled={!owner} aria-invalid={Boolean(inviteError)} className={inputClass} /></Field>
          <Field id="invite-role" label="Role"><select id="invite-role" className={selectClass} value={inviteRole} onChange={event => setInviteRole(event.target.value === 'owner' ? 'owner' : 'member')} disabled={!owner}><option value="member">member</option><option value="owner">owner</option></select></Field>
          <ActionButton type="submit" tone="human" disabled={!owner || busy}>Create invitation</ActionButton>
        </form>
        {acceptUrl && <ShownOnce title="Invitation link" label="Invitation accept URL" value={acceptUrl} note="Send this link to the invited person. It is not shown again and is not stored in this browser." />}
      </Panel>
      {owner && <Panel title="Invitation lifecycle" eyebrow="Owner" icon={<ShieldCheckIcon weight="regular" aria-hidden="true" />}>
        {invitations.phase === 'loading' && <RouteState state="loading" title="Reading invitations" description="Waiting for pending and completed invitation links." />}
        {invitations.phase === 'error' && invitations.error && <ApiFailure error={invitations.error} onRetry={invitations.reload} retryLabel="Retry invitations" />}
        {invitations.phase === 'ready' && invitations.value && (invitations.value.length
          ? <DataTable flush caption="Invitation lifecycle" headings={['Address', 'Role', 'Status', 'Expires', 'Action']}>
            {invitations.value.map(invitation => <tr key={invitation.invitation_id}>
              <th scope="row" className={styles.pathCell}>{invitation.email}</th>
              <td>{invitation.role}</td>
              <td><StateBadge tone={invitation.status === 'pending' ? 'human' : invitation.status === 'revoked' ? 'warning' : 'neutral'}>{invitation.status}</StateBadge></td>
              <td>{invitation.expires_at}</td>
              <td><ActionButton size="sm" disabled={invitation.status !== 'pending' || busy} onClick={() => { void revokeInvitation(invitation); }}>Revoke</ActionButton></td>
            </tr>)}
          </DataTable>
          : <RouteState state="empty" title="No invitations yet" description="Created links will appear here without exposing their capability token." />)}
      </Panel>}
      </div>
    </> : <>
      {deviceCode && <Panel title="Device authorization" eyebrow="CLI sign-in" icon={<KeyIcon weight="regular" aria-hidden="true" />} action={<StateBadge tone="warning">Pending</StateBadge>}>
        <div className={styles.shownOnce}>
          <IconTile icon={<KeyIcon weight="duotone" />} size="lg" tone="human" />
          <p>A CLI on another machine asked for code <code>{deviceCode}</code>. Approve it only if you started that sign-in.</p>
        </div>
        <div className={styles.actions}>
          <ActionButton tone="human" disabled={!owner} onClick={() => { void decideDevice(true); }}>Approve this device</ActionButton>
          <ActionButton disabled={!owner} onClick={() => { void decideDevice(false); }}>Deny</ActionButton>
        </div>
        <p className={styles.feedback} role="status">{deviceStatus}</p>
      </Panel>}
      <Panel title="Set up an adapter" eyebrow="Consumer repo" icon={<PlugsConnectedIcon weight="regular" aria-hidden="true" />}>
        <div className={styles.shownOnce}>
          <IconTile icon={<PlugsConnectedIcon weight="duotone" />} size="lg" tone="system" />
          <div className={styles.shownOnceBody}>
            <p>An adapter is the CLI package copied into your repo (<code>skills/guidefold/</code> to <code>.agents/skills/guidefold/</code>) that runs SEARCH and USE against this organization with an installation token, and queues the telemetry events this console reads.</p>
            <ol className="grid gap-5">
              {ADAPTER_STEPS.map((step, index) => <li key={step.title} className={styles.stack}>
                <div className={styles.stepText}>
                  <span className={styles.stepNumber} aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                  <strong>{step.title}</strong>
                  <span className={styles.stepDetail}>{step.detail}</span>
                </div>
                <CommandBlock commands={step.command} />
                {index === 2 && (owner
                  ? <ActionButton size="sm" tone="system" href={'#' + createInstallationPanelId}>Open Create an installation</ActionButton>
                  : <p className={styles.help}>Only an owner can create an installation token here; ask one to run this step.</p>)}
              </li>)}
            </ol>
            <p>Once the adapter runs and flushes, <Link to={ctx.href('home', {})}>Overview</Link> stops showing &ldquo;No adapter installed&rdquo; and &ldquo;No telemetry in the last 30d&rdquo;, and <Link to={ctx.href('usage', {})}>Usage &amp; quality</Link> begins to fill in.</p>
          </div>
        </div>
      </Panel>
      <div className={styles.asideColumns}>
        {owner && <Panel title="GitHub App installations" eyebrow="Source connection" icon={<GithubLogoIcon weight="regular" aria-hidden="true" />}>
          {githubInstallations.phase === 'loading' && <RouteState state="loading" title="Reading GitHub installations" description="Waiting for the source connections for this organization." />}
          {githubInstallations.phase === 'error' && githubInstallations.error && <ApiFailure error={githubInstallations.error} onRetry={githubInstallations.reload} retryLabel="Retry GitHub installations" />}
          {githubInstallations.phase === 'ready' && (githubInstallations.value?.length
            ? <DataTable flush caption="GitHub App installations" headings={['Account', 'Repositories', 'Status', 'Action']}>
              {githubInstallations.value.map(entry => <tr key={entry.installation_id}><th scope="row">{entry.account}<span className={styles.linkHint}>Installation {entry.installation_id}</span></th><td>{entry.repositories.length ? entry.repositories.map(repo => repo.full_name).join(', ') : 'No repository list received'}</td><td><StateBadge tone={entry.suspended ? 'warning' : 'system'}>{entry.suspended ? 'suspended' : 'active'}</StateBadge></td><td><ActionButton size="sm" disabled={busy} onClick={() => { void removeGitHubInstallation(entry); }}>Remove</ActionButton></td></tr>)}
            </DataTable>
            : <RouteState state="empty" title="No GitHub App installation" description="Install the Guidefold GitHub App for an organization before choosing repositories. The CLI remains available as a fallback." />)}
        </Panel>}
        <Panel title="Installations" eyebrow="Adapter tokens" icon={<LinkSimpleIcon weight="regular" aria-hidden="true" />}>
          {installations.phase === 'loading' && <RouteState state="loading" title="Reading installations" description="Waiting for the installation list." />}
          {installations.phase === 'error' && installations.error && <ApiFailure error={installations.error} onRetry={installations.reload} retryLabel="Retry the installation list" />}
          {installations.phase === 'ready' && (installations.value?.length
            ? <DataTable flush caption="Installations and adapter health" headings={['Installation', 'Scopes', 'Last seen', 'Adapter version', 'Capabilities', 'Action']}>
              {installations.value.map(entry => <tr key={entry.installation_id}>
                <th scope="row">{entry.name}<span className={styles.linkHint}>{unknown(entry.repo_id)}</span></th>
                <td>{formatList(entry.scopes)}</td>
                <td>{unknown(entry.last_seen_at)}</td>
                <td>{unknown(entry.adapter_version)}</td>
                <td>{formatList(entry.capabilities)}</td>
                <td><ActionButton size="sm" disabled={!owner} onClick={() => { void revoke(entry.installation_id); }}>Revoke</ActionButton></td>
              </tr>)}
            </DataTable>
            : <RouteState state="empty" title="No installation yet" description="Create one to let an adapter read this organization. Absent health values stay Unknown." />)}
          <p className={styles.feedback} role="status">{integrationStatus}</p>
        </Panel>
        <Panel id={createInstallationPanelId} title="Create an installation" eyebrow="Owner" icon={<KeyIcon weight="regular" aria-hidden="true" />}>
          <form className={styles.form} onSubmit={createInstallation}>
            <Field id="installation-name" label="Installation name" hint="Names the machine or harness this token belongs to."><Input id="installation-name" name="name" value={installationName} onChange={event => setInstallationName(event.target.value)} required maxLength={80} disabled={!owner} className={inputClass} /></Field>
            <Field id="installation-harness" label="Harness"><select id="installation-harness" className={selectClass} value={harness} onChange={event => setHarness(event.target.value)} disabled={!owner}><option value="claude">Claude Code</option><option value="copilot">Copilot CLI</option></select></Field>
            <ActionButton type="submit" tone="human" disabled={!owner || busy}>Create installation</ActionButton>
          </form>
          {secret && <ShownOnce title="Installation token" label="Installation token value" value={secret} note="Store this token in your credentials file. It is shown once and is not kept in this browser." />}
        </Panel>
      </div>
    </>}
  </div>;
}
