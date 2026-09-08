import { describe, expect, test, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiLibraryRoute } from './CatalogRoutes';
import { ApiError } from '../api/client';
import type { SkillPage, SkillSummary } from '../api/decoders';
import type { SkillQuery } from '../data/source';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';

const summary = (name: string, over: Partial<SkillSummary> = {}): SkillSummary => ({
  skill_id: 'urn:skill:meridian:forge.pipelines:' + name, name, description: '[forge.pipelines] ' + name,
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

  test('a repository is required before anything is read', () => {
    renderApi(ApiLibraryRoute, fakeSource(), '', { repo: null });
    expect(screen.getByText('No repository selected')).toBeInTheDocument();
  });
});

describe('Library route, rows', () => {
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
