import {useState, type FormEvent} from 'react';
import {Link} from 'react-router-dom';
import {ArrowLeft, ArrowSquareOut, ChatText, FileText, FolderSimple, Funnel, GitBranch, LinkSimple, Stack, TreeStructure} from '@phosphor-icons/react';
import {ActionButton, DataTable, Field, Panel, ProvenanceTrail, ScopeTree, SkillContent, StateBadge, Tabs, Urn} from '../Shared';
import {findSkill, fixture, proposalSkill, sourceURL, visibleSkills} from '../data';
import type {Params, RouteContext, Skill, TreeNode, View} from '../domain';
import styles from './CatalogRoutes.module.css';

type RouteProps = {ctx: RouteContext};
type MapAxis = 'repository' | 'scopes' | 'pyramid';
const axes: MapAxis[] = ['repository', 'scopes', 'pyramid'];
const filterFields = [
  {key: 'scope', label: 'Scope', field: 'scope'},
  {key: 'owner', label: 'Owner from source', field: 'owner'},
  {key: 'layer', label: 'Source layer', field: 'sourceLayer'},
  {key: 'status', label: 'Source status', field: 'sourceStatus'},
] as const;
const clearFilters: Params = {q: null, scope: null, owner: null, layer: null, status: null};
const mapAxis = (ctx: RouteContext): MapAxis => axes.includes(ctx.params.get('tab') as MapAxis) ? ctx.params.get('tab') as MapAxis : 'repository';
const originView = (ctx: RouteContext): View => ['map', 'library', 'proposals', 'usage'].includes(ctx.params.get('from') || '') ? ctx.params.get('from') as View : 'library';
const originNames: Partial<Record<View, string>> = {map: 'Map', library: 'Library', proposals: 'Proposals', usage: 'Usage & quality'};

function CatalogNotice({ctx}: RouteProps) {
  if (ctx.state !== 'partial' && ctx.state !== 'degraded') return null;
  return <div className={styles.notice} role="status">
    <StateBadge tone="warning">{ctx.state === 'partial' ? 'Partial snapshot' : 'From memory'}</StateBadge>
    <span>{ctx.state === 'partial'
      ? `${visibleSkills(ctx.state).length}/${fixture.skills.length} fixture skills are available. Source paths were deliberately omitted from this local QA snapshot.`
      : 'Reading the last available fixture snapshot. New notes cannot be saved while the connection is unavailable.'}</span>
  </div>;
}

function SourceLink({path, label}: {path: string; label?: string}) {
  return <a className={styles.sourceLink} href={sourceURL(path.split('#')[0])} target="_blank" rel="noopener noreferrer">
    <span>{label || path.split('#')[0]}</span><ArrowSquareOut weight="regular" aria-hidden="true" /><span className={styles.externalLabel}>GitHub · new tab</span>
  </a>;
}

function Relations({ctx, skill, axis}: RouteProps & {skill: Skill; axis?: MapAxis}) {
  const from = axis ? 'map' : originView(ctx);
  const returnTab = axis || ctx.params.get('return_tab');
  return <div className={styles.relations}>{(['requires', 'refines'] as const).map(type => <section key={type}>
    <h3 className={styles.relationHeading}><LinkSimple weight="regular" aria-hidden="true" />{type}</h3>
    {skill[type].length ? <ul className={styles.relationList}>{skill[type].map(id => {
      const target = findSkill(id);
      const delivered = visibleSkills(ctx.state).some(item => item.id === id);
      return <li key={id}>{target ? <Link to={ctx.href('skill', {skill: id, revision: target.revision, tab: 'source', from, return_tab: returnTab})}>{target.name}</Link> : <strong>Unresolved source declaration</strong>}
        <code>{id}</code>{target && !delivered && <span className={styles.muted}>Source omitted from this snapshot.</span>}
      </li>;
    })}</ul> : <p className={styles.muted}>None declared in source.</p>}
  </section>)}</div>;
}

export function LibraryRoute({ctx}: RouteProps) {
  const q = ctx.params.get('q') || '';
  const skills = visibleSkills(ctx.state);
  const words = q.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const matches = skills.filter(skill => words.every(word => `${skill.name} ${skill.description} ${skill.path}`.toLowerCase().includes(word)) && filterFields.every(({key, field}) => !ctx.params.get(key) || skill[field] === ctx.params.get(key)));
  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    ctx.go('library', Object.fromEntries(['q', ...filterFields.map(field => field.key)].map(key => [key, String(form.get(key) || '').trim() || null])));
  }
  return <div className={styles.stack}>
    <CatalogNotice ctx={ctx} />
    <Panel title="Find an instruction" eyebrow="Source catalog" icon={<Funnel weight="regular" aria-hidden="true" />}>
      <form id="library-filters" className={styles.filterForm} onSubmit={applyFilters} key={ctx.params.toString()}>
        <Field id="q" label="Search name, description or path"><input id="q" name="q" type="search" defaultValue={q} placeholder="For example: postgres auth" /></Field>
        <div className={styles.filterGrid}>{filterFields.map(({key, label, field}) => <Field key={key} id={key} label={label}>
          <select id={key} name={key} defaultValue={ctx.params.get(key) || ''}><option value="">All</option>{[...new Set(fixture.skills.map(skill => skill[field]))].sort().map(value => <option key={value} value={value}>{value}</option>)}</select>
        </Field>)}</div>
        <div className={styles.actions}><ActionButton type="submit" tone="human">Apply filters</ActionButton><ActionButton href={ctx.href('library', clearFilters)}>Clear filters</ActionButton></div>
      </form>
    </Panel>
    <Panel title="Skill revisions" icon={<FileText weight="regular" aria-hidden="true" />} action={<StateBadge>{matches.length} skills</StateBadge>}>
      <div className={styles.resultsSummary}><p role="status"><strong>{matches.length} skills</strong> match the current filters{ctx.state === 'partial' ? ` within ${skills.length} delivered sources` : ''}.</p><p className={styles.muted}>Source status does not establish publication. Knowledge layer: Unclassified.</p></div>
      {matches.length ? <DataTable caption="Fixture skill revisions matching your filters" headings={['Skill / exact source', 'Scope', 'Owner from source', 'Source layer', 'Source status']}>
        {matches.map(skill => <tr key={skill.id}>
          <td><div className={styles.skillCell}><Link className={styles.skillName} to={ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: 'content', from: 'library', return_tab: null})}>{skill.name}</Link><details className={styles.sourceDetails}><summary>Source details</summary><p>{skill.description}</p><SourceLink path={skill.path} /></details></div></td>
          <td><span className={styles.identifier}>{skill.scope}</span>{!fixture.nodes.some(node => node.id === skill.scope) && <span className={styles.muted}>Unmapped scope</span>}</td>
          <td>{skill.owner}</td><td>{skill.sourceLayer}</td><td><StateBadge>{skill.sourceStatus}</StateBadge></td>
        </tr>)}
      </DataTable> : <div className={styles.emptyResult}><h3>No matching skills</h3><p>Adjust the search or filters. The fixture remains available.</p><ActionButton href={ctx.href('library', clearFilters)}>Clear filters</ActionButton></div>}
    </Panel>
  </div>;
}

function repositoryNodes(skills: Skill[], ctx: RouteContext, axis: MapAxis): TreeNode[] {
  type Branch = {folders: Map<string, Branch>; skills: Skill[]};
  const root: Branch = {folders: new Map(), skills: []};
  for (const skill of skills) {
    let branch = root;
    for (const folder of skill.path.split('/').slice(0, -1)) {
      if (!branch.folders.has(folder)) branch.folders.set(folder, {folders: new Map(), skills: []});
      branch = branch.folders.get(folder)!;
    }
    branch.skills.push(skill);
  }
  const toNodes = (branch: Branch, path: string): TreeNode[] => [
    ...branch.skills.map(skill => ({id: skill.id, label: skill.name, detail: `${skill.scope} · ${skill.sourceLayer}`, href: ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: 'source', from: 'map', return_tab: axis})})),
    ...[...branch.folders].map(([folder, child]) => ({id: `${path}/${folder}`, label: `${folder}/`, children: toNodes(child, `${path}/${folder}`)})),
  ];
  return toNodes(root, fixture.sources);
}

function SkillList({skills, ctx, axis}: RouteProps & {skills: Skill[]; axis: MapAxis}) {
  return <ul className={styles.skillList}>{skills.map(skill => <li key={skill.id}>
    <FileText weight="regular" aria-hidden="true" /><div><Link to={ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: 'source', from: 'map', return_tab: axis})}>{skill.name}</Link><span className={styles.muted}>{skill.scope} · Source layer: {skill.sourceLayer}</span></div>
  </li>)}</ul>;
}

export function MapRoute({ctx}: RouteProps) {
  const axis = mapAxis(ctx);
  const skills = visibleSkills(ctx.state);
  const selected = findSkill(ctx.params.get('skill')) || proposalSkill;
  const selectionAvailable = skills.some(skill => skill.id === selected.id);
  const unmapped = [...new Set(skills.filter(skill => !fixture.nodes.some(node => node.id === skill.scope)).map(skill => skill.scope))];
  const scopeNodes = [...fixture.nodes.map(node => ({...node, unmapped: false})), ...unmapped.map(id => ({id, paths: [] as string[], owner: '', unmapped: true}))].filter(node => ctx.state !== 'partial' || skills.some(skill => skill.scope === node.id));
  function selectSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    ctx.go('map', {skill: String(new FormData(event.currentTarget).get('skill')), tab: axis});
  }
  const links = skills.flatMap(skill => (['requires', 'refines'] as const).flatMap(type => skill[type].map(id => ({skill, type, id}))));
  return <div className={styles.stack}>
    <CatalogNotice ctx={ctx} />
    <p className={styles.intro}>Explore repository paths, declared scopes and source relationships. Each axis describes a different part of the same fixture.</p>
    <Tabs label="Map axes" current={axis} items={axes.map(id => ({id, label: id === 'repository' ? 'Repository' : id === 'scopes' ? 'Scopes' : 'Pyramid', href: ctx.href('map', {tab: id})}))} />
    <div className={styles.mapGrid}>
      <div className={styles.stack}>
        {axis === 'repository' && <Panel title="Repository tree" eyebrow={fixture.sources} icon={<FolderSimple weight="regular" aria-hidden="true" />} action={<StateBadge>{skills.length} skills</StateBadge>}>
          <p className={styles.panelIntro}>Actual source paths. Expand a directory to inspect its imported instructions.</p>
          <ScopeTree label="Repository source paths" nodes={repositoryNodes(skills, ctx, axis)} selected={selected.id} />
        </Panel>}
        {axis === 'scopes' && <Panel title="Declared scopes" eyebrow="Scope mapping" icon={<TreeStructure weight="regular" aria-hidden="true" />}>
          <p className={styles.panelIntro}>Paths and scope owners are declared in the fixture. Directory depth does not define a knowledge layer.</p>
          <div className={styles.scopeGroups}>{scopeNodes.map(node => {
            const assigned = skills.filter(skill => skill.scope === node.id);
            return <details key={node.id} className={styles.scopeGroup} open><summary><span>{node.id}</span>{node.unmapped && <StateBadge tone="warning">Unmapped scope</StateBadge>}<span className={styles.count}>{assigned.length} skills</span></summary>
              <div className={styles.scopeBody}><dl className={styles.scopeMeta}><div><dt>Paths</dt><dd>{node.paths.length ? node.paths.map(path => <code key={path}>{path}</code>) : 'Unknown — no mapping declared in the fixture.'}</dd></div><div><dt>Scope owner</dt><dd>{node.owner || 'Unknown — no scope node.'}</dd></div></dl>
              {assigned.length ? <SkillList skills={assigned} ctx={ctx} axis={axis} /> : <p className={styles.muted}>No skill assigned directly to this scope.</p>}</div>
            </details>;
          })}</div>
        </Panel>}
        {axis === 'pyramid' && <>
          <Panel title="Knowledge layer" eyebrow="Pyramid axis" icon={<Stack weight="regular" aria-hidden="true" />} action={<StateBadge tone="warning">Unclassified</StateBadge>}>
            <div className={styles.panelIntro}><p>The fixture declares source layers: org, platform and team. No atomic, task or abstract classification is provided.</p><p className={styles.muted}>The list and relationships below preserve the source declarations.</p></div>
            <SkillList skills={skills} ctx={ctx} axis={axis} />
          </Panel>
          <Panel title="Declared relationships" icon={<GitBranch weight="regular" aria-hidden="true" />}>
            <DataTable caption="Text alternative: explicit knowledge relationships" headings={['Source skill', 'Relationship', 'Target skill']}>
              {links.map(({skill, type, id}) => <tr key={`${skill.id}:${type}:${id}`}><td><Link to={ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: 'dependencies', from: 'map', return_tab: axis})}>{skill.name}</Link></td><td><code>{type}</code></td><td>{findSkill(id) ? <Link to={ctx.href('skill', {skill: id, revision: findSkill(id)!.revision, tab: 'source', from: 'map', return_tab: axis})}>{findSkill(id)!.name}</Link> : <code>{id}</code>}{findSkill(id) && !skills.some(item => item.id === id) && <span className={styles.muted}>Source omitted from this snapshot.</span>}</td></tr>)}
              {!links.length && <tr><td colSpan={3}>No relationships declared in the available sources.</td></tr>}
            </DataTable>
          </Panel>
        </>}
      </div>
      <aside className={styles.stack} aria-label="Selected map object">
        <Panel title="Selected skill" eyebrow="Inspect source" icon={<FileText weight="regular" aria-hidden="true" />}>
          <div className={styles.panelBody}>
            <form className={styles.stack} id="map-select" onSubmit={selectSkill} key={`${selected.id}:${axis}`}>
              <Field id="map-skill" label="Inspect relationships"><select id="map-skill" name="skill" defaultValue={selectionAvailable ? selected.id : skills[0]?.id}>{skills.map(skill => <option key={skill.id} value={skill.id}>{skill.name} · {skill.scope}</option>)}</select></Field>
              <ActionButton type="submit">Select skill</ActionButton>
            </form>
            {selectionAvailable ? <><h3 className={styles.selectedName}>{selected.name}</h3><dl className={styles.scopeMeta}><div><dt>Scope</dt><dd>{selected.scope}</dd></div><div><dt>Source layer</dt><dd>{selected.sourceLayer}</dd></div><div><dt>Knowledge layer</dt><dd>Unclassified</dd></div></dl>
              <ActionButton tone="human" href={ctx.href('skill', {skill: selected.id, revision: selected.revision, tab: 'source', from: 'map', return_tab: axis})}>Open source and scope</ActionButton>
            </> : <div className={styles.notice}><p>The selected source is omitted from this snapshot. Select an available skill to inspect its relationships.</p></div>}
          </div>
        </Panel>
        {selectionAvailable && <Panel title="Declared relationships" icon={<GitBranch weight="regular" aria-hidden="true" />}><div className={styles.panelBody}><Relations skill={selected} ctx={ctx} axis={axis} /></div></Panel>}
      </aside>
    </div>
  </div>;
}

function FeedbackForm({ctx, skill}: RouteProps & {skill: Skill}) {
  const [note, setNote] = useState(ctx.memory.feedback?.[skill.id] || '');
  const [message, setMessage] = useState('');
  function saveNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ctx.canFeedback || !note.trim()) return;
    ctx.save({feedback: {...ctx.memory.feedback, [skill.id]: note.trim()}});
    setMessage('Local note saved for this revision. No telemetry was sent.');
  }
  return <Panel title="Feedback" eyebrow="Local note" icon={<ChatText weight="regular" aria-hidden="true" />}>
    <div className={styles.panelBody}><p>No usage observations exist in this fixture. This note is stored only in this browser session.</p>
      {!ctx.canFeedback && <p className={styles.notice}>Feedback is unavailable in this snapshot. Saved notes remain readable.</p>}
      <form id="skill-feedback" className={styles.stack} onSubmit={saveNote}>
        <Field id="feedback-note" label="Review note and reason" hint="Stored with this skill revision in the local simulation."><textarea id="feedback-note" name="note" rows={6} required value={note} onChange={event => {setNote(event.target.value); setMessage('');}} disabled={!ctx.canFeedback} /></Field>
        <div className={styles.actions}><ActionButton type="submit" tone="human" disabled={!ctx.canFeedback}>Save local note</ActionButton></div>
        <p className={styles.feedbackStatus} role="status">{message}</p>
      </form>
    </div>
  </Panel>;
}

export function SkillRoute({ctx}: RouteProps) {
  const requested = ctx.params.get('skill');
  const skill = requested ? findSkill(requested) : proposalSkill;
  const from = originView(ctx);
  const backLink = <Link className={styles.backLink} to={ctx.href(from, {tab: ctx.params.get('return_tab') || null, from: null, return_tab: null})}><ArrowLeft weight="regular" aria-hidden="true" />Back to {originNames[from]}</Link>;
  if (!skill) return <div className={styles.stack}>{backLink}<Panel title="Skill not found"><div className={styles.panelBody}><p>The requested identifier is absent from this fixture.</p><ActionButton href={ctx.href('library', {skill: null, tab: null, from: null})}>Return to Library</ActionButton></div></Panel></div>;
  if (!visibleSkills(ctx.state).some(item => item.id === skill.id)) return <div className={styles.stack}>{backLink}<CatalogNotice ctx={ctx} /><Panel title="Source omitted from QA subset"><div className={styles.panelBody}><p>This source file was deliberately omitted from the current {visibleSkills(ctx.state).length}/{fixture.skills.length} local snapshot. Its body is unavailable in this scenario.</p><ActionButton href={ctx.href('library', {tab: null, from: null})}>Return to partial Library</ActionButton></div></Panel></div>;
  const requestedRevision = ctx.params.get('revision');
  if (requestedRevision && requestedRevision !== skill.revision) return <div className={styles.stack}>
    {backLink}<CatalogNotice ctx={ctx} />
    <Panel title="Selected revision unavailable" eyebrow="Source revision mismatch" icon={<FileText weight="regular" aria-hidden="true" />}>
      <div className={styles.panelBody}>
        <p>The selected revision is not part of the imported source snapshot. Its body and feedback are unavailable here. A local candidate does not replace the immutable imported revision.</p>
        <ProvenanceTrail entries={[
          {label: 'Skill', value: skill.name},
          {label: 'Scope', value: skill.scope, code: true},
          {label: 'Selected SHA-256', value: requestedRevision, code: true},
          {label: 'Available imported SHA-256', value: skill.revision, code: true},
        ]} />
        <ActionButton href={ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: 'content'})}>Open available imported revision</ActionButton>
      </div>
    </Panel>
  </div>;
  const tab = ['content', 'source', 'dependencies', 'feedback'].includes(ctx.params.get('tab') || '') ? ctx.params.get('tab')! : 'content';
  const node = fixture.nodes.find(item => item.id === skill.scope);
  return <div className={styles.stack}>
    {backLink}<CatalogNotice ctx={ctx} />
    <Panel title={skill.name} eyebrow="Immutable source revision" icon={<FileText weight="regular" aria-hidden="true" />} action={<ActionButton tone="human" href={sourceURL(skill.path)}>Open exact source revision <ArrowSquareOut weight="regular" aria-hidden="true" /></ActionButton>}>
      <div className={styles.panelBody}><p className={styles.description}>{skill.description}</p>
        <dl className={styles.identityGrid}><div><dt>Scope</dt><dd>{skill.scope}{!node && <StateBadge tone="warning">Unmapped scope</StateBadge>}</dd></div><div><dt>Owner from source</dt><dd>{skill.owner}</dd></div><div><dt>Source status</dt><dd><StateBadge>{skill.sourceStatus}</StateBadge></dd></div><div><dt>Source layer</dt><dd>{skill.sourceLayer}</dd></div><div><dt>Knowledge layer</dt><dd>Unclassified</dd></div><div><dt>Publication at import</dt><dd>Not established</dd></div></dl>
        <dl className={styles.revisionStrip}><div><dt>Source path</dt><dd><code>{skill.path}</code></dd></div><div><dt>Content SHA-256</dt><dd><code>{skill.revision}</code></dd></div></dl>
        <Urn value={skill.id} />
      </div>
    </Panel>
    <Tabs label="Skill sections" current={tab} items={[{id: 'content', label: 'Content'}, {id: 'source', label: 'Source & scope'}, {id: 'dependencies', label: 'Dependencies'}, {id: 'feedback', label: 'Feedback'}].map(item => ({...item, href: ctx.href('skill', {skill: skill.id, revision: skill.revision, tab: item.id})}))} />
    {tab === 'content' && <Panel title="Original body" eyebrow="Source content" icon={<FileText weight="regular" aria-hidden="true" />}><div className={styles.panelIntro}><p>Complete Markdown body from the source revision. Commands are inert.</p></div><SkillContent content={skill.body} /></Panel>}
    {tab === 'source' && <div className={styles.stack}>
      <Panel title="Source and scope" eyebrow="Provenance" icon={<GitBranch weight="regular" aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          {label: 'Repository', value: fixture.repo},
          {label: 'Scope', value: skill.scope, detail: node ? node.paths.join(', ') : 'Unmapped scope — no path mapping declared in the fixture.'},
          {label: 'Owner from source', value: skill.owner, detail: 'Ownership metadata; not an access grant.'},
          {label: 'Source path', value: skill.path, href: sourceURL(skill.path), code: true},
          {label: 'Base commit', value: fixture.commit, code: true},
          {label: 'Content SHA-256', value: skill.revision, detail: 'Digest of the exact SKILL.md bytes, including frontmatter.', code: true},
          {label: 'Source bytes', value: `${skill.bytes.toLocaleString('en-US')} bytes`},
        ]} />
        <div className={styles.panelBody}><p className={styles.muted}>No verified line mapping is available. Source links open the file at the exact base commit.</p><SourceLink path={skill.path} label="Open exact source revision" /></div>
      </Panel>
      <Panel title="Declared references" icon={<LinkSimple weight="regular" aria-hidden="true" />}><div className={styles.panelBody}>{skill.references.length ? <ul className={styles.referenceList}>{skill.references.map(reference => <li key={reference}><SourceLink path={reference} />{reference.includes('#') && <p className={styles.muted}>Source fragment: <code>{reference.split('#').slice(1).join('#')}</code>. No verified line mapping.</p>}</li>)}</ul> : <p className={styles.muted}>No references declared in the fixture.</p>}
        <details className={styles.rawSource}><summary>Inspect complete SKILL.md including frontmatter</summary><pre tabIndex={0} aria-label="Complete imported SKILL.md">{skill.raw}</pre></details>
      </div></Panel>
    </div>}
    {tab === 'dependencies' && <Panel title="Declared relationships" eyebrow="Source declarations" icon={<GitBranch weight="regular" aria-hidden="true" />}><div className={styles.panelBody}><p>These links express source declarations. They do not prove delivery to an agent.</p><Relations ctx={ctx} skill={skill} /></div></Panel>}
    {tab === 'feedback' && <FeedbackForm key={skill.id} skill={skill} ctx={ctx} />}
  </div>;
}


