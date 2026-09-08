import {useState, type FormEvent} from 'react';
import {Link} from 'react-router-dom';
import {ArrowDown, ArrowSquareOut, Check, DownloadSimple, FileText, GitBranch, ListChecks, PencilSimple, X} from '@phosphor-icons/react';
import {ActionButton, DataTable, Field, MetricRow, Panel, ProvenanceTrail, SkillContent, SkillDiff, StateBadge, Urn} from '../Shared';
import {bodyPrefix, defaultProposal, digest, findSkill, fixture, proposalSkill, sourceURL} from '../data';
import type {Proposal, ProposalStage, RouteContext} from '../domain';
import styles from './ReviewRoutes.module.css';

type Props = {ctx: RouteContext};
const stageNames: Record<ProposalStage, string> = {
  draft: 'Draft', editing: 'Editing local candidate', approved_for_export: 'Approved for export',
  awaiting_git: 'Awaiting Git', published: 'Published (fixture)', rejected: 'Rejected (local decision)',
};
const jumpLabels: Record<ProposalStage, string> = {
  draft: 'Review decision: approve, edit or reject', editing: 'Continue editing candidate',
  approved_for_export: 'Continue to export', awaiting_git: 'Review Git handoff',
  published: 'Review publication evidence', rejected: 'Review rejection reason',
};
const decisionOptions = [
  {value: 'approve', label: 'Approve for export', detail: 'Prepare this candidate file for a Git handoff.', icon: Check},
  {value: 'edit', label: 'Edit candidate', detail: 'Change the Markdown body and review a new local draft.', icon: PencilSimple},
  {value: 'reject', label: 'Reject', detail: 'Close this local proposal and retain your reason.', icon: X},
] as const;

function ReadOnlyNotice({ctx}: Props) {
  if (ctx.canWrite) return null;
  const message = ctx.state === 'partial'
    ? 'Partial import: the source snapshot is incomplete. Decisions and export are blocked until a complete source snapshot is available.'
    : ctx.state === 'degraded'
      ? 'Degraded connection: showing the available local fixture. Decisions, edits, export and Git simulation are unavailable.'
      : 'Read-only member access. You can inspect the source and candidate; proposal decisions and export require an owner.';
  return <p className={styles.notice} role="status"><StateBadge tone="warning">Read only</StateBadge>{message}</p>;
}

function ContentPreview({body, raw, candidate}: {body: string; raw: string; candidate?: boolean}) {
  const subject = candidate ? 'candidate' : 'source';
  return <div className={styles.contentPreview}>
    <details className={styles.disclosure}>
      <summary>Read {subject} body</summary>
      <div className={styles.bodyPreview}>
        <a className={styles.jumpLink} href="#decision"><ArrowDown aria-hidden="true" />Jump to decision and publication</a>
        <SkillContent content={body} />
        <a className={styles.jumpLink} href="#decision"><ArrowDown aria-hidden="true" />Jump to decision and publication</a>
      </div>
    </details>
    <details className={styles.disclosure}>
      <summary>Full {candidate ? 'candidate' : 'original'} SKILL.md · raw file</summary>
      <pre className={styles.raw} tabIndex={0} aria-label={`${candidate ? 'Candidate' : 'Original'} SKILL.md source text`}>{raw}</pre>
    </details>
  </div>;
}

export function ProposalsRoute({ctx}: Props) {
  const source = proposalSkill;
  const prefix = bodyPrefix(source);
  const saved = ctx.memory.proposal;
  const proposal: Proposal = saved?.candidate.startsWith(prefix) ? saved : defaultProposal();
  const {stage, candidate} = proposal;
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const locked = !ctx.canWrite || busy;
  const changed = candidate !== source.raw;
  const candidateBody = candidate.slice(prefix.length);
  const save = (patch: Partial<Proposal>) => {
    ctx.save({proposal: {...proposal, ...patch}});
    if (patch.stage) window.requestAnimationFrame(() => document.getElementById("decision")?.focus());
  };
  const fail = (message: string) => {setError(message); setNotice('');};

  async function recordDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked) return;
    const values = new FormData(event.currentTarget);
    const decision = String(values.get('decision') ?? '');
    const reason = String(values.get('reason') ?? '').trim();
    if (!reason || !['approve', 'edit', 'reject'].includes(decision)) {fail('Choose a decision and explain your reason.'); return;}
    setBusy(true); setError('');
    try {
      const revision = await digest(candidate);
      save({reason, digest: revision, stage: decision === 'approve' ? 'approved_for_export' : decision === 'edit' ? 'editing' : 'rejected'});
      setNotice('Decision saved in this local session.');
    } catch {fail('The candidate digest could not be computed. No decision was saved.');}
    finally {setBusy(false);}
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (locked) return;
    const values = new FormData(event.currentTarget);
    const body = String(values.get('candidate') ?? '');
    const reason = String(values.get('reason') ?? '').trim();
    if (!body.trim() || !reason) {fail('A candidate body and edit reason are required.'); return;}
    const nextCandidate = prefix + body;
    setBusy(true); setError('');
    try {
      const revision = await digest(nextCandidate);
      save({candidate: nextCandidate, digest: revision, reason, stage: 'draft'});
      setNotice('Local draft saved. Review the line diff and record a new decision.');
    } catch {fail('The candidate digest could not be computed. Your edit remains in the form.');}
    finally {setBusy(false);}
  }

  async function exportCandidate() {
    if (locked || stage !== 'approved_for_export') return;
    setBusy(true); setError('');
    try {
      const revision = await digest(candidate);
      const blob = new Blob([candidate], {type: 'text/markdown;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = 'postgres-auth.SKILL.md';
      document.body.append(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      save({digest: revision, stage: 'awaiting_git'});
      setNotice('SKILL.md download started. The local scenario is now Awaiting Git.');
    } catch {fail('The file could not be prepared. The candidate remains approved for export.');}
    finally {setBusy(false);}
  }

  return <div className={styles.route}>
    <ReadOnlyNotice ctx={ctx} />
    <section className={styles.summary} aria-label="Proposal status and evidence">
      <div className={styles.summaryHeading}>
        <div><span className={styles.eyebrow}>Source candidate</span><h2 className={styles.name}>{source.name}</h2></div>
        <StateBadge tone={stage === 'published' ? 'system' : 'human'}>{stageNames[stage]}</StateBadge>
      </div>
      <p>Review the existing skill file as a candidate revision. This fixture introduces no new procedure and claims no source problem.</p>
      <div className={styles.summaryEvidence}>
        <span><strong>Evidence level</strong>Local simulation only</span>
        <span><strong>Context loaded</strong>Unknown · no adapter observations</span>
      </div>
      <div className={styles.actions}>
        <a className={styles.jumpLink} href="#decision"><ArrowDown aria-hidden="true" />{jumpLabels[stage]}</a>
        <Link to={ctx.href('skill', {skill: source.id, revision: source.revision, tab: 'source', from: 'proposals'})}>Inspect source and scope</Link>
      </div>
    </section>

    <div className={styles.comparison}>
      <Panel title="Source" eyebrow="Exact imported revision" icon={<FileText aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          {label: 'Scope', value: source.scope, code: true},
          {label: 'Owner', value: source.owner},
          {label: 'Source layer / Knowledge layer', value: `${source.sourceLayer} / ${source.knowledgeLayer}`},
          {label: 'Source status', value: source.sourceStatus, detail: 'Publication at import: not established'},
          {label: 'Source path', value: source.path, href: sourceURL(source.path), code: true},
          {label: 'Commit', value: fixture.commit, code: true},
          {label: 'SHA-256', value: source.revision, code: true},
        ]} />
        <div className={styles.actions}><a href={sourceURL(source.path)} target="_blank" rel="noreferrer">Open source in Git <ArrowSquareOut aria-hidden="true" /></a></div>
        <ContentPreview body={source.body} raw={source.raw} />
      </Panel>
      <Panel title="Candidate" eyebrow={changed ? 'Local operator edit' : 'Unchanged source'} icon={<GitBranch aria-hidden="true" />}>
        <div className={styles.candidateState}><StateBadge tone={changed ? 'human' : 'neutral'}>{changed ? 'Text changed by local operator' : 'No text changes'}</StateBadge></div>
        <ProvenanceTrail entries={[
          {label: 'Scope', value: source.scope, code: true, detail: 'Same scope as the source'},
          {label: 'Source owner', value: source.owner},
          {label: 'Source layer / Knowledge layer', value: `${source.sourceLayer} / ${source.knowledgeLayer}`},
          {label: 'Candidate SHA-256', value: proposal.digest, code: true},
          {label: 'Export artifact', value: 'postgres-auth.SKILL.md', detail: 'Complete candidate file; referenced resources are not bundled.'},
        ]} />
        <ContentPreview body={candidateBody} raw={candidate} candidate />
      </Panel>
    </div>

    <Panel title="Source to candidate" eyebrow="Line diff" icon={<ListChecks aria-hidden="true" />}>
      <p className={styles.panelNote}>The complete files are compared. Frontmatter, scope, owner and declared relationships stay fixed.</p>
      <SkillDiff source={source.raw} candidate={candidate} />
      <details className={styles.disclosure}>
        <summary>Declared requirements and references</summary>
        <div className={styles.references}>
          <h3>Requires</h3>{source.requires.map(id => <Urn key={id} value={id} />)}
          <h3>Refines</h3>{source.refines.map(id => <Urn key={id} value={id} />)}
          <h3>Source references</h3>{source.references.map(path => <a key={path} href={sourceURL(path)} target="_blank" rel="noreferrer">{path}</a>)}
        </div>
      </details>
    </Panel>

    <div id="decision" tabIndex={-1} className={styles.decisionAnchor}>
      <Panel title="Decision and publication" eyebrow="Local fixture workflow" icon={<GitBranch aria-hidden="true" />}>
        <div className={styles.decisionContent}>
          <p className={styles.muted}>Source: Meridian fixture · Reviewer: Fixture operator ({ctx.member ? 'member' : 'owner'} role). Decisions require an owner.</p>
          <ol className={styles.lifecycle} aria-label="Publication lifecycle">
            {(['draft', 'approved_for_export', 'awaiting_git', 'published'] as const).map(item => <li key={item} aria-current={stage === item ? 'step' : undefined}><StateBadge tone={stage === item ? 'human' : 'neutral'}>{stageNames[item]}</StateBadge></li>)}
          </ol>

          {stage === 'draft' && <form id="decision-form" className={styles.form} onSubmit={recordDecision}>
            <fieldset disabled={locked} className={styles.choices}>
              <legend>Review decision</legend>
              {decisionOptions.map(({value, label, detail, icon: Icon}) => <label key={value} className={styles.choice}>
                <input type="radio" name="decision" value={value} required />
                <Icon aria-hidden="true" />
                <span><strong>{label}</strong><span>{detail}</span></span>
              </label>)}
            </fieldset>
            <Field id="decision-reason" label="Reason for this decision" hint="Explain the source and scope considered. Required for every decision.">
              <textarea id="decision-reason" name="reason" defaultValue={proposal.reason} required disabled={locked} className={styles.reason} />
            </Field>
            <div className={styles.actions}><ActionButton tone="human" type="submit" disabled={locked}>{busy ? 'Saving local decision…' : 'Record decision (local)'}</ActionButton></div>
          </form>}

          {stage === 'editing' && <form id="edit-form" className={styles.form} onSubmit={saveEdit}>
            <Field id="candidate-text" label="Candidate body · local operator edit" hint="Only the Markdown body is editable. Original frontmatter remains fixed.">
              <textarea id="candidate-text" name="candidate" defaultValue={candidateBody} required disabled={locked} className={styles.bodyEditor} spellCheck={false} />
            </Field>
            <Field id="edit-reason" label="Reason for the edit" hint="Saving returns this candidate to Draft for a new review decision.">
              <textarea id="edit-reason" name="reason" defaultValue={proposal.reason} required disabled={locked} className={styles.reason} />
            </Field>
            <div className={styles.actions}>
              <ActionButton tone="human" type="submit" disabled={locked}>{busy ? 'Computing SHA-256…' : 'Save local draft'}</ActionButton>
              <ActionButton disabled={locked} onClick={() => {save({stage: 'draft'}); setError(''); setNotice('Unsaved body edits discarded.');}}>Cancel edit</ActionButton>
            </div>
          </form>}

          {stage === 'approved_for_export' && <div className={styles.stageContent}>
            <p>The candidate is approved for a Git handoff. Download the exact candidate bytes and compare the file against the source commit.</p>
            <p className={styles.muted}>Export includes SKILL.md only. This local action does not create a commit, publish a revision or confirm usefulness.</p>
            <div className={styles.actions}><ActionButton id="export-patch" tone="human" disabled={locked} onClick={exportCandidate}><DownloadSimple aria-hidden="true" />{busy ? 'Preparing candidate…' : 'Export SKILL.md'}</ActionButton></div>
          </div>}

          {stage === 'awaiting_git' && <div className={styles.stageContent}>
            <p><strong>File exported. Waiting for Git review and sync.</strong> Export alone does not publish this revision.</p>
            <ol className={styles.steps}>
              <li>Compare the downloaded file with the source at the imported commit.</li>
              <li>Review and merge any changes in Git. An unchanged source file needs no new commit.</li>
              <li>A sync verifies the revision and publication policy.</li>
            </ol>
            <p className={styles.muted}>The prototype cannot observe these events. The action below advances the local scenario without contacting Git.</p>
            <div className={styles.actions}><ActionButton id="simulate-sync" tone="human" disabled={locked} onClick={() => {save({stage: 'published'}); setNotice('Git sync simulated locally. No real publication or context load was verified.');}}><GitBranch aria-hidden="true" />Simulate Git sync</ActionButton></div>
          </div>}

          {stage === 'published' && <div className={styles.stageContent}>
            <p><strong>Published (fixture)</strong> is the final state of this local scenario. No Git merge, server publication or agent load was verified.</p>
            <ProvenanceTrail entries={[
              {label: 'Evidence level', value: 'Local simulation only'},
              {label: 'Revision', value: proposal.digest, code: true},
              {label: 'Context loaded', value: 'Unknown', detail: 'No adapter observations'},
            ]} />
            <div className={styles.actions}><ActionButton tone="system" href={ctx.href('usage', {skill: source.id, scope: source.scope, revision: proposal.digest, from: 'proposals'})}>Check usage evidence</ActionButton></div>
          </div>}

          {stage === 'rejected' && <div className={styles.stageContent}>
            <p>This local candidate was rejected. No export or publication took place.</p>
            <p><strong>Reason:</strong> {proposal.reason}</p>
            <div className={styles.actions}><ActionButton disabled={locked} onClick={() => {save({stage: 'draft'}); setNotice('Proposal reopened as a local draft.');}}>Reopen as local draft</ActionButton></div>
          </div>}

          {proposal.reason && !['draft', 'editing', 'rejected'].includes(stage) && <p className={styles.reasonRecord}><strong>Decision reason</strong>{proposal.reason}</p>}
          {error && <p className={styles.error} role="alert">{error}</p>}
          <p className={styles.status} role="status" aria-live="polite">{notice}</p>
        </div>
      </Panel>
    </div>
  </div>;
}

const evidenceRows = [
  ['Card exposures', 'No adapter delivery events'],
  ['download_verified', 'No checksum or download events from an adapter'],
  ['context_loaded', 'No adapter acknowledgement that instructions entered model context'],
  ['Applied · reported / observed', 'No attributed task episodes'],
  ['Helpfulness', 'No helped or hindered assessments; denominator unavailable'],
  ['Feedback coverage', 'No eligible episode identifiers; denominator unavailable'],
  ['Integration lag or losses', 'No connection health observations'],
];

export function UsageRoute({ctx}: Props) {
  const params = ctx.params;
  const selectedSkill = findSkill(params.get('skill'));
  const scopes = [...new Set(fixture.skills.map(skill => skill.scope))].sort();
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    ctx.go('usage', Object.fromEntries(['scope', 'skill', 'revision', 'harness'].map(key => [key, String(form.get(key) ?? '').trim() || null])));
  }
  return <div className={styles.route}>
    {ctx.state === 'partial' && <p className={styles.notice} role="status"><StateBadge tone="warning">Partial</StateBadge>Import coverage is limited. No event ledger or eligible-episode denominator is available; observation coverage remains Unknown.</p>}
    {ctx.state === 'degraded' && <p className={styles.notice} role="status"><StateBadge tone="warning">Degraded</StateBadge>Showing the available fixture context. There is no saved event report to refresh; delivery and outcomes remain Unknown.</p>}
    <MetricRow items={[
      {label: 'Delivery', value: 'Unknown', detail: 'No adapter event ledger'},
      {label: 'Helpfulness', value: 'Unknown', detail: 'No attributed assessments'},
      {label: 'Observation coverage', value: 'Unknown', detail: 'Eligible episodes unavailable'},
    ]} />
    <Panel title="Review queue" eyebrow="Evidence before action" icon={<ListChecks aria-hidden="true" />}>
      <div className={styles.queueEmpty}>
        <StateBadge>No observations</StateBadge>
        <p>This source fixture contains no adapter events, feedback episodes or verified publication records. Missing telemetry does not prove a skill is unused or incorrect.</p>
      </div>
      <DataTable caption="Reason-driven review queue" headings={['Skill and revision', 'Reason', 'Evidence', 'Owner action']}>
        <tr><td colSpan={4}>No observed items. A review item needs a source change, removal or feedback event before an owner can record Checked, Fixed in Git, or No change with a reason.</td></tr>
      </DataTable>
      <div className={styles.actions}><ActionButton tone="system" href={ctx.href('organization', {tab: 'integrations', from: 'usage'})}>Inspect integration setup</ActionButton></div>
    </Panel>
    <Panel title="Observation context" eyebrow="Filters preserved in the URL" icon={<FileText aria-hidden="true" />}>
      <form key={params.toString()} id="usage-filters" className={styles.filters} onSubmit={filter}>
        <Field id="usage-scope" label="Scope"><select id="usage-scope" name="scope" defaultValue={params.get('scope') || ''}><option value="">All fixture scopes</option>{scopes.map(scope => <option key={scope} value={scope}>{scope}</option>)}</select></Field>
        <Field id="usage-skill" label="Skill"><select id="usage-skill" name="skill" defaultValue={params.get('skill') || ''}><option value="">All fixture skills</option>{fixture.skills.map(skill => <option key={skill.id} value={skill.id}>{skill.name}</option>)}</select></Field>
        <Field id="revision" label="Revision" hint="Optional full SHA-256"><input id="revision" name="revision" defaultValue={params.get('revision') || ''} placeholder="Any revision" spellCheck={false} /></Field>
        <Field id="harness" label="Harness" hint="No harness observed in this fixture"><input id="harness" name="harness" defaultValue={params.get('harness') || ''} placeholder="Unknown · no events" /></Field>
        <div className={styles.filterAction}><ActionButton type="submit">Apply observation filters</ActionButton></div>
      </form>
      <div className={styles.contextSummary}>
        <p><strong>Window:</strong> Unknown · <strong>Source:</strong> no event ledger · <strong>Coverage:</strong> Unknown</p>
        {selectedSkill && <p><Link to={ctx.href('skill', {skill: selectedSkill.id, from: 'usage', tab: 'content'})}>Inspect {selectedSkill.name}</Link><span className={styles.muted}> · {selectedSkill.scope}</span></p>}
        {params.get('revision') && <p className={styles.revision}><strong>Selected revision</strong><code>{params.get('revision')}</code></p>}
      </div>
      <DataTable caption="Delivery and outcome evidence" headings={['Measure', 'Value', 'Why it is unknown']}>
        {evidenceRows.map(([measure, why]) => <tr key={measure}><th scope="row">{measure}</th><td><StateBadge>Unknown</StateBadge></td><td>{why}</td></tr>)}
      </DataTable>
      <p className={styles.panelNote}>Published and loaded are separate. A download or HTTP success would not prove the instruction reached the model context.</p>
      {params.get('from') === 'proposals' && <div className={styles.actions}><Link to={ctx.href('proposals', {skill: proposalSkill.id})}>Return to proposal</Link></div>}
    </Panel>
  </div>;
}
