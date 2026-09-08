import {describe, expect, test} from 'vitest';
import {pyramidBands, isFullyUnclassified} from './pyramid';
import type {Skill} from '../domain';

function makeSkill(over: Partial<Skill> & {id: string}): Skill {
  return {
    name: over.id, scope: 'root', owner: 'team', sourceLayer: 'team', knowledgeLayer: 'Unclassified',
    sourceStatus: 'active', description: '', body: '', raw: '', path: over.id + '/SKILL.md',
    revision: 'sha-' + over.id, bytes: 0, requires: [], refines: [], references: [],
    ...over,
  };
}

describe('pyramidBands', () => {
  test('all-unclassified groups into one band', () => {
    const skills = [makeSkill({id: 'a'}), makeSkill({id: 'b'}), makeSkill({id: 'c'})];
    const bands = pyramidBands(skills);
    expect(bands).toHaveLength(1);
    expect(bands[0].layer).toBe('unclassified');
    expect(bands[0].items).toHaveLength(3);
    expect(isFullyUnclassified(bands)).toBe(true);
  });

  test('a mix of layers groups correctly, ordered abstract, task, atomic, unclassified', () => {
    const skills = [
      makeSkill({id: 'atomic-1', knowledgeLayer: 'atomic'}),
      makeSkill({id: 'abstract-1', knowledgeLayer: 'Abstract'}),
      makeSkill({id: 'task-1', knowledgeLayer: 'TASK'}),
      makeSkill({id: 'unknown-1', knowledgeLayer: 'weird-value'}),
    ];
    const bands = pyramidBands(skills);
    expect(bands.map(band => band.layer)).toEqual(['abstract', 'task', 'atomic', 'unclassified']);
    expect(bands.find(band => band.layer === 'abstract')?.items[0].skill.id).toBe('abstract-1');
    expect(bands.find(band => band.layer === 'unclassified')?.items[0].skill.id).toBe('unknown-1');
    expect(isFullyUnclassified(bands)).toBe(false);
  });

  test('an empty band is never included', () => {
    const skills = [makeSkill({id: 'atomic-1', knowledgeLayer: 'atomic'})];
    const bands = pyramidBands(skills);
    expect(bands).toHaveLength(1);
    expect(bands[0].layer).toBe('atomic');
  });

  test('a refines parent renders in the item data, and the parent gains the child in its family', () => {
    const skills = [
      makeSkill({id: 'postgres-production', knowledgeLayer: 'abstract'}),
      makeSkill({id: 'postgres-auth', knowledgeLayer: 'task', refines: ['postgres-production']}),
    ];
    const bands = pyramidBands(skills);
    const child = bands.find(band => band.layer === 'task')!.items[0];
    expect(child.skill.id).toBe('postgres-auth');
    expect(child.parentIds).toEqual(['postgres-production']);
    const parent = bands.find(band => band.layer === 'abstract')!.items[0];
    expect(parent.skill.id).toBe('postgres-production');
    expect(parent.childIds).toEqual(['postgres-auth']);
  });
});
