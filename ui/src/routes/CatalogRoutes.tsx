import {useEffect, useState, type FormEvent, type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {ContextMenu} from '@base-ui/react/context-menu';
import {toast} from 'sonner';
import {ArrowLeft, ArrowSquareOut, ChatText, CopySimple, DownloadSimple, FileText, FolderSimple, Funnel, GitBranch, LinkSimple, Prohibit, Scales, Stack, Star, ThumbsDown, ThumbsUp, TreeStructure} from '@phosphor-icons/react';
import {ActionButton, DataTable, Field, Panel, ProvenanceTrail, PyramidChart, RouteState, ScopeTree, SkillContent, StateBadge, Tabs, Urn} from '../Shared';
import {
  ApiFailure, DegradedNotice, PartialNotice, RepositoryRequired, asApiError, cleared, downloadText,
  readOnly, stableKey, unknown, useAsync, type ApiProps,
} from './apiState';
import type {FeedbackEntry, MapChild, SkillSummary} from '../api/decoders';
import type {SkillQuery} from '../data/source';
import type {View} from '../domain';
import {pyramidGraphBands, pyramidGraphEdges, hasAnyClassification, type PyramidLayer} from '../domain/pyramidGraph';
import styles from './CatalogRoutes.module.css';

const pyramidLayerLabels: Record<PyramidLayer, string> = {
  abstract: 'Abstract', task: 'Task', atomic: 'Atomic', unclassified: 'Unclassified',
};
const pyramidLayerDescriptions: Record<PyramidLayer, string> = {
  abstract: 'Concepts and domain knowledge', task: 'Reusable capabilities and workflows',
  atomic: 'Concrete, executable elements', unclassified: 'No declared layer yet',
};

type MapAxis = 'repository' | 'scopes' | 'pyramid';
const axes: MapAxis[] = ['repository', 'scopes', 'pyramid'];
const originView = (ctx: {params: URLSearchParams}): View => ['map', 'library', 'proposals', 'usage'].includes(ctx.params.get('from') || '') ? ctx.params.get('from') as View : 'library';
const originNames: Partial<Record<View, string>> = {map: 'Map', library: 'Library', proposals: 'Proposals', usage: 'Usage & quality'};

function favoritesKey(ctx: ApiProps['ctx']) {
  return ['guidefold-favorites-v1', ctx.me?.user.id ?? 'unknown', ctx.org ?? 'unknown', ctx.repo ?? 'unknown'].join(':');
}
function readFavorites(key: string) {
  try {
    const value = JSON.parse(window.localStorage.getItem(key) ?? '[]');
    return new Set<string>(Array.isArray(value) ? value.filter(item => typeof item === 'string') : []);
  } catch { return new Set<string>(); }
}
function useFavorites(ctx: ApiProps['ctx']) {
  const key = favoritesKey(ctx);
  const [favorites, setFavorites] = useState<Set<string>>(() => readFavorites(key));
  useEffect(() => setFavorites(readFavorites(key)), [key]);
  const toggle = (skillId: string, name: string) => {
    const next = readFavorites(key), adding = !next.has(skillId);
    adding ? next.add(skillId) : next.delete(skillId);
    try {
      window.localStorage.setItem(key, JSON.stringify([...next]));
      toast.success(adding ? 'Added to favorites' : 'Removed from favorites', {description: name});
      setFavorites(next);
    } catch {
      toast.error('Favorite was not saved', {description: 'Browser storage is unavailable.'});
    }
  };
  return {favorites, toggle};
}

function FavoriteToggle({active,name,onToggle}:{active:boolean;name:string;onToggle:()=>void}) {
  return <button type="button" className={styles.favoriteButton} data-slot="badge" aria-pressed={active} aria-label={(active ? 'Remove ' : 'Add ') + name + (active ? ' from favorites' : ' to favorites')} onClick={onToggle}>
    <Star weight={active ? 'fill' : 'regular'} aria-hidden="true"/><span>{active ? 'Favorite' : 'Add favorite'}</span>
  </button>;
}

function SkillContextActions({item,href,favorite,onToggle,children}:{item:SkillSummary;href:string;favorite:boolean;onToggle:()=>void;children:ReactNode}) {
  const copyUrn = async () => {
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(item.skill_id);
      toast.success('Skill URN copied');
    } catch { toast.error('Could not copy the skill URN'); }
  };
  return <ContextMenu.Root>
    <ContextMenu.Trigger className={styles.contextTarget}>{children}</ContextMenu.Trigger>
    <ContextMenu.Portal><ContextMenu.Positioner className={styles.contextPositioner}><ContextMenu.Popup className={styles.contextMenu}>
      <ContextMenu.Item className={styles.contextItem} render={<Link to={href}/>}><ArrowSquareOut aria-hidden="true"/>Open skill</ContextMenu.Item>
      <ContextMenu.Item className={styles.contextItem} onClick={onToggle}><Star weight={favorite ? 'fill' : 'regular'} aria-hidden="true"/>{favorite ? 'Remove from favorites' : 'Add to favorites'}</ContextMenu.Item>
      <ContextMenu.Separator className={styles.contextSeparator}/>
      <ContextMenu.Item className={styles.contextItem} onClick={()=>{void copyUrn();}}><CopySimple aria-hidden="true"/>Copy skill URN</ContextMenu.Item>
    </ContextMenu.Popup></ContextMenu.Positioner></ContextMenu.Portal>
  </ContextMenu.Root>;
}

// ---------------------------------------------------------------------------
// Hosted API routes (F13, F14, F15).
// ---------------------------------------------------------------------------

const catalogFilters = [
  {key: 'scope', field: 'scope' as const, label: 'Scope'},
  {key: 'owner', field: 'owner' as const, label: 'Owner from source'},
  {key: 'layer', field: 'layer' as const, label: 'Source layer'},
  {key: 'status', field: 'status' as const, label: 'Source status'},
];
const libraryKeys = ['q', 'scope', 'owner', 'layer', 'status'];
/** 07 §Budżety: the map starts at 100 objects per request and never renders past 200. */
const MAP_RENDER_LIMIT = 200;
const MAP_MAX_DEPTH = 8;

export function ApiLibraryRoute({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const ready = Boolean(org && repo);
  const at = (key: string) => ctx.params.get(key) ?? '';
  const cursor = ctx.params.get('cursor');
  const query: SkillQuery = {
    q: at('q') || undefined, scope: at('scope') || undefined, owner: at('owner') || undefined,
    layer: at('layer') || undefined, status: at('status') || undefined, cursor: cursor ?? undefined,
  };
  const signature = [...libraryKeys.map(at), cursor ?? ''].join('|');
  const page = useAsync(() => source.listSkills(target, query), 'skills:' + org + '/' + repo + ':' + signature, ready);
  const facets = useAsync(
    () => Promise.all(catalogFilters.map(entry => source.getFacets(target, {field: entry.field}))),
    'facets:' + org + '/' + repo, ready,
  );
  const chosen = catalogFilters.filter(entry => at(entry.key));
  // The active value keeps its own lookup so it stays visible outside the current facet page.
  const lookups = useAsync(
    () => Promise.all(chosen.map(entry => source.lookupFacet(target, entry.field, at(entry.key)))),
    'lookup:' + org + '/' + repo + ':' + chosen.map(entry => entry.key + '=' + at(entry.key)).join('&'),
    ready && chosen.length > 0,
  );
  const [trail, setTrail] = useState<string[]>([]);
  const {favorites, toggle: toggleFavorite} = useFavorites(ctx);
  const result = page.value;
  const failedRefresh = page.phase === 'error' && Boolean(result);
  const degraded = readOnly(ctx, failedRefresh);
  const lookupOf = (entry: typeof catalogFilters[number]) => lookups.value?.find(item => item.field === entry.field && item.value === at(entry.key));
  const unavailable = (entry: typeof catalogFilters[number]) => {
    const active = at(entry.key);
    if (!active) return false;
    const echo = result?.filters?.[entry.key];
    if (echo && echo.value === active) return echo.available === false;
    const lookup = lookupOf(entry);
    return lookup ? !lookup.available : false;
  };
  const blocked = catalogFilters.filter(unavailable);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setTrail([]);
    // A cursor belongs to one query; changing a filter must start the listing again.
    ctx.go('library', {...Object.fromEntries(libraryKeys.map(key => [key, String(form.get(key) ?? '').trim() || null])), cursor: null});
  }
  function openNext(next: string) {
    setTrail(current => [...current, cursor ?? '']);
    ctx.go('library', {cursor: next});
  }
  function openPrevious() {
    const previous = trail[trail.length - 1] ?? '';
    setTrail(current => current.slice(0, -1));
    ctx.go('library', {cursor: previous || null});
  }

  if (!ready) return <RepositoryRequired ctx={ctx} />;
  if (!result && page.phase === 'error' && page.error) return <ApiFailure error={page.error} onRetry={page.reload} retryLabel="Retry this page" />;
  if (!result) return <RouteState state="loading" title="Reading the catalog" description="Waiting for the first page of skill summaries. No body is requested here." />;

  // The active value keeps one stable <option> node whether or not the facet page lists it: the
  // select is uncontrolled, and swapping that node once facets arrive would drop the selection.
  const options = (entry: typeof catalogFilters[number], index: number) => {
    const values = facets.value?.[index]?.values ?? [];
    const active = at(entry.key);
    const listed = values.find(item => item.value === active);
    return <>
      <option value="">All</option>
      {active && <option key="active" value={active}>{unavailable(entry) ? 'Not available in this snapshot: ' + active : listed ? active + ' (' + listed.count + ')' : active}</option>}
      {values.filter(item => item.value !== active).map(item => <option key={item.value} value={item.value}>{item.value} ({item.count})</option>)}
    </>;
  };

  return <div className={styles.stack}>
    {degraded && <DegradedNotice>{failedRefresh
      ? 'Showing the last page this session read. The catalog could not be refreshed, so counts and filters may have moved on.'
      : 'Membership could not be reconfirmed, so this page stays read only.'}</DegradedNotice>}
    {blocked.length > 0 && <PartialNotice>{'This snapshot has no value ' + blocked.map(entry => at(entry.key)).join(', ') + ' for ' + blocked.map(entry => entry.label.toLowerCase()).join(', ') + '. The request is kept in the address; nothing was silently widened to All.'}</PartialNotice>}
    <Panel title="Find an instruction" eyebrow="Skill catalog" icon={<Funnel weight="regular" aria-hidden="true" />}>
      <form id="library-filters" className={styles.filterForm} onSubmit={applyFilters} key={ctx.params.toString()}>
        <Field id="q" label="Search name, description or path"><input id="q" name="q" type="search" defaultValue={at('q')} /></Field>
        <div className={styles.filterGrid}>{catalogFilters.map((entry, index) => <Field key={entry.key} id={entry.key} label={entry.label}
          hint={facets.phase === 'loading' ? 'Reading available values' : undefined}
          error={unavailable(entry) ? 'This value is not available in this snapshot. Choose another value or clear this filter.' : undefined}>
          <select id={entry.key} name={entry.key} defaultValue={at(entry.key)}>{options(entry, index)}</select>
        </Field>)}</div>
        <div className={styles.actions}>
          <ActionButton type="submit" tone="human">Apply filters</ActionButton>
          <ActionButton href={ctx.href('library', {...cleared(libraryKeys), cursor: null})}>Clear filters</ActionButton>
        </div>
      </form>
      {facets.phase === 'error' && facets.error && <p className={styles.muted} role="status">Filter values could not be read ({facets.error.code}). The address filters still apply to the result below.</p>}
    </Panel>
    <Panel title="Skill revisions" icon={<FileText weight="regular" aria-hidden="true" />}
      action={<StateBadge tone={blocked.length ? 'warning' : 'neutral'}>{blocked.length ? 'Filter value unavailable' : result.items.length + ' on this page'}</StateBadge>}>
      <div className={styles.resultsSummary}>
        <p role="status">{result.items.length} skill summaries on this page{result.next_cursor ? ', more pages follow' : ', last page'}. Bodies are read on the Skill view.</p>
        <p className={styles.muted}>Snapshot {result.snapshot_id ?? 'Unknown'}. Source status does not establish publication.</p>
      </div>
      {result.items.length ? <>
        <DataTable caption="Skill summaries matching the current filters" headings={['Skill / source path', 'Scope', 'Owner from source', 'Source layer', 'Publication']}>
          {result.items.map(item => {const skillHref=ctx.href('skill', {skill: item.skill_id, revision: item.revision_id, tab: 'content', from: 'library', return_tab: null});const favorite=favorites.has(item.skill_id);return <tr key={item.skill_id}>
            <td><SkillContextActions item={item} href={skillHref} favorite={favorite} onToggle={()=>toggleFavorite(item.skill_id,item.name)}><div className={styles.skillCell}>
              <Link className={styles.skillName} to={skillHref}>{item.name}</Link>
              <FavoriteToggle active={favorite} name={item.name} onToggle={()=>toggleFavorite(item.skill_id,item.name)}/>
              <details className={styles.sourceDetails}><summary>Source details</summary><p>{item.description}</p><code>{item.path}</code></details>
            </div></SkillContextActions></td>
            <td><span className={styles.identifier}>{item.scope}</span></td>
            <td>{unknown(item.owner)}</td>
            <td>{unknown(item.source_layer)}<span className={styles.muted}>Knowledge layer: {item.knowledge_layer ?? 'Unknown'}</span></td>
            <td><StateBadge tone={item.publication_status === 'published' ? 'system' : item.publication_status === 'needs_review' ? 'warning' : 'neutral'}>{item.publication_status}</StateBadge></td>
          </tr>;})}
        </DataTable>
        <div className={styles.pager}>
          <ActionButton onClick={openPrevious} disabled={trail.length === 0}>Previous page</ActionButton>
          <ActionButton onClick={() => openNext(result.next_cursor as string)} disabled={!result.next_cursor}>Next page</ActionButton>
          <p>{cursor ? 'Reading a page after the first. The cursor stays in the address.' : 'First page.'}</p>
        </div>
      </> : <div className={styles.emptyResult}>
        <h3>{blocked.length ? 'Filter value unavailable' : chosen.length || at('q') ? 'No matching skills' : 'No skills yet'}</h3>
        <p>{blocked.length
          ? 'The requested value is kept in the address. Choose an available value or clear this filter.'
          : chosen.length || at('q')
            ? 'No summary in this snapshot matches the current search and filters.'
            : 'Nothing has been imported into this repository yet. Run the CLI from your checkout, then read the import result.'}</p>
        <ActionButton href={chosen.length || at('q') ? ctx.href('library', {...cleared(libraryKeys), cursor: null}) : ctx.href('import', {step: 'preview'})} tone="system">
          {chosen.length || at('q') ? 'Clear filters' : 'Open Import'}
        </ActionButton>
      </div>}
    </Panel>
  </div>;
}

function RepositoryBranch({ctx, path, label, depth}: ApiProps & {path: string; label: string; depth: number}) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const [open, setOpen] = useState(depth === 0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [children, setChildren] = useState<MapChild[]>([]);
  const chunk = useAsync(() => source.getMapRepository(target, path, cursor ?? undefined), 'map-repository:' + org + '/' + repo + ':' + path + ':' + (cursor ?? ''), open);
  const value = chunk.value;
  useEffect(() => {
    if (chunk.phase !== 'ready' || !value) return;
    setChildren(previous => cursor ? [...previous, ...value.children] : value.children);
  }, [chunk.phase, value, cursor]);
  const shown = children.slice(0, MAP_RENDER_LIMIT);
  const body = <>
    {chunk.phase === 'loading' && children.length === 0 && <RouteState state="loading" title="Reading this directory" description="Only the requested branch is read." />}
    {chunk.phase === 'error' && chunk.error && <ApiFailure error={chunk.error} onRetry={chunk.reload} retryLabel="Retry this branch" />}
    {shown.length > 0 && <ul className={styles.branchList}>
      {shown.map(child => <li key={child.path}>
        {child.kind === 'dir'
          ? <RepositoryBranch ctx={ctx} path={child.path} label={child.name + '/'} depth={depth + 1} />
          : child.kind === 'skill' && child.skill_id
            ? <><FileText weight="regular" aria-hidden="true" /><Link to={ctx.href('skill', {skill: child.skill_id, revision: null, tab: 'content', from: 'map', return_tab: 'repository'})}>{child.name}</Link><code>{child.path}</code></>
            : <><FileText weight="regular" aria-hidden="true" /><span>{child.name}</span><span className={styles.muted}>Document, not a skill</span></>}
      </li>)}
    </ul>}
    {chunk.phase === 'ready' && children.length === 0 && <p className={styles.muted}>This directory holds no imported object.</p>}
    {children.length > MAP_RENDER_LIMIT && <p className={styles.muted}>{'Showing ' + MAP_RENDER_LIMIT + ' of ' + children.length + ' read objects in this directory. Narrow the path to read the rest.'}</p>}
    {value?.next_cursor && children.length <= MAP_RENDER_LIMIT && <ActionButton onClick={() => setCursor(value.next_cursor)}>Read the next 100 objects</ActionButton>}
  </>;
  if (depth === 0) return <div className={styles.branchRoot}>{body}</div>;
  return <details open={open} onToggle={event => setOpen((event.currentTarget as HTMLDetailsElement).open)}>
    <summary><FolderSimple weight="regular" aria-hidden="true" />{label}{depth >= MAP_MAX_DEPTH ? <span className={styles.muted}>Depth limit</span> : null}</summary>
    {depth >= MAP_MAX_DEPTH ? <p className={styles.muted}>This branch is deeper than the map reads. Open the source repository to inspect it.</p> : body}
  </details>;
}

function RelationList({ctx, skillId}: ApiProps & {skillId: string}) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const [cursor, setCursor] = useState<string | null>(null);
  const relations = useAsync(() => source.getRelations(target, {skillId, cursor: cursor ?? undefined}), 'relations:' + org + '/' + repo + ':' + skillId + ':' + (cursor ?? ''), Boolean(org && repo));
  if (relations.phase === 'loading' && !relations.value) return <RouteState state="loading" title="Reading relations" description="Waiting for the declared neighbourhood of this skill." />;
  if (relations.phase === 'error' && relations.error && !relations.value) return <ApiFailure error={relations.error} onRetry={relations.reload} retryLabel="Retry this skill's relations" />;
  const value = relations.value;
  if (!value || value.items.length === 0) return <p className={styles.muted}>No relation is declared for this skill.</p>;
  return <>
    {value.truncated && <PartialNotice>The API truncated this neighbourhood. The list below is incomplete and does not prove the absence of other relations.</PartialNotice>}
    <DataTable caption="Declared relations of the selected skill" headings={['Relation', 'Target skill', 'Provenance']}>
      {value.items.map(edge => <tr key={edge.type + ':' + edge.to + ':' + (edge.from ?? '')}>
        <th scope="row"><code>{edge.type}</code></th>
        <td className={styles.pathCell}><Link to={ctx.href('skill', {skill: edge.to, revision: edge.revision, tab: 'content', from: 'map', return_tab: 'pyramid'})}>{edge.to}</Link></td>
        <td>{unknown(edge.provenance)}</td>
      </tr>)}
    </DataTable>
    {value.next_cursor && <ActionButton onClick={() => setCursor(value.next_cursor)}>Read more relations</ActionButton>}
  </>;
}

function ModulePanel({ctx, scope}: ApiProps & {scope: string}) {
  const {source, org, repo} = ctx;
  const module = useAsync(() => source.getModule({org: org ?? '', repo: repo ?? ''}, scope), 'module:' + org + '/' + repo + ':' + scope, Boolean(org && repo));
  if (module.phase === 'loading' && !module.value) return <RouteState state="loading" title="Reading the module" description="Waiting for the reading order of this scope." />;
  if (module.phase === 'error' && module.error && !module.value) return <ApiFailure error={module.error} onRetry={module.reload} retryLabel="Retry this module" />;
  const value = module.value;
  if (!value) return null;
  const byId = new Map(value.skills.map(item => [item.skill_id, item]));
  return <Panel title={'Module ' + value.scope} eyebrow="Reading order" icon={<Stack weight="regular" aria-hidden="true" />} action={<StateBadge>{value.skills.length} skills</StateBadge>}>
    <p className={styles.muted}>Owner from source: {unknown(value.owner)}. Reading order comes from the module, not from directory depth.</p>
    {value.reading_order.length ? <ol className={styles.readingOrder}>
      {value.reading_order.map(id => <li key={id}>
        <Link to={ctx.href('skill', {skill: id, revision: byId.get(id)?.revision_id ?? null, tab: 'content', from: 'map', return_tab: 'scopes'})}>{byId.get(id)?.name ?? id}</Link>
        <span className={styles.muted}>{byId.get(id)?.description ?? 'Summary not part of this module page.'}</span>
      </li>)}
    </ol> : <p className={styles.muted}>This module declares no reading order.</p>}
    <h3 className={styles.relationHeading}>Shared with other modules</h3>
    {value.shared.length ? <ul className={styles.relationList}>
      {value.shared.map(item => <li key={item.skill_id}>
        <Link to={ctx.href('skill', {skill: item.skill_id, revision: null, tab: 'content', from: 'map', return_tab: 'scopes'})}>{item.name}</Link>
        <span className={styles.muted}>Used by {item.used_by.length ? item.used_by.join(', ') : 'Unknown'}</span>
      </li>)}
    </ul> : <p className={styles.muted}>No skill in this module is shared with another scope.</p>}
    {value.documents.length > 0 && <details className={styles.disclosure}><summary>Documents in this scope ({value.documents.length})</summary>
      <ul className={styles.relationList}>{value.documents.map(document => <li key={document.path}><code>{document.path}</code><span className={styles.muted}>{unknown(document.kind)}</span></li>)}</ul>
    </details>}
  </Panel>;
}

export function ApiMapRoute({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const ready = Boolean(org && repo);
  const axis = axes.includes(ctx.params.get('tab') as MapAxis) ? ctx.params.get('tab') as MapAxis : 'repository';
  const selectedScope = ctx.params.get('scope');
  const selectedSkill = ctx.params.get('skill');
  const scopes = useAsync(() => source.getMapScopes(target, selectedScope ?? undefined), 'map-scopes:' + org + '/' + repo + ':' + (selectedScope ?? ''), ready && axis === 'scopes');
  const layers = useAsync(() => source.getMapLayers(target), 'map-layers:' + org + '/' + repo, ready && axis === 'pyramid');
  // The pyramid graph is scoped to one repository scope at a time — P08's "family", not a
  // whole-repository dump (`layers` above already gives the honest whole-repository overview as
  // bare counts and stays untouched). `familySkills`/`familyRelations` only fetch once a scope is
  // chosen, via the same `scope` query param the Scopes tab already uses.
  const familySkills = useAsync(() => source.listSkills(target, {scope: selectedScope ?? undefined, limit: 200}), 'map-family-skills:' + org + '/' + repo + ':' + (selectedScope ?? ''), ready && axis === 'pyramid' && Boolean(selectedScope));
  const familyRelations = useAsync(() => source.getRelations(target, {type: 'refines', limit: 1000}), 'map-family-relations:' + org + '/' + repo, ready && axis === 'pyramid' && Boolean(selectedScope));
  const familyBandsAll = pyramidGraphBands(familySkills.value?.items ?? []);
  const familyBands = familyBandsAll.filter(band => band.layer !== 'unclassified');
  const familyUnclassifiedCount = familyBandsAll.find(band => band.layer === 'unclassified')?.items.length ?? 0;
  const familyEdges = pyramidGraphEdges(familySkills.value?.items ?? [], familyRelations.value?.items ?? []);
  const familyChartBands = familyBands.map(band => ({key: band.layer as 'abstract' | 'task' | 'atomic', label: pyramidLayerLabels[band.layer], description: pyramidLayerDescriptions[band.layer], items: band.items}));
  const degraded = readOnly(ctx);
  if (!ready) return <RepositoryRequired ctx={ctx} action="Choose a repository" />;
  return <div className={styles.stack}>
    {degraded && <DegradedNotice>Membership could not be reconfirmed. The map is read only and may be behind the repository.</DegradedNotice>}
    <p className={styles.intro}>Three axes over the same import: where a file lives, which scope owns it and how the declared relations run. Directory depth does not assign a knowledge layer.</p>
    <Tabs label="Map axes" current={axis} items={axes.map(id => ({id, label: id === 'repository' ? 'Repository' : id === 'scopes' ? 'Scopes' : 'Pyramid', href: ctx.href('map', {tab: id, skill: selectedSkill, scope: selectedScope})}))} />
    <div className={styles.mapGrid}>
      <div className={styles.stack}>
        {axis === 'repository' && <Panel title="Repository tree" eyebrow="Source paths" icon={<FolderSimple weight="regular" aria-hidden="true" />}>
          <p className={styles.panelIntro}>Each directory is read when you open it, up to 100 objects per request.</p>
          <RepositoryBranch ctx={ctx} path="" label="/" depth={0} />
        </Panel>}
        {axis === 'scopes' && <Panel title="Declared scopes" eyebrow="Scope mapping" icon={<TreeStructure weight="regular" aria-hidden="true" />}>
          {scopes.phase === 'loading' && !scopes.value && <RouteState state="loading" title="Reading scopes" description="Waiting for the scope map of this repository." />}
          {scopes.phase === 'error' && scopes.error && !scopes.value && <ApiFailure error={scopes.error} onRetry={scopes.reload} retryLabel="Retry the scope map" />}
          {scopes.value && <>
            {scopes.value.scope ? <dl className={styles.scopeMeta}>
              <div><dt>Scope</dt><dd>{scopes.value.scope.id}</dd></div>
              <div><dt>Scope owner</dt><dd>{unknown(scopes.value.scope.owner)}</dd></div>
              <div><dt>Paths</dt><dd>{scopes.value.scope.paths.length ? scopes.value.scope.paths.map(path => <code key={path}>{path}</code>) : 'Unknown. No path mapping declared.'}</dd></div>
              <div><dt>Parent</dt><dd>{scopes.value.scope.parent ?? 'Root'}</dd></div>
            </dl> : <p className={styles.muted}>No scope is selected. The list below is the top of the scope map.</p>}
            {scopes.value.children.length ? <ul className={styles.relationList}>
              {scopes.value.children.map(child => <li key={child.id}>
                <Link to={ctx.href('map', {tab: 'scopes', scope: child.id, skill: null})}>{child.id}</Link>
                <span className={styles.muted}>{child.skills} skills, owner {unknown(child.owner)}</span>
              </li>)}
            </ul> : <p className={styles.muted}>No child scope is declared here.</p>}
            {scopes.value.skills.length > 0 && <ul className={styles.relationList}>
              {scopes.value.skills.map(item => <li key={item.skill_id}>
                <Link to={ctx.href('map', {tab: 'scopes', skill: item.skill_id, scope: selectedScope})}>{item.name}</Link><code>{item.skill_id}</code>
              </li>)}
            </ul>}
            {scopes.value.unmapped.length > 0 && <div className={styles.notice} role="status">
              <StateBadge tone="warning">Unmapped scope</StateBadge>
              <p>{scopes.value.unmapped.length} skills declare a scope with no mapping in this repository: {scopes.value.unmapped.map(item => item.name).join(', ')}. They stay readable and are not assigned to a parent.</p>
            </div>}
          </>}
        </Panel>}
        {axis === 'scopes' && selectedScope && <ModulePanel ctx={ctx} scope={selectedScope} />}
        {axis === 'pyramid' && <Panel title="Knowledge layer" eyebrow="General to specific" icon={<Stack weight="regular" aria-hidden="true" />}>
          {layers.phase === 'loading' && !layers.value && <RouteState state="loading" title="Reading layers" description="Waiting for the knowledge layer counts." />}
          {layers.phase === 'error' && layers.error && !layers.value && <ApiFailure error={layers.error} onRetry={layers.reload} retryLabel="Retry the layer counts" />}
          {layers.value && (layers.value.layers.length ? <DataTable caption="Skills per knowledge layer" headings={['Knowledge layer', 'Skills']}>
            {layers.value.layers.map(entry => <tr key={entry.layer}><th scope="row">{entry.layer}</th><td>{entry.count}</td></tr>)}
          </DataTable> : <RouteState state="empty" title="No classified layer" description="No skill in this repository carries a knowledge layer. Unclassified is a named absence, not a level." />)}
          <p className={styles.muted}>A layer is declared, never inferred from the folder a file sits in.</p>
        </Panel>}
        {axis === 'pyramid' && <Panel title="Family" eyebrow={selectedScope ? 'Scope ' + selectedScope : 'Choose a scope'} icon={<Stack weight="regular" aria-hidden="true" />}>
          {!selectedScope
            ? <p className={styles.muted}>No scope is selected. <Link to={ctx.href('map', {tab: 'scopes', skill: selectedSkill, scope: null})}>Open the Scopes tab</Link> and choose one to see its pyramid, abstract to atomic.</p>
            : <>
              {((familySkills.phase === 'loading' && !familySkills.value) || (familyRelations.phase === 'loading' && !familyRelations.value)) && <RouteState state="loading" title="Reading the family" description="Waiting for the skills and declared relations of this scope." />}
              {familySkills.phase === 'error' && familySkills.error && !familySkills.value && <ApiFailure error={familySkills.error} onRetry={familySkills.reload} retryLabel="Retry the scope's skills" />}
              {familyRelations.phase === 'error' && familyRelations.error && !familyRelations.value && <ApiFailure error={familyRelations.error} onRetry={familyRelations.reload} retryLabel="Retry the declared relations" />}
              {familySkills.value && familyRelations.value && <>
                {familySkills.value.next_cursor && <PartialNotice>This scope has more than 200 skills. The pyramid below only reflects the first page.</PartialNotice>}
                {familyRelations.value.truncated && <PartialNotice>The API truncated the relation list. Some connector lines above may be missing.</PartialNotice>}
                {hasAnyClassification(familyBandsAll)
                  ? <>
                    <PyramidChart bands={familyChartBands} edges={familyEdges} selectedId={selectedSkill} onSelect={id => ctx.go('map', {tab: 'pyramid', scope: selectedScope, skill: id})} />
                    {familyUnclassifiedCount > 0 && <p className={styles.muted}>{familyUnclassifiedCount} more skill{familyUnclassifiedCount === 1 ? '' : 's'} in this scope carry no knowledge layer yet and are not pictured above.</p>}
                    <DataTable caption={'Text alternative: refines relationships within ' + selectedScope} headings={['From', 'To']}>
                      {familyEdges.map(edge => <tr key={edge.from + '>' + edge.to}><td><code>{edge.from}</code></td><td><code>{edge.to}</code></td></tr>)}
                    </DataTable>
                  </>
                  : <RouteState state="empty" title="No classified skill in this scope" description="No skill in this scope carries a knowledge layer. Unclassified is a named absence, not a level." />}
              </>}
            </>}
        </Panel>}
      </div>
      <aside className={styles.stack} aria-label="Selected map object">
        <Panel title="Selected skill" eyebrow="Declared relations" icon={<GitBranch weight="regular" aria-hidden="true" />}>
          {selectedSkill
            ? <div className={styles.panelBody}>
              <code>{selectedSkill}</code>
              <RelationList ctx={ctx} skillId={selectedSkill} />
              <ActionButton tone="human" href={ctx.href('skill', {skill: selectedSkill, revision: null, tab: 'content', from: 'map', return_tab: axis})}>Open this skill</ActionButton>
            </div>
            : <p className={styles.muted}>Choose a skill in the tree, a scope or a relation to read its neighbourhood.</p>}
        </Panel>
      </aside>
    </div>
  </div>;
}

const skillTabs = ['content', 'revisions', 'source', 'dependencies', 'feedback'];
const verdicts = [
  {value: 'helped', label: 'Helped', detail: 'The instruction changed what I did, for the better.', icon: ThumbsUp},
  {value: 'mixed', label: 'Mixed', detail: 'Partly useful, partly wrong for this task.', icon: Scales},
  {value: 'hindered', label: 'Hindered', detail: 'The instruction cost time or led the task astray.', icon: ThumbsDown},
  {value: 'not_applicable', label: 'Not applicable', detail: 'The instruction did not apply to this task.', icon: Prohibit},
];

function FeedbackPanel({ctx, skillId, revisionId, existing}: ApiProps & {skillId: string; revisionId: string; existing: FeedbackEntry[]}) {
  const {source, org, repo} = ctx;
  const [verdict, setVerdict] = useState('helped');
  const [reason, setReason] = useState('');
  const [taskId, setTaskId] = useState('');
  const [judgment, setJudgment] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const blocked = readOnly(ctx);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || blocked || !org || !repo) return;
    const text = reason.trim();
    if (!text) {setError('Describe what happened. A verdict without a reason cannot be reviewed.'); return;}
    setBusy(true);
    setError('');
    try {
      const result = await source.sendFeedback({org, repo}, skillId, revisionId,
        {verdict, reason: text, task_id: taskId.trim() || undefined},
        stableKey('feedback', skillId, revisionId, verdict, text, taskId.trim()));
      setJudgment(result.judgment_id);
      toast.success('Assessment recorded', {description: 'Judgment ' + result.judgment_id});
    } catch (failure) {
      const problem = asApiError(failure);
      setError(problem.denied ? 'This organization is not readable with your current membership. Nothing was recorded.' : 'The assessment was not recorded (' + problem.code + '). Your text is unchanged.');
      toast.error('Assessment was not recorded', {description: problem.code});
    } finally {setBusy(false);}
  }

  return <Panel title="Feedback" eyebrow="Your assessment of this revision" icon={<ChatText weight="regular" aria-hidden="true" />}>
    <div className={styles.panelBody}>
      <p className={styles.muted}>An assessment is attached to this exact revision. Members and owners may both record one.</p>
      {blocked && <p className={styles.muted}>Membership could not be reconfirmed, so nothing can be recorded right now.</p>}
      <form id="skill-feedback" className={styles.stack} onSubmit={send}>
        <fieldset className={styles.choices} disabled={blocked || busy} data-slot="rating">
          <legend>Verdict</legend>
          {verdicts.map(item => {const Icon=item.icon;return <label key={item.value} className={styles.choice}>
            <input type="radio" name="verdict" value={item.value} checked={verdict === item.value} onChange={() => setVerdict(item.value)} />
            <Icon weight={verdict===item.value?'fill':'regular'} aria-hidden="true"/><span>{item.label}<small>{item.detail}</small></span>
          </label>;})}
        </fieldset>
        <Field id="feedback-reason" label="What happened" hint="Name the task and the part of the instruction that mattered." error={error || undefined}>
          <textarea id="feedback-reason" name="reason" rows={5} required value={reason} onChange={event => {setReason(event.target.value); setError('');}} disabled={blocked || busy} aria-invalid={Boolean(error)} />
        </Field>
        <Field id="feedback-task" label="Task id" hint="Optional. Links this assessment to one episode in the usage report.">
          <input id="feedback-task" name="task_id" value={taskId} onChange={event => setTaskId(event.target.value)} disabled={blocked || busy} maxLength={120} />
        </Field>
        <div className={styles.actions}><ActionButton type="submit" tone="human" disabled={blocked || busy}>{busy ? 'Recording assessment…' : 'Record assessment'}</ActionButton></div>
        <p className={styles.feedbackStatus} role="status">{judgment ? 'Recorded as judgment ' + judgment + '. A correction refers to this identifier instead of adding a second vote.' : ''}</p>
      </form>
      <h3 className={styles.relationHeading}>Recorded assessments</h3>
      {existing.length ? <DataTable caption="Assessments already recorded for this revision" headings={['Verdict', 'Reason', 'Source', 'Recorded']}>
        {existing.map(entry => <tr key={entry.judgment_id}>
          <th scope="row"><StateBadge tone={entry.verdict === 'hindered' ? 'warning' : entry.verdict === 'helped' ? 'system' : 'neutral'}>{entry.verdict}</StateBadge></th>
          <td className={styles.pathCell}>{unknown(entry.reason)}</td>
          <td>{unknown(entry.source)}</td>
          <td>{unknown(entry.occurred_at)}</td>
        </tr>)}
      </DataTable> : <p className={styles.muted}>No assessment is recorded for this revision. That is an absence of evidence, not a negative result.</p>}
    </div>
  </Panel>;
}

export function ApiSkillRoute({ctx}: ApiProps) {
  const {source, org, repo} = ctx;
  const target = {org: org ?? '', repo: repo ?? ''};
  const ready = Boolean(org && repo);
  const skillId = ctx.params.get('skill');
  const requested = ctx.params.get('revision');
  const from = originView(ctx);
  const [raw, setRaw] = useState<{bytes: number; ready: boolean} | null>(null);
  const [rawError, setRawError] = useState('');
  const {favorites, toggle: toggleFavorite} = useFavorites(ctx);
  const detail = useAsync(() => source.getSkill(target, skillId ?? ''), 'skill:' + org + '/' + repo + ':' + skillId, ready && Boolean(skillId));
  const revisionId = requested ?? detail.value?.revision_id ?? null;
  const revision = useAsync(() => source.getRevision(target, skillId ?? '', revisionId ?? ''), 'revision:' + org + '/' + repo + ':' + skillId + ':' + revisionId, ready && Boolean(skillId && revisionId));
  // The origin keeps its own filters in the address; only this view's selection is dropped.
  const backLink = <Link className={styles.backLink} to={ctx.href(from, {tab: ctx.params.get('return_tab') || null, from: null, return_tab: null, skill: null, revision: null})}><ArrowLeft weight="regular" aria-hidden="true" />Back to {originNames[from]}</Link>;

  if (!ready) return <RepositoryRequired ctx={ctx} />;
  if (!skillId) return <RouteState state="empty" title="No skill selected" description="Open a skill from the library or the map to read its exact revision." action={<ActionButton href={ctx.href('library', {skill: null, revision: null, tab: null, from: null})} tone="system">Open Library</ActionButton>} />;
  if (detail.phase === 'error' && detail.error && !detail.value) return <div className={styles.stack}>{backLink}<ApiFailure error={detail.error} onRetry={detail.reload} retryLabel="Retry this skill" /></div>;
  if (!detail.value) return <div className={styles.stack}>{backLink}<RouteState state="loading" title="Reading this skill" description="Waiting for the summary and its revision list." /></div>;

  const skill = detail.value;
  const missingRevision = revision.phase === 'error' && revision.error && (revision.error.code === 'revision_not_found' || revision.error.status === 404);
  if (missingRevision) return <div className={styles.stack}>
    {backLink}
    <RouteState state="error" title="Revision not available"
      description="The requested revision is not stored for this skill. A newer revision is never shown in its place, because the body would then belong to a different file."
      action={<ActionButton href={ctx.href('skill', {skill: skillId, revision: skill.revision_id, tab: 'content'})} tone="system">Open the current revision</ActionButton>} />
    <Panel title="Requested revision" eyebrow="Not substituted" icon={<FileText weight="regular" aria-hidden="true" />}>
      <ProvenanceTrail entries={[
        {label: 'Skill', value: skill.name},
        {label: 'Requested revision', value: requested ?? 'Unknown', code: true},
        {label: 'Current revision', value: unknown(skill.revision_id), code: true},
        {label: 'Stored revisions', value: String(skill.revisions.length), detail: 'Every stored revision is immutable.'},
      ]} />
      {skill.revisions.length > 0 && <DataTable caption="Revisions stored for this skill" headings={['Revision', 'Commit', 'Origin', 'Created']}>
        {skill.revisions.map(entry => <tr key={entry.revision_id}>
          <th scope="row" className={styles.hashCell}><Link to={ctx.href('skill', {skill: skillId, revision: entry.revision_id, tab: 'content'})}><code>{entry.revision_id}</code></Link></th>
          <td className={styles.hashCell}><code>{unknown(entry.commit)}</code></td>
          <td>{unknown(entry.source)}</td>
          <td>{unknown(entry.created_at)}</td>
        </tr>)}
      </DataTable>}
    </Panel>
  </div>;
  if (revision.phase === 'error' && revision.error && !revision.value) return <div className={styles.stack}>{backLink}<ApiFailure error={revision.error} onRetry={revision.reload} retryLabel="Retry this revision" /></div>;

  const body = revision.value;
  const tab = skillTabs.includes(ctx.params.get('tab') || '') ? ctx.params.get('tab')! : 'content';
  const generated = body?.provenance?.origin === 'inferred';
  const degraded = readOnly(ctx, revision.phase === 'error' && Boolean(body));
  const sourceUrl = body?.source?.url ?? null;
  const requiredMissing = (body?.references ?? []).filter(reference => reference.required && !reference.available);

  async function download() {
    if (!revisionId) return;
    setRawError('');
    try {
      const text = await source.getRevisionRaw(target, skillId as string, revisionId);
      const bytes = new TextEncoder().encode(text).length;
      downloadText(skill.name + '.SKILL.md', text, 'text/markdown;charset=utf-8');
      setRaw({bytes, ready: true});
    } catch (failure) {
      setRawError('The exact file could not be read (' + asApiError(failure).code + '). Nothing was downloaded.');
    }
  }

  return <div className={styles.stack}>
    {backLink}
    {degraded && <DegradedNotice>Membership could not be reconfirmed. The body below is the last confirmed read and no assessment can be recorded.</DegradedNotice>}
    {!body && revision.phase === 'loading' && <RouteState state="loading" title="Reading this revision" description="Waiting for the exact stored bytes of the selected revision." />}
    {requiredMissing.length > 0 && <PartialNotice>{requiredMissing.length + ' required package resources are missing from this revision. Publication stays blocked until they are present.'}</PartialNotice>}
    <Panel title={skill.name} eyebrow="Immutable revision" icon={<FileText weight="regular" aria-hidden="true" />}
      action={<div className={styles.panelActions}><FavoriteToggle active={favorites.has(skill.skill_id)} name={skill.name} onToggle={()=>toggleFavorite(skill.skill_id,skill.name)}/><StateBadge tone={skill.publication_status === 'published' ? 'system' : skill.publication_status === 'needs_review' ? 'warning' : 'neutral'}>{skill.publication_status}</StateBadge></div>}>
      <div className={styles.panelBody}>
        <p className={styles.description}>{skill.description}</p>
        {generated && <p className={styles.notice} role="status"><StateBadge tone="warning">Generated</StateBadge>This revision was inferred by a generator, not taken from the source file. Read the proposal that produced it before relying on it.</p>}
        <dl className={styles.identityGrid}>
          <div><dt>Scope</dt><dd>{skill.scope}</dd></div>
          <div><dt>Owner from source</dt><dd>{unknown(skill.owner)}</dd></div>
          <div><dt>Source status</dt><dd><StateBadge>{unknown(skill.source_status)}</StateBadge></dd></div>
          <div><dt>Source layer</dt><dd>{unknown(skill.source_layer)}</dd></div>
          <div><dt>Knowledge layer</dt><dd>{skill.knowledge_layer ?? 'Unknown'}</dd></div>
          <div><dt>Provenance</dt><dd>{unknown(body?.provenance?.origin)}</dd></div>
        </dl>
        <dl className={styles.revisionStrip}>
          <div><dt>Source path</dt><dd><code>{skill.path}</code></dd></div>
          <div><dt>Revision</dt><dd><code>{unknown(revisionId)}</code></dd></div>
          <div><dt>Content SHA-256</dt><dd><code>{unknown(body?.content_sha256 ?? skill.content_sha256)}</code></dd></div>
        </dl>
        <Urn value={skill.skill_id} />
      </div>
    </Panel>
    <Tabs label="Skill sections" current={tab} items={[
      {id: 'content', label: 'Content'}, {id: 'revisions', label: 'Revisions'}, {id: 'source', label: 'Source & scope'},
      {id: 'dependencies', label: 'Dependencies'}, {id: 'feedback', label: 'Feedback'},
    ].map(item => ({...item, href: ctx.href('skill', {skill: skillId, revision: requested, tab: item.id})}))} />

    {tab === 'revisions' && <Panel title="Revision history" eyebrow="Immutable revisions" icon={<FileText weight="regular" aria-hidden="true" />}>
      {skill.revisions.length > 0 ? <DataTable caption="Revisions stored for this skill" headings={['Revision', 'Commit', 'Origin', 'Created']}>
        {skill.revisions.map(entry => <tr key={entry.revision_id}>
          <th scope="row" className={styles.hashCell}><Link to={ctx.href('skill', {skill: skillId, revision: entry.revision_id, tab: 'content'})}><code>{entry.revision_id}</code></Link></th>
          <td className={styles.hashCell}><code>{unknown(entry.commit)}</code></td>
          <td>{unknown(entry.source)}</td>
          <td>{unknown(entry.created_at)}</td>
        </tr>)}
      </DataTable> : <p className={styles.muted}>No stored revision is available for this skill.</p>}
    </Panel>}

    {tab === 'content' && <Panel title="Body" eyebrow="Exact stored revision" icon={<FileText weight="regular" aria-hidden="true" />}>
      {body?.body
        ? <><div className={styles.panelIntro}><p>Markdown of this revision. Commands are inert here.</p></div><SkillContent content={body.body} /></>
        : body
          ? <RouteState state="partial" title="Body not stored with this revision" description="The revision exists, but its body is not part of this response. Nothing is substituted from another revision." />
          : null}
    </Panel>}

    {tab === 'source' && <div className={styles.stack}>
      <Panel title="Source and scope" eyebrow="Provenance" icon={<GitBranch weight="regular" aria-hidden="true" />}>
        <ProvenanceTrail entries={[
          {label: 'Repository', value: repo ?? 'Unknown'},
          {label: 'Scope', value: skill.scope},
          {label: 'Owner from source', value: unknown(skill.owner), detail: 'Ownership metadata; not an access grant.'},
          {label: 'Source path', value: unknown(body?.source?.path ?? skill.path), code: true},
          {label: 'Commit', value: unknown(body?.source?.commit ?? skill.commit), code: true},
          {label: 'Content SHA-256', value: unknown(body?.content_sha256 ?? skill.content_sha256), code: true},
        ]} />
        <div className={styles.panelBody}>
          {sourceUrl
            ? <a className={styles.sourceLink} href={sourceUrl} target="_blank" rel="noopener noreferrer">
              <span>Open exact source revision</span><ArrowSquareOut weight="regular" aria-hidden="true" /><span className={styles.externalLabel}>{sourceUrl}</span>
            </a>
            : <p className={styles.muted}>Source host not configured. The file lives at <code>{unknown(body?.source?.path ?? skill.path)}</code> in this repository; add a Git host URL to the repository to link it.</p>}
          <div className={styles.actions}>
            <ActionButton onClick={download} disabled={!revisionId}><DownloadSimple weight="regular" aria-hidden="true" />Download exact SKILL.md</ActionButton>
          </div>
          <p className={styles.feedbackStatus} role="status">{raw?.ready ? 'Downloaded ' + raw.bytes + ' bytes. Declared SHA-256 ' + unknown(body?.content_sha256) + '.' : ''}</p>
          {rawError && <p className={styles.muted} role="alert">{rawError}</p>}
        </div>
      </Panel>
      <Panel title="Declared references" icon={<LinkSimple weight="regular" aria-hidden="true" />}>
        {body && body.references.length ? <DataTable caption="Package resources declared by this revision" headings={['Path', 'Type', 'Required', 'Available', 'SHA-256']}>
          {body.references.map(reference => <tr key={reference.path}>
            <th scope="row" className={styles.pathCell}><code>{reference.path}</code></th>
            <td>{unknown(reference.type)}</td>
            <td>{reference.required ? 'Required' : 'Optional'}</td>
            <td><StateBadge tone={reference.available ? 'system' : reference.required ? 'error' : 'warning'}>{reference.available ? 'Available' : 'Missing'}</StateBadge></td>
            <td className={styles.hashCell}><code>{unknown(reference.sha256)}</code></td>
          </tr>)}
        </DataTable> : <p className={styles.muted}>This revision declares no package resource.</p>}
      </Panel>
    </div>}

    {tab === 'dependencies' && <Panel title="Declared relationships" eyebrow="From this revision" icon={<GitBranch weight="regular" aria-hidden="true" />}>
      <div className={styles.panelBody}>
        <p>These links are declarations in the revision. They do not prove delivery to an agent.</p>
        <div className={styles.relations}>
          {(['requires', 'refines'] as const).map(type => <section key={type}>
            <h3 className={styles.relationHeading}><LinkSimple weight="regular" aria-hidden="true" />{type}</h3>
            {body && body[type].length ? <ul className={styles.relationList}>{body[type].map(id => <li key={id}>
              <Link to={ctx.href('skill', {skill: id, revision: null, tab: 'content', from, return_tab: ctx.params.get('return_tab')})}>{id}</Link>
            </li>)}</ul> : <p className={styles.muted}>None declared in this revision.</p>}
          </section>)}
        </div>
        {body && body.relations.length > 0 && <DataTable caption="Other declared relations" headings={['Relation', 'Target', 'Provenance']}>
          {body.relations.map(edge => <tr key={edge.type + ':' + edge.to}>
            <th scope="row"><code>{edge.type}</code></th>
            <td className={styles.pathCell}><Link to={ctx.href('skill', {skill: edge.to, revision: null, tab: 'content', from})}>{edge.to}</Link></td>
            <td>{unknown(edge.provenance)}</td>
          </tr>)}
        </DataTable>}
      </div>
    </Panel>}

    {tab === 'feedback' && revisionId && <FeedbackPanel key={revisionId} ctx={ctx} skillId={skillId} revisionId={revisionId} existing={body?.feedback ?? []} />}
  </div>;
}
