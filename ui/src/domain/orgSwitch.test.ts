import {describe, it, expect, vi, afterEach} from 'vitest';
import {resolveOrg, readOrgMemory, writeOrgMemory, orgSwitcherLinks} from './orgSwitch';
import type {OrgMembership} from '../api/decoders';

const meridian: OrgMembership = {org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', role: 'owner'};
const apex: OrgMembership = {org_id: 'o-2', slug: 'apex', name: 'Apex Systems', role: 'member'};
const orgs = [meridian, apex];

describe('resolveOrg', () => {
  it('uses the remembered organisation when the URL names none', () => {
    expect(resolveOrg(orgs, null, 'apex')).toEqual({membership: apex, action: null});
  });
  it('ignores a stale remembered organisation and falls back to the first membership, dropping it', () => {
    expect(resolveOrg([meridian], null, 'apex')).toEqual({membership: meridian, action: {type: 'clear'}});
  });
  it('falls back to the first membership with nothing remembered and nothing requested', () => {
    expect(resolveOrg(orgs, null, null)).toEqual({membership: meridian, action: null});
  });
  it('lets an explicit ?org= win over a different remembered organisation and remembers it', () => {
    expect(resolveOrg(orgs, 'apex', 'meridian')).toEqual({membership: apex, action: {type: 'set', value: 'apex'}});
  });
  it('matches ?org= by org_id as well as slug', () => {
    expect(resolveOrg(orgs, 'o-2', null)).toEqual({membership: apex, action: {type: 'set', value: 'apex'}});
  });
  it('resolves an unknown ?org= to no membership without touching a good remembered value', () => {
    expect(resolveOrg(orgs, 'someone-else', 'meridian')).toEqual({membership: null, action: null});
  });
  it('resolves to no membership with no organisations at all, and never writes storage', () => {
    expect(resolveOrg([], null, null)).toEqual({membership: null, action: null});
    expect(resolveOrg([], null, 'meridian')).toEqual({membership: null, action: {type: 'clear'}});
  });
});

describe('org memory (localStorage)', () => {
  afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

  it('reads back what it wrote, namespaced by user', () => {
    writeOrgMemory('u-1', {type: 'set', value: 'apex'});
    expect(readOrgMemory('u-1')).toBe('apex');
    expect(readOrgMemory('u-2')).toBeNull();
  });
  it('clears the remembered value', () => {
    writeOrgMemory('u-1', {type: 'set', value: 'apex'});
    writeOrgMemory('u-1', {type: 'clear'});
    expect(readOrgMemory('u-1')).toBeNull();
  });
  it('does nothing for a null action', () => {
    writeOrgMemory('u-1', {type: 'set', value: 'apex'});
    writeOrgMemory('u-1', null);
    expect(readOrgMemory('u-1')).toBe('apex');
  });
  it('behaves correctly when storage throws on read and on write', () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(readOrgMemory('u-1')).toBeNull();
    getItem.mockRestore();
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(() => writeOrgMemory('u-1', {type: 'set', value: 'apex'})).not.toThrow();
    setItem.mockRestore();
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(() => writeOrgMemory('u-1', {type: 'clear'})).not.toThrow();
    removeItem.mockRestore();
  });
});

describe('orgSwitcherLinks', () => {
  it('marks the current organisation and builds each link by dropping repo and setting org', () => {
    const buildHref = (changes: Record<string, unknown>) => '/library?org=' + changes.org + '&repo=' + (changes.repo ?? '');
    const links = orgSwitcherLinks(orgs, meridian, buildHref);
    expect(links).toEqual([
      {org: meridian, current: true, href: '/library?org=meridian&repo='},
      {org: apex, current: false, href: '/library?org=apex&repo='},
    ]);
  });
  it('marks nothing current when there is no current membership', () => {
    const links = orgSwitcherLinks(orgs, null, () => '/library');
    expect(links.every(link => !link.current)).toBe(true);
  });
});
