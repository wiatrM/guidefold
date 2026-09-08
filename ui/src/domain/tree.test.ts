import {describe, expect, test} from 'vitest';
import {compactTree} from './tree';
import type {TreeNode} from '../domain';

describe('compactTree', () => {
  test('a chain of 3 single-child directories collapses to one row', () => {
    const nodes: TreeNode[] = [{
      id: '.agents', label: '.agents/', children: [{
        id: '.agents/skills', label: 'skills/', children: [{
          id: '.agents/skills/postgres-auth', label: 'postgres-auth/', children: [
            {id: 'urn:skill:meridian:postgres-auth', label: 'postgres-auth', href: '/skill?skill=x'},
          ],
        }],
      }],
    }];
    const result = compactTree(nodes);
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe('.agents/skills/postgres-auth/');
    expect(result[0].id).toBe('.agents/skills/postgres-auth');
    expect(result[0].children).toHaveLength(1);
    expect(result[0].children![0].label).toBe('postgres-auth');
  });

  test('a directory with 2 children does not collapse', () => {
    const nodes: TreeNode[] = [{
      id: 'platforms', label: 'platforms/', children: [
        {id: 'platforms/atlas', label: 'atlas/', children: [{id: 'a', label: 'a', href: '/a'}]},
        {id: 'platforms/forge', label: 'forge/', children: [{id: 'b', label: 'b', href: '/b'}]},
      ],
    }];
    const result = compactTree(nodes);
    expect(result[0].label).toBe('platforms/');
    expect(result[0].children).toHaveLength(2);
  });

  test('a directory containing both a file and a subdirectory does not collapse past that point', () => {
    const nodes: TreeNode[] = [{
      id: 'root', label: 'root/', children: [{
        id: 'root/mid', label: 'mid/', children: [
          {id: 'root/mid/notes', label: 'notes.md', href: '/notes'},
          {id: 'root/mid/sub', label: 'sub/', children: [{id: 'leaf', label: 'leaf', href: '/leaf'}]},
        ],
      }],
    }];
    const result = compactTree(nodes);
    // root's only content was one subdirectory (mid), so root+mid merge into one row.
    expect(result).toHaveLength(1);
    expect(result[0].label).toBe('root/mid/');
    // mid holds a file and a subdirectory (2 entries), so the merge stops there.
    expect(result[0].children).toHaveLength(2);
    const sub = result[0].children!.find(child => child.label === 'sub/');
    // sub's only content is a file, not a directory, so it does not merge into its leaf.
    expect(sub?.children).toEqual([{id: 'leaf', label: 'leaf', href: '/leaf'}]);
  });

  test('sibling chains that collapse to different depths keep unique ids', () => {
    const nodes: TreeNode[] = [
      {id: 'a', label: 'a/', children: [{id: 'a/b', label: 'b/', children: [{id: 'leaf-1', label: 'x', href: '/1'}]}]},
      {id: 'c', label: 'c/', children: [{id: 'c/d', label: 'd/', children: [{id: 'leaf-2', label: 'y', href: '/2'}]}]},
    ];
    const result = compactTree(nodes);
    const ids = result.map(node => node.id);
    expect(ids).toEqual(['a/b', 'c/d']);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test('a leaf node passes through unchanged', () => {
    const nodes: TreeNode[] = [{id: 'leaf', label: 'README', href: '/readme', detail: 'root · org'}];
    expect(compactTree(nodes)).toEqual(nodes);
  });
});
