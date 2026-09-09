import { describe, expect, test, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiMapRoute } from './CatalogRoutes';
import { ApiError } from '../api/client';
import type { MapRepository, MapScopes, ModulePage, Relations, SkillPage } from '../api/decoders';
import { fakeSource } from '../test/fakes';
import { renderApi } from '../test/apiRoute';
vi.mock('../components/PyramidChart/SchemaFlow',()=>({SchemaFlow:()=> <div role="region" aria-label="Skill hierarchy"/>}));

const root: MapRepository = {
  path: '', next_cursor: null,
  children: [
    { name: 'platforms', path: 'platforms', kind: 'dir', skill_id: null, count: 12 },
    { name: 'AGENTS.md', path: 'AGENTS.md', kind: 'document', skill_id: null, count: null },
  ],
};
const branch: MapRepository = {
  path: 'platforms', next_cursor: 'more-1',
  children: [{ name: 'pipeline-testing', path: 'platforms/forge/SKILL.md', kind: 'skill', skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', count: null }],
};
const scopes: MapScopes = {
  scope: { id: 'forge.pipelines', owner: 'pipelines-team', paths: ['platforms/forge'], parent: 'forge' },
  children: [{ id: 'forge.pipelines.build', owner: null, skills: 3 }],
  skills: [{ skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', name: 'pipeline-testing' }],
  unmapped: [{ skill_id: 'urn:skill:meridian:_index:hierarchy-index', name: 'hierarchy-index' }],
};
const relations: Relations = {
  items: [
    { from: 'urn:a', to: 'urn:b', type: 'requires', provenance: 'source', revision: 'rev-b' },
    { from: 'urn:a', to: 'urn:c', type: 'similar', provenance: 'inferred', revision: null },
  ],
  next_cursor: null, truncated: true,
};
const module: ModulePage = {
  scope: 'forge.pipelines', owner: 'pipelines-team',
  skills: [{
    skill_id: 'urn:a', name: 'pipeline-testing', description: 'Read first', scope: 'forge.pipelines', owner: null,
    source_layer: 'team', knowledge_layer: 'unclassified', source_status: 'active', publication_status: 'published',
    path: 'p/SKILL.md', content_sha256: null, revision_id: 'rev-a', card_revision: null, package_digest: null, commit: null, updated_at: null,
  }],
  reading_order: ['urn:a'],
  shared: [{ skill_id: 'urn:shared', name: 'postgres-auth', used_by: ['atlas.identity', 'forge.pipelines'] }],
  documents: [{ path: 'platforms/forge/AGENTS.md', kind: 'document' }],
};

const familyPage: SkillPage = {
  items: [
    { skill_id: 'urn:skill:meridian:forge.ontology:schema-evolution', name: 'schema-evolution', description: '', scope: 'forge.ontology', owner: null, source_layer: 'team', knowledge_layer: 'abstract', source_status: 'active', publication_status: 'published', path: 'p1', content_sha256: null, revision_id: 'r1', card_revision: null, package_digest: null, commit: null, updated_at: null },
    { skill_id: 'urn:skill:meridian:forge.ontology:object-type-migrations', name: 'object-type-migrations', description: '', scope: 'forge.ontology', owner: 'ontology-team', source_layer: 'team', knowledge_layer: 'task', source_status: 'active', publication_status: 'published', path: 'p2', content_sha256: null, revision_id: 'r2', card_revision: null, package_digest: null, commit: null, updated_at: null },
  ],
  next_cursor: null, snapshot_id: null, schema_version: null, filters: {},
};
const familyRefines: Relations = {
  items: [{ from: 'urn:skill:meridian:forge.ontology:object-type-migrations', to: 'urn:skill:meridian:forge.ontology:schema-evolution', type: 'refines', provenance: 'source', revision: null }],
  next_cursor: null, truncated: false,
};

describe('Map route, hosted API, six states', () => {
  test('Empty: a layer axis with no classification names the absence', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapLayers: async () => ({ layers: [] }) }), 'tab=pyramid');
    expect(await screen.findByText('No classified layer')).toBeInTheDocument();
  });

  test('Loading: the repository branch is awaited', () => {
    renderApi(ApiMapRoute, fakeSource({ getMapRepository: () => new Promise(() => {}) }), 'tab=repository');
    expect(screen.getByText('Reading this directory')).toBeInTheDocument();
  });

  test('Partial: a truncated relation list says so instead of implying completeness', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapRepository: async () => root, getRelations: async () => relations }), 'tab=repository&skill=urn:a');
    expect(await screen.findByText(/The API truncated this neighbourhood/)).toBeInTheDocument();
    expect(screen.getByText('similar')).toBeInTheDocument();
    expect(screen.getByText('requires')).toBeInTheDocument();
  });

  test('Error: one branch fails without hiding the rest of the map', async () => {
    let fail = true;
    const getMapRepository = vi.fn(async () => {
      if (fail) throw new ApiError({ status: 500, code: 'internal_error', message: 'no' });
      return root;
    });
    renderApi(ApiMapRoute, fakeSource({ getMapRepository }), 'tab=repository');
    const retry = await screen.findByRole('button', { name: 'Retry this branch' });
    fail = false;
    await userEvent.click(retry);
    expect(await screen.findByText('platforms/')).toBeInTheDocument();
  });

  test('Degraded: an unconfirmed membership marks the map read only', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapRepository: async () => root }), 'tab=repository', { access: { status: 'offline', me: null, checkedAt: 1 } });
    expect(await screen.findByText('Degraded')).toBeInTheDocument();
  });

  test('Restricted: a denial reveals no node', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapScopes: async () => { throw new ApiError({ status: 403, code: 'forbidden', message: 'no' }); } }), 'tab=scopes');
    expect(await screen.findByText('Not available to your account')).toBeInTheDocument();
    expect(screen.queryByText('forge.pipelines')).not.toBeInTheDocument();
  });
});

describe('Map route, three axes', () => {
  test('a directory is read only when it is opened', async () => {
    const asked: string[] = [];
    const getMapRepository = vi.fn(async (_target, path = '') => { asked.push(path); return path ? branch : root; });
    renderApi(ApiMapRoute, fakeSource({ getMapRepository }), 'tab=repository');
    expect(await screen.findByText('platforms/')).toBeInTheDocument();
    expect(asked).toEqual(['']);
    await userEvent.click(screen.getByText('platforms/'));
    expect(await screen.findByRole('link', { name: 'pipeline-testing' })).toBeInTheDocument();
    expect(asked).toEqual(['', 'platforms']);
    expect(screen.getByRole('button', { name: 'Read the next 100 objects' })).toBeInTheDocument();
  });

  test('the scope axis names an unmapped scope and opens the module panel', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapScopes: async () => scopes, getModule: async () => module }), 'tab=scopes&scope=forge.pipelines');
    expect(await screen.findByText('Unmapped scope')).toBeInTheDocument();
    expect(screen.getByText(/hierarchy-index/)).toBeInTheDocument();
    expect(await screen.findByText('Module forge.pipelines')).toBeInTheDocument();
    expect(screen.getByText('Shared with other modules')).toBeInTheDocument();
    expect(screen.getByText('Used by atlas.identity, forge.pipelines')).toBeInTheDocument();
  });

  test('the pyramid axis lists declared layers only', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapLayers: async () => ({ layers: [{ layer: 'unclassified', count: 27 }] }) }), 'tab=pyramid');
    expect(await screen.findByText('unclassified')).toBeInTheDocument();
    expect(screen.getByText('27')).toBeInTheDocument();
  });

  test('the pyramid axis prompts for a scope before it draws a family graph', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapLayers: async () => ({ layers: [] }) }), 'tab=pyramid');
    expect(await screen.findByRole('link', { name: 'Open the Scopes tab' })).toBeInTheDocument();
  });

  test('the pyramid axis draws the family of a chosen scope from its skills and refines edges', async () => {
    renderApi(ApiMapRoute, fakeSource({
      getMapLayers: async () => ({ layers: [] }),
      listSkills: async () => familyPage,
      getRelations: async (_target, query) => query.type === 'refines' ? familyRefines : relations,
    }), 'tab=pyramid&scope=forge.ontology');
    await userEvent.click(await screen.findByRole('button', { name: 'List' }));
    expect(await screen.findByRole('button', { name: 'object-type-migrations' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'schema-evolution' })).toBeInTheDocument();
    expect(screen.getByText('Text alternative: refines relationships within forge.ontology')).toBeInTheDocument();
  });

  test('a scope with no classified skill names the absence instead of an empty chart', async () => {
    renderApi(ApiMapRoute, fakeSource({
      getMapLayers: async () => ({ layers: [] }),
      listSkills: async () => ({ ...familyPage, items: familyPage.items.map(item => ({ ...item, knowledge_layer: 'unclassified' })) }),
      getRelations: async () => ({ items: [], next_cursor: null, truncated: false }),
    }), 'tab=pyramid&scope=forge.ontology');
    expect(await screen.findByText('No classified skill in this scope')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'object-type-migrations' })).not.toBeInTheDocument();
  });

  test('the selected object stays in the address', async () => {
    renderApi(ApiMapRoute, fakeSource({ getMapRepository: async () => root, getRelations: async () => ({ ...relations, truncated: false }) }), 'tab=repository&skill=urn:a');
    const open = await screen.findByRole('link', { name: 'Open this skill' });
    expect(open).toHaveAttribute('href', expect.stringContaining('skill=urn%3Aa'));
    expect(open).toHaveAttribute('href', expect.stringContaining('return_tab=repository'));
  });
});
