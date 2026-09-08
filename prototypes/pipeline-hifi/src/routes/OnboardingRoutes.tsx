import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Buildings, CheckCircle, Copy, FileCode, GithubLogo, GoogleLogo, Key, LinkSimple, ShieldCheck, Terminal, Users } from '@phosphor-icons/react';
import { ActionButton, DataTable, Field, MetricRow, Panel, ProvenanceTrail, StateBadge, Tabs, Urn } from '../Shared';
import { fixture, sourceURL, visibleSkills } from '../data';
import type { RouteContext, Skill } from '../domain';
import styles from './OnboardingRoutes.module.css';

type RouteProps = { ctx: RouteContext };
type ImportStep = 'login' | 'organization' | 'preview' | 'result';
const steps: { id: ImportStep; label: string; detail: string }[] = [
  { id: 'login', label: 'Sign in', detail: 'Local provider scenario' },
  { id: 'organization', label: 'Organization', detail: 'Choose the fixture boundary' },
  { id: 'preview', label: 'Preview', detail: 'Inspect the source manifest' },
  { id: 'result', label: 'Import result', detail: 'Read what is available' },
];
const importCommands = 'guidefold login\nguidefold org use meridian\nguidefold scan . --dry-run\nguidefold import .';
const formatNumber = (value: number) => value.toLocaleString('en-US');

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
    <ActionButton onClick={copyCommands}><Copy weight="regular" aria-hidden="true" />Copy proposed commands</ActionButton>
    <p className={styles.feedback} role="status">{status}</p>
  </div>;
}

function AccessNote({ ctx }: RouteProps) {
  if (ctx.canWrite) return null;
  const message = ctx.member
    ? 'Member access is read only here. Import and organization changes require an owner.'
    : ctx.state === 'partial'
      ? 'The partial fixture is available for inspection. Import, membership changes and diagnostics are disabled.'
      : 'This fixture remains available for inspection. New imports, organization changes and diagnostics are disabled while degraded.';
  return <p className={styles.notice}><ShieldCheck weight="regular" aria-hidden="true" /><span>{message}</span></p>;
}

function PartialManifest({ skills }: { skills: Skill[] }) {
  const delivered = new Set(skills.map(skill => skill.id));
  const omitted = fixture.skills.filter(skill => !delivered.has(skill.id));
  return <Panel title="Partial delivery manifest" eyebrow="Simulated QA subset" icon={<FileCode weight="regular" aria-hidden="true" />}>
    <p>The same {skills.length}/{fixture.skills.length} skills are available in Import, Library and Map. Omission is simulated; no repository scan or failure was observed.</p>
    <div className={styles.twoColumns}>
      <details className={styles.disclosure}><summary>Delivered source paths ({skills.length})</summary><ul className={styles.pathList}>{skills.map(skill => <li key={skill.id}><code>{skill.path}</code></li>)}</ul></details>
      <details className={styles.disclosure}><summary>Omitted source paths ({omitted.length})</summary><ul className={styles.pathList}>{omitted.map(skill => <li key={skill.id}><code>{skill.path}</code></li>)}</ul></details>
    </div>
    <p className={styles.help}>No deletion or publication is inferred from this partial snapshot.</p>
  </Panel>;
}

export function ImportRoute({ ctx }: RouteProps) {
  const requested = ctx.params.get('step');
  const fallback: ImportStep = ctx.memory.imported ? 'result' : ctx.memory.org ? 'preview' : ctx.memory.login ? 'organization' : 'login';
  const step = steps.some(item => item.id === requested) ? requested as ImportStep : fallback;
  const currentStep = steps.findIndex(item => item.id === step);
  const skills = visibleSkills(ctx.state);
  const partial = ctx.state === 'partial';
  const sourceBytes = skills.reduce((sum, skill) => sum + skill.bytes, 0);
  const availableScopes = fixture.nodes.filter(node => skills.some(skill => skill.scope === node.id)).length;
  const [provider, setProvider] = useState(ctx.memory.login === 'GitHub' ? 'GitHub' : 'Google');

  function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ctx.canWrite) return;
    ctx.save({ login: provider });
    ctx.go('import', { step: 'organization' });
  }
  function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ctx.canWrite) return;
    ctx.save({ org: true });
    ctx.go('import', { step: 'preview' });
  }
  function simulateImport() {
    if (!ctx.canWrite) return;
    ctx.save({ imported: true });
    ctx.go('import', { step: 'result' });
  }

  return <div className={styles.route}>
    <ol className={styles.steps} aria-label="Fixture import progress">
      {steps.map((item, index) => <li key={item.id} className={index === currentStep ? styles.currentStep : undefined} aria-current={index === currentStep ? 'step' : undefined}>
        <span className={styles.stepNumber} aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
        <div><strong>{item.label}</strong><span>{item.detail}</span></div>
      </li>)}
    </ol>
    <AccessNote ctx={ctx} />

    {step === 'login' && <div className={styles.twoColumns}>
      <Panel title="Sign in to the local scenario" eyebrow="01 / Identity" icon={<ShieldCheck weight="regular" aria-hidden="true" />}>
        <p>Choose a provider for this fixture flow. No account is contacted or authenticated.</p>
        <form className={styles.form} onSubmit={signIn}>
          <fieldset className={styles.providers} disabled={!ctx.canWrite}>
            <legend>Provider</legend>
            <label className={styles.provider}><input type="radio" name="provider" value="Google" checked={provider === 'Google'} onChange={() => setProvider('Google')} /><GoogleLogo weight="regular" aria-hidden="true" /><span>Google <small>Fixture sign-in</small></span></label>
            <label className={styles.provider}><input type="radio" name="provider" value="GitHub" checked={provider === 'GitHub'} onChange={() => setProvider('GitHub')} /><GithubLogo weight="regular" aria-hidden="true" /><span>GitHub <small>Fixture sign-in</small></span></label>
          </fieldset>
          <ActionButton type="submit" tone="human" disabled={!ctx.canWrite}>Continue with selected provider (fixture)<ArrowRight weight="regular" aria-hidden="true" /></ActionButton>
        </form>
      </Panel>
      <Panel title="A bounded source fixture" eyebrow="Import context" icon={<FileCode weight="regular" aria-hidden="true" />}>
        <StateBadge tone="neutral">Local simulation</StateBadge>
        <p>Meridian contains {fixture.skills.length} existing skills and {fixture.nodes.length} declared scope nodes. The next steps expose the manifest before its local result.</p>
        <ProvenanceTrail entries={[
          { label: 'Organization / repository', value: `${fixture.org} / ${fixture.repo}` },
          { label: 'Source', value: 'examples/monorepo', code: true },
          { label: 'Session operator', value: `Fixture operator · ${ctx.member ? 'member' : 'owner'}`, detail: 'Synthetic role for this local scenario.' },
          { label: 'External activity', value: 'None', detail: 'No authentication, upload or repository writes.' },
        ]} />
      </Panel>
    </div>}

    {step === 'organization' && <div className={styles.twoColumns}>
      <Panel title="Create the fixture organization" eyebrow="02 / Organization" icon={<Buildings weight="regular" aria-hidden="true" />}>
        <p>Continue as Fixture operator{ctx.memory.login ? ` through ${ctx.memory.login} (simulated)` : ''}. This step creates local scenario state only.</p>
        <form className={styles.form} onSubmit={createOrganization}>
          <Field id="org-name" label="Organization name" hint="The public Meridian fixture is the only organization in this scenario."><input id="org-name" name="org" value={fixture.org} readOnly aria-describedby="org-name-hint" /></Field>
          <ActionButton type="submit" tone="human" disabled={!ctx.canWrite}>Create meridian (fixture)<ArrowRight weight="regular" aria-hidden="true" /></ActionButton>
        </form>
      </Panel>
      <Panel title="Organization boundary" eyebrow="Access context" icon={<ShieldCheck weight="regular" aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          { label: 'Repository', value: fixture.repo },
          { label: 'Role', value: ctx.member ? 'Member · read and feedback' : 'Owner · local scenario' },
          { label: 'Membership', value: 'Simulated only', detail: 'No real accounts or access grants are created.' },
          { label: 'Source ownership', value: 'Metadata only', detail: 'Source owner strings and CODEOWNERS do not authorize access.' },
        ]} />
      </Panel>
    </div>}

    {step === 'preview' && <>
      <MetricRow items={[
        { label: 'Selected source files', value: partial ? `${skills.length}/${fixture.skills.length}` : String(skills.length), detail: 'Existing SKILL.md files' },
        { label: 'Declared scope nodes', value: String(fixture.nodes.length), detail: 'From the source scope map' },
        { label: 'Source bytes', value: formatNumber(sourceBytes), detail: 'Exact selected fixture files' },
      ]} />
      <div className={styles.asideColumns}>
        <Panel title="Local manifest preview" eyebrow="03 / Inspect before import" icon={<FileCode weight="regular" aria-hidden="true" />}>
          <p>The manifest contains {skills.length} selected fixture sources for <strong>{fixture.org} / {fixture.repo}</strong>. This preview is not a completed repository scan.</p>
          <ProvenanceTrail entries={[
            { label: 'Base commit', value: <Urn value={fixture.commit} /> },
            { label: 'Source bytes', value: `${formatNumber(sourceBytes)} bytes`, detail: 'Calculated from the selected fixture files.' },
            { label: 'Exclusions', value: 'Not evaluated', detail: 'A real dry-run must show ignored files, secrets policy and required assets before upload.' },
          ]} />
          <details className={styles.disclosure}>
            <summary>Inspect files, hashes and sizes ({skills.length})</summary>
            <DataTable caption="Selected source manifest" headings={['Source path', 'Bytes', 'SHA-256']}>
              {skills.map(skill => <tr key={skill.id}><td className={styles.pathCell}><a href={sourceURL(skill.path)} target="_blank" rel="noreferrer">{skill.path}<span className={styles.linkHint}>GitHub, new tab</span></a></td><td>{formatNumber(skill.bytes)}</td><td className={styles.hashCell}><code>{skill.revision}</code></td></tr>)}
            </DataTable>
          </details>
          <div className={styles.actionFooter}><p className={styles.help}>The fixture is already parsed. No scan, upload or LLM job runs.</p><ActionButton tone="human" onClick={simulateImport} disabled={!ctx.canWrite}>Simulate import<ArrowRight weight="regular" aria-hidden="true" /></ActionButton></div>
        </Panel>
        <Panel title="Dry-run preview" eyebrow="Proposed CLI" icon={<Terminal weight="regular" aria-hidden="true" />}>
          <StateBadge tone="neutral">Proposed CLI</StateBadge>
          <p>Planned product syntax for a local repository. Copying these commands does not execute them.</p>
          <CommandBlock commands={importCommands} />
        </Panel>
      </div>
    </>}

    {step === 'result' && <>
      <MetricRow items={[
        { label: 'Available skills', value: partial ? `${skills.length}/${fixture.skills.length}` : String(skills.length), detail: partial ? `${fixture.skills.length - skills.length} paths omitted in this QA scenario` : 'Existing fixture skills parsed' },
        { label: partial ? 'Scopes with delivered skills' : 'Declared scope nodes', value: partial ? `${availableScopes}/${fixture.nodes.length}` : String(fixture.nodes.length), detail: 'Unmapped scopes remain explicit' },
        { label: 'Publication', value: partial ? 'Unavailable' : 'Not established', detail: 'Import is separate from publication' },
      ]} />
      <Panel title={partial ? 'Import result · partial QA subset' : 'Import result (fixture)'} eyebrow="04 / Read the result" icon={<CheckCircle weight="regular" aria-hidden="true" />} action={<StateBadge tone={partial ? 'warning' : 'system'}>{partial ? 'Partial snapshot' : 'Parsed · ready to browse'}</StateBadge>}>
        <p>{partial ? `The ${skills.length} delivered source files are available for reading. ${fixture.skills.length - skills.length} source paths were deliberately omitted from this local scenario.` : `${fixture.skills.length} existing skills and ${fixture.nodes.length} scope nodes are read from the embedded Meridian fixture.`} No network upload, scan, LLM generation or publication occurred.</p>
        <ProvenanceTrail entries={[
          { label: 'Source', value: 'examples/monorepo', code: true },
          { label: 'Base commit', value: <Urn value={fixture.commit} /> },
          { label: 'Publication', value: partial ? 'Unavailable · partial QA data cannot activate a snapshot' : 'Not established · owner review is still required' },
          { label: 'Ignored sources', value: 'Unknown', detail: 'The fixture contains selected skills only.' },
        ]} />
        <div className={styles.actions}><ActionButton href={ctx.href('map', { step: null, tab: 'repository' })} tone="human">{partial ? 'Open partial Map' : 'Open Map'}<ArrowRight weight="regular" aria-hidden="true" /></ActionButton><Link to={ctx.href('library', { step: null })}>Open Library</Link></div>
      </Panel>
    </>}
    {partial && <PartialManifest skills={skills} />}
  </div>;
}

export function OrganizationRoute({ ctx }: RouteProps) {
  const tab = ctx.params.get('tab') === 'integrations' ? 'integrations' : 'members';
  const [label, setLabel] = useState('');
  const [memberError, setMemberError] = useState('');
  const [memberStatus, setMemberStatus] = useState('');
  const [adapter, setAdapter] = useState('claude');
  const [integrationStatus, setIntegrationStatus] = useState('');
  const members = ctx.memory.members ?? [];
  const commands = `guidefold install --harness ${adapter}\nguidefold doctor`;

  function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ctx.canWrite) return;
    const value = label.trim();
    if (!value) { setMemberError('Enter a label for this local member entry.'); return; }
    if (members.some(member => member.toLowerCase() === value.toLowerCase())) { setMemberError('This label already exists in the local scenario.'); return; }
    ctx.save({ members: [...members, value] });
    setLabel('');
    setMemberError('');
    setMemberStatus('Local member entry created. No invitation was sent.');
  }
  function removeMember(index: number) {
    if (!ctx.canWrite) return;
    ctx.save({ members: members.filter((_, memberIndex) => memberIndex !== index) });
    setMemberStatus('Local member entry removed. No real access changed.');
  }
  function checkConnection() {
    if (!ctx.canWrite) return;
    ctx.save({ connection: true });
    setIntegrationStatus('Local check complete. Actual adapter connection, download verification and context loaded remain Unknown.');
  }
  function changeToken() {
    if (!ctx.canWrite) return;
    ctx.save({ token: !ctx.memory.token });
    setIntegrationStatus('Token lifecycle simulated. No credential was issued or revoked.');
  }

  return <div className={styles.route}>
    <p className={styles.intro}>Inspect organization access and adapter evidence for <strong>{fixture.org}</strong>. All changes are local simulations.</p>
    <Tabs label="Organization sections" current={tab} items={[
      { id: 'members', label: 'Members', href: ctx.href('organization', { tab: 'members' }) },
      { id: 'integrations', label: 'Integrations', href: ctx.href('organization', { tab: 'integrations' }) },
    ]} />
    <AccessNote ctx={ctx} />
    {tab === 'members' ? <div className={styles.asideColumns}>
      <Panel title="Members" eyebrow="Organization access" icon={<Users weight="regular" aria-hidden="true" />} action={<StateBadge>Local scenario</StateBadge>}>
        <p>Only the fixture operator is supplied. Source owner strings name teams in metadata; they are not member accounts.</p>
        <DataTable caption="Local membership scenario" headings={['Member', 'Role', 'Access', 'Action']}>
          <tr><th scope="row">Fixture operator<span className={styles.linkHint}>Synthetic session role</span></th><td><StateBadge tone={ctx.member ? 'neutral' : 'human'}>{ctx.member ? 'Member' : 'Owner'}</StateBadge></td><td>Permitted fixture repositories</td><td><ActionButton disabled>Remove operator</ActionButton><span className={styles.linkHint}>{ctx.member ? 'Owner required' : 'Last owner cannot be removed'}</span></td></tr>
          {members.map((member, index) => <tr key={`${member}-${index}`}><th scope="row" className={styles.pathCell}>{member}<span className={styles.linkHint}>Local entry</span></th><td><StateBadge>Member</StateBadge></td><td>Simulated only</td><td><ActionButton disabled={!ctx.canWrite} onClick={() => removeMember(index)}>Remove local entry</ActionButton></td></tr>)}
        </DataTable>
        {members.length === 0 && <p className={styles.help}>No additional local members. Add a test label to exercise the membership flow.</p>}
        <form className={styles.memberForm} onSubmit={addMember}>
          <Field id="member-label" label="Member label for local simulation" hint="No email address is required. No invitation is sent." error={memberError || undefined}><input id="member-label" name="member" value={label} onChange={event => { setLabel(event.target.value); setMemberError(''); }} required maxLength={80} disabled={!ctx.canWrite} placeholder="Enter a test label" aria-describedby={memberError ? 'member-label-hint member-label-error' : 'member-label-hint'} aria-invalid={Boolean(memberError)} /></Field>
          <ActionButton type="submit" tone="human" disabled={!ctx.canWrite}>Add local member</ActionButton>
        </form>
        <p className={styles.feedback} role="status">{memberStatus}</p>
      </Panel>
      <Panel title="Organization boundary" eyebrow="Permission context" icon={<ShieldCheck weight="regular" aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          { label: 'Organization', value: `${fixture.org} (fixture)` },
          { label: 'Repository', value: fixture.repo },
          { label: 'Permission model', value: 'Owner / member scenario', detail: 'CODEOWNERS and source owner metadata do not authorize access.' },
          { label: 'Last owner', value: 'Removal blocked', detail: 'The fixture operator remains the owner in the owner scenario.' },
          { label: 'Organization switching', value: 'One fixture organization', detail: 'A foreign organization or repository URL has no authorized fixture content.' },
        ]} />
      </Panel>
    </div> : <>
      <div className={styles.twoColumns}>
        <Panel title="Install an adapter" eyebrow="Proposed CLI" icon={<Terminal weight="regular" aria-hidden="true" />}>
          <p>Commands below are proposed product syntax. The prototype does not install an adapter or contact a harness.</p>
          <div className={styles.form}><Field id="adapter" label="Adapter scenario"><select id="adapter" value={adapter} onChange={event => setAdapter(event.target.value)}><option value="claude">Claude Code</option><option value="copilot">Copilot CLI</option></select></Field><CommandBlock key={adapter} commands={commands} /></div>
          <div className={styles.actionFooter}><ActionButton tone="human" disabled={!ctx.canWrite} onClick={checkConnection}><LinkSimple weight="regular" aria-hidden="true" />Simulate connection check</ActionButton><p className={styles.feedback} role="status">{integrationStatus || (ctx.memory.connection ? 'Local check complete. Actual adapter connection and delivery remain Unknown.' : 'No local connection check has been run.')}</p></div>
        </Panel>
        <Panel title="Connection evidence" eyebrow="Observed status" icon={<LinkSimple weight="regular" aria-hidden="true" />} action={<StateBadge>Unknown</StateBadge>}>
          <p>No installed adapter or delivery observations are supplied by this fixture.</p>
          <ProvenanceTrail entries={[
            { label: 'Repository / organization', value: `${fixture.repo} / ${fixture.org}` },
            { label: 'Installation scope', value: 'Unknown', detail: 'No adapter configuration.' },
            { label: 'Adapter connection', value: 'Unknown', detail: 'No verified connection.' },
            { label: 'download_verified', value: 'Unknown', detail: 'No download or checksum observations.' },
            { label: 'context_loaded', value: 'Unknown', detail: 'No adapter acknowledgement.' },
            { label: 'Version / capabilities', value: 'Unknown', detail: 'No adapter handshake.' },
          ]} />
        </Panel>
      </div>
      <Panel title="Token lifecycle" eyebrow="Local exercise" icon={<Key weight="regular" aria-hidden="true" />}>
        <p>No real tokens are available or issued. Use this local exercise to preview token creation and revocation.</p>
        <details className={styles.disclosure}><summary>Local token lifecycle exercise</summary><div className={styles.tokenExercise}><StateBadge tone={ctx.memory.token ? 'system' : 'neutral'}>Scenario token: {ctx.memory.token ? 'present' : 'absent'}</StateBadge><p className={styles.help}>No credential value exists. The state does not grant access.</p><ActionButton disabled={!ctx.canWrite} onClick={changeToken}>{ctx.memory.token ? 'Simulate token revocation' : 'Simulate token creation'}</ActionButton></div></details>
      </Panel>
    </>}
  </div>;
}

