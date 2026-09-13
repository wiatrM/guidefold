import { describe, expect, test, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiLibraryRoute } from './CatalogRoutes';
import { ApiError } from '../api/client';
import type { DuplicateGroup, SkillPage, SkillSummary } from '../api/decoders';
import type { SkillQuery } from '../data/source';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';

const summary = (name: string, over: Partial<SkillSummary> = {}): SkillSummary => ({
  skill_id: 'urn:skill:meridian:forge.pipelines:' + name, repo_id: 'monorepo', name, description: '[forge.pipelines] ' + name,
  scope: 'forge.pipelines', owner: 'pipelines-team', source_layer: 'team', knowledge_layer: 'unclassified',
  source_status: 'active', publication_status: 'draft', path: 'platforms/forge/' + name + '/SKILL.md',
  content_sha256: 'sha-' + name, revision_id: 'rev-' + name, card_revision: null, package_digest: null, commit: 'c0ffee', updated_at: null,
  ...over,
});
const page = (over: Partial<SkillPage> = {}): SkillPage => ({
  items: [summary('pipeline-testing')], next_cursor: null, snapshot_id: 'snap-1', schema_version: 'mgmt-1', filters: {}, ...over,
});
const facets = fakeSource({
  listSkills: async () => page(),
  getFacets: async (_target, query) => ({ field: query.field, values: [{ value: 'forge.pipelines', count: 4 }], next_cursor: null }),
  lookupFacet: async (_target, field, value) => ({ field, value, count: 0, available: false }),
});

describe('Library route, hosted API, six states', () => {
  test('Empty: an unfiltered empty catalog points at Import', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page({ items: [] }),
      getFacets: async () => ({ field: 'scope', values: [], next_cursor: null }),
    }));
    expect(await screen.findByText('No skills yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Import' })).toBeInTheDocument();
  });

  test('Loading: nothing is claimed before the first page arrives', () => {
    renderApi(ApiLibraryRoute, fakeSource({ listSkills: () => new Promise(() => {}), getFacets: () => new Promise(() => {}) }));
    expect(screen.getByText('Reading the catalog')).toBeInTheDocument();
  });

  test('Partial: an unavailable filter value is named, never widened to All', async () => {
    const source = fakeSource({
      listSkills: async () => page({ items: [], filters: { scope: { value: 'missing-scope', available: false } } }),
      getFacets: async (_target, query) => ({ field: query.field, values: [{ value: 'forge.pipelines', count: 4 }], next_cursor: null }),
      lookupFacet: async (_target, field, value) => ({ field, value, count: 0, available: false }),
    });
    renderApi(ApiLibraryRoute, source, 'scope=missing-scope');
    expect(await screen.findByText(/This snapshot has no value missing-scope/)).toBeInTheDocument();
    const field = screen.getByLabelText('Scope');
    expect(field).toHaveValue('missing-scope');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('option', { name: 'Not available in this snapshot: missing-scope' })).toBeInTheDocument();
    expect(screen.getAllByText('Filter value unavailable')).toHaveLength(2);
  });

  test('Error: the page offers a retry and claims nothing about the catalog', async () => {
    let fail = true;
    const listSkills = vi.fn(async () => {
      if (fail) throw new ApiError({ status: 503, code: 'backend_unavailable', message: 'no' });
      return page();
    });
    renderApi(ApiLibraryRoute, fakeSource({ listSkills, getFacets: async () => ({ field: 'scope', values: [], next_cursor: null }) }));
    const retry = await screen.findByRole('button', { name: 'Retry this page' });
    fail = false;
    await userEvent.click(retry);
    expect(await screen.findByText('pipeline-testing')).toBeInTheDocument();
  });

  test('Degraded: an unconfirmed membership keeps the last page read only', async () => {
    renderApi(ApiLibraryRoute, facets, '', { access: { status: 'offline', me: null, checkedAt: 1 } });
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
    expect(screen.getByText(/Membership could not be reconfirmed/)).toBeInTheDocument();
  });

  test('Restricted: a denial says nothing about the content', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'no' }); },
      getFacets: async () => ({ field: 'scope', values: [], next_cursor: null }),
    }));
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('pipeline-testing')).not.toBeInTheDocument();
  });
});

describe('Library route, filters and paging', () => {
  test('filters round-trip through the URL and reset the cursor', async () => {
    const { ctx } = renderApi(ApiLibraryRoute, facets, 'q=auth&scope=forge.pipelines&cursor=page-2');
    expect(await screen.findByText('pipeline-testing')).toBeInTheDocument();
    expect(screen.getByLabelText('Search name, description or path')).toHaveValue('auth');
    expect(screen.getByLabelText('Scope')).toHaveValue('forge.pipelines');
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    expect(ctx.go).toHaveBeenCalledWith('library', expect.objectContaining({ q: 'auth', scope: 'forge.pipelines', cursor: null }));
  });

  test('the active value stays selectable when it is outside the facet page', async () => {
    const source = fakeSource({
      listSkills: async () => page(),
      getFacets: async (_target, query) => ({ field: query.field, values: [{ value: 'atlas.identity', count: 2 }], next_cursor: 'facet-2' }),
      lookupFacet: async (_target, field, value) => ({ field, value, count: 7, available: true }),
    });
    renderApi(ApiLibraryRoute, source, 'scope=forge.pipelines');
    expect(await screen.findByRole('option', { name: 'forge.pipelines' })).toBeInTheDocument();
    expect(screen.getByLabelText('Scope')).toHaveValue('forge.pipelines');
    expect(screen.getByLabelText('Scope')).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('cursor paging walks forward and back through the URL', async () => {
    const asked: (string | undefined)[] = [];
    const source = fakeSource({
      listSkills: async (_target, query: SkillQuery) => { asked.push(query.cursor); return page({ next_cursor: 'page-2' }); },
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
    });
    const { ctx } = renderApi(ApiLibraryRoute, source);
    expect(await screen.findByText('pipeline-testing')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(ctx.go).toHaveBeenCalledWith('library', { cursor: 'page-2' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Previous page' }));
    expect(ctx.go).toHaveBeenLastCalledWith('library', { cursor: null });
    expect(asked).toEqual([undefined]);
  });

  test('no body is fetched to render the list', async () => {
    const getRevision = vi.fn();
    const getSkill = vi.fn();
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page(),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
      getSkill, getRevision,
    }));
    expect(await screen.findByText('pipeline-testing')).toBeInTheDocument();
    expect(getSkill).not.toHaveBeenCalled();
    expect(getRevision).not.toHaveBeenCalled();
  });

  test('ADR-0047: no repository reads the whole organisation and each row names its repository', async () => {
    const listSkills = vi.fn(async () => page({ items: [summary('pipeline-testing'), summary('billing-rules', { repo_id: 'billing', scope: 'billing.core' })] }));
    const getFacets = vi.fn(async (_target: unknown, query: { field: string }) => ({ field: query.field, values: [], next_cursor: null }));
    renderApi(ApiLibraryRoute, fakeSource({ listSkills, getFacets }), '', { repo: null });
    const first = (await screen.findByRole('link', { name: 'pipeline-testing' })).closest('tr')!;
    expect(screen.queryByText('No repository selected')).not.toBeInTheDocument();
    expect(listSkills).toHaveBeenCalledWith({ org: 'meridian', repo: null }, expect.anything());
    expect(getFacets).toHaveBeenCalledWith({ org: 'meridian', repo: null }, { field: 'scope' });
    expect(within(first).getByText('monorepo', { selector: 'code' })).toBeInTheDocument();
    const second = screen.getByRole('link', { name: 'billing-rules' }).closest('tr')!;
    expect(within(second).getByText('billing', { selector: 'code' })).toBeInTheDocument();
  });

  test('with a repository chosen the row does not repeat it', async () => {
    renderApi(ApiLibraryRoute, facets);
    const row = (await screen.findByRole('link', { name: 'pipeline-testing' })).closest('tr')!;
    expect(within(row).queryByText('monorepo', { selector: 'code' })).not.toBeInTheDocument();
  });
});

describe('Library route, rows', () => {
  test('a favorite is an accessible badge action and stays saved for this account and repository', async () => {
    const key = 'guidefold-favorites-v1:u1:meridian:monorepo';
    localStorage.removeItem(key);
    const view = renderApi(ApiLibraryRoute, facets);
    const add = await screen.findByRole('button', { name: 'Add pipeline-testing to favorites' });
    await userEvent.click(add);
    expect(add).toHaveAttribute('aria-pressed', 'true');
    expect(JSON.parse(localStorage.getItem(key) ?? '[]')).toContain('urn:skill:meridian:forge.pipelines:pipeline-testing');
    view.unmount();
    renderApi(ApiLibraryRoute, facets);
    expect(await screen.findByRole('button', { name: 'Remove pipeline-testing from favorites' })).toHaveAttribute('aria-pressed', 'true');
    localStorage.removeItem(key);
  });

  test('publication status is a labelled badge whose tone follows the state; colour never stands alone', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page({ items: [summary('published-one', { publication_status: 'published' }), summary('review-one', { publication_status: 'needs_review' }), summary('draft-one')] }),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
    }));
    const published = await screen.findByText('published');
    expect(getComputedStyle(published).color).toBe('var(--system-ink)');
    expect(getComputedStyle(screen.getByText('needs_review')).color).toBe('var(--warning-ink)');
    expect(getComputedStyle(screen.getByText('draft')).color).not.toBe('var(--warning-ink)');
  });

  test('an absent owner, layer or knowledge layer reads Unknown, never an empty cell', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page({ items: [summary('bare', { owner: null, source_layer: null, knowledge_layer: null })] }),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
    }));
    const row = (await screen.findByRole('link', { name: 'bare' })).closest('tr')!;
    expect(within(row).getAllByText('Unknown')).toHaveLength(2);
    expect(within(row).getByText('Knowledge layer: Unknown')).toBeInTheDocument();
  });

  test('the source details disclosure holds the description and path, and the name links to the exact revision', async () => {
    const user = userEvent.setup();
    renderApi(ApiLibraryRoute, facets);
    const link = await screen.findByRole('link', { name: 'pipeline-testing' });
    expect(link).toHaveAttribute('href', expect.stringContaining('skill=urn%3Askill%3Ameridian%3Aforge.pipelines%3Apipeline-testing'));
    expect(link).toHaveAttribute('href', expect.stringContaining('revision=rev-pipeline-testing'));
    await user.click(screen.getByText('Source details'));
    expect(screen.getByText('[forge.pipelines] pipeline-testing')).toBeInTheDocument();
    expect(screen.getByText('platforms/forge/pipeline-testing/SKILL.md')).toBeInTheDocument();
  });

  test('the page summary names the count, whether more pages follow and the snapshot', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page({ items: [summary('a'), summary('b')], next_cursor: 'page-2', snapshot_id: null }),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
    }));
    expect(await screen.findByText(/2 skill summaries on this page, more pages follow/)).toBeInTheDocument();
    expect(screen.getByText(/Snapshot Unknown\./)).toBeInTheDocument();
    expect(screen.getByText('2 on this page')).toBeInTheDocument();
  });
});

const group = (name: string, identical = true): DuplicateGroup => ({
  name, repos: ['meridian', 'second'], count: 2, identical,
  skills: ['meridian', 'second'].map(repo => ({ skill_id: 'urn:skill:' + repo + ':_root:' + name, repo_id: repo, scope: '_root', path: '.agents/skills/' + name + '/SKILL.md', content_sha256: 'sha', publication_status: 'draft' })),
});
const sevenGroups = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((name, index) => group('skill-' + name, index !== 1));

describe('Library route, duplicates across repositories (contract 1.12.0)', () => {
  test('a compact panel shows five groups, their badges and a link to all of them', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page(),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
      listDuplicates: async () => ({ items: sevenGroups, next_cursor: null }),
    }), '', { repo: null });
    const panel = (await screen.findByText('Duplicated across repositories')).closest('section') ?? document.body;
    const table = within(panel as HTMLElement).getByRole('table', { name: 'Skill names that appear in more than one repository' });
    expect(within(table).getAllByRole('row')).toHaveLength(6);
    expect(within(table).queryByText('skill-f')).not.toBeInTheDocument();
    expect(within(table).getAllByText('Differs')).toHaveLength(1);
    expect(within(table).getAllByText('Identical')).toHaveLength(4);
    expect(screen.getByRole('link', { name: 'Show all 7' })).toHaveAttribute('href', expect.stringContaining('duplicates=1'));
    expect(screen.getByText('pipeline-testing')).toBeInTheDocument();
  });

  test('each copy links to its own Skill view with its repository', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page(),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
      listDuplicates: async () => ({ items: [group('adr-process')], next_cursor: 'more' }),
    }), '', { repo: null });
    const link = await screen.findByRole('link', { name: 'Open adr-process in second' });
    expect(link).toHaveAttribute('href', expect.stringContaining('repo=second'));
    expect(link).toHaveAttribute('href', expect.stringContaining('skill=' + encodeURIComponent('urn:skill:second:_root:adr-process')));
    expect(screen.getByRole('link', { name: 'Show all 1+' })).toBeInTheDocument();
  });

  test('no group means no panel', async () => {
    renderApi(ApiLibraryRoute, fakeSource({
      listSkills: async () => page(),
      getFacets: async (_target, query) => ({ field: query.field, values: [], next_cursor: null }),
      listDuplicates: async () => ({ items: [], next_cursor: null }),
    }));
    expect(await screen.findByText('pipeline-testing')).toBeInTheDocument();
    expect(screen.queryByText('Duplicated across repositories')).not.toBeInTheDocument();
  });

  test('duplicates=1 replaces the skill list with every group and a way back', async () => {
    const listSkills = vi.fn(async () => page());
    renderApi(ApiLibraryRoute, fakeSource({ listSkills, listDuplicates: async () => ({ items: sevenGroups, next_cursor: null }) }), 'duplicates=1', { repo: null });
    const table = await screen.findByRole('table', { name: 'Skill names that appear in more than one repository' });
    expect(within(table).getAllByRole('row')).toHaveLength(8);
    expect(screen.getByRole('link', { name: 'Back to all skills' })).not.toHaveAttribute('href', expect.stringContaining('duplicates'));
    expect(listSkills).not.toHaveBeenCalled();
    expect(screen.queryByText('pipeline-testing')).not.toBeInTheDocument();
  });

  test('duplicates=1 with no group says so plainly', async () => {
    renderApi(ApiLibraryRoute, fakeSource({ listDuplicates: async () => ({ items: [], next_cursor: null }) }), 'duplicates=1', { repo: null });
    expect(await screen.findByText('No skill name appears in more than one repository you can read.')).toBeInTheDocument();
  });
});
