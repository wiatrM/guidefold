import {describe, expect, test} from 'vitest';
import {hasAnyClassification, knowledgeLayerOrder, pyramidGraphBands, pyramidGraphEdges} from './pyramidGraph';
import type {RelationEdge, RelationType, SkillSummary} from '../api/decoders';

const skill = (name: string, knowledge_layer: SkillSummary['knowledge_layer']): SkillSummary => ({
  skill_id: 'urn:skill:meridian:atlas.identity:' + name, name, description: '', scope: 'atlas.identity', owner: 'identity-team',
  source_layer: 'team', knowledge_layer, source_status: 'active', publication_status: 'published',
  path: 'platforms/atlas/identity/' + name + '/SKILL.md', content_sha256: 'sha-' + name, revision_id: 'rev-' + name,
  card_revision: null, package_digest: null, commit: 'c0ffee', updated_at: null,
});
const edge = (from: string, to: string, type: RelationType = 'refines'): RelationEdge =>
  ({from: 'urn:skill:meridian:atlas.identity:' + from, to: 'urn:skill:meridian:atlas.identity:' + to, type, provenance: 'source', revision: null});

describe('pyramidGraphBands', () => {
  test('every layer is present, in general-to-specific order, even when empty', () => {
    const bands = pyramidGraphBands([skill('postgres-auth', 'task')]);
    expect(bands.map(band => band.layer)).toEqual([...knowledgeLayerOrder]);
    expect(bands.find(band => band.layer === 'task')?.items.map(item => item.label)).toEqual(['postgres-auth']);
    expect(bands.find(band => band.layer === 'abstract')?.items).toEqual([]);
  });

  test('a skill without a declared layer joins unclassified; nothing is inferred', () => {
    const bands = pyramidGraphBands([skill('secrets', null), skill('rbac-policies', 'abstract')]);
    expect(bands.find(band => band.layer === 'unclassified')?.items.map(item => item.label)).toEqual(['secrets']);
    expect(bands.find(band => band.layer === 'abstract')?.items.map(item => item.label)).toEqual(['rbac-policies']);
  });

  test('a node carries the identity, name and scope the chart and its text alternative need', () => {
    const [item] = pyramidGraphBands([skill('postgres-auth', 'atomic')]).find(band => band.layer === 'atomic')!.items;
    expect(item).toEqual({id: 'urn:skill:meridian:atlas.identity:postgres-auth', label: 'postgres-auth', detail: 'atlas.identity'});
  });
});

describe('pyramidGraphEdges', () => {
  test('keeps refines edges whose both ends are in the scoped skill list, and drops the rest', () => {
    const skills = [skill('postgres-auth', 'task'), skill('postgres-production', 'abstract')];
    const edges = pyramidGraphEdges(skills, [
      edge('postgres-auth', 'postgres-production'),
      edge('postgres-auth', 'outside-scope'),
      edge('postgres-auth', 'postgres-production', 'requires'),
    ]);
    expect(edges).toEqual([{from: 'urn:skill:meridian:atlas.identity:postgres-auth', to: 'urn:skill:meridian:atlas.identity:postgres-production'}]);
  });
});

describe('hasAnyClassification', () => {
  test('is false while every skill is unclassified and true once one carries a layer', () => {
    expect(hasAnyClassification(pyramidGraphBands([skill('a', null), skill('b', 'unclassified')]))).toBe(false);
    expect(hasAnyClassification(pyramidGraphBands([skill('a', null), skill('b', 'task')]))).toBe(true);
  });
});
