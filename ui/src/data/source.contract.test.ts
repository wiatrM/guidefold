/**
 * The behavioural promise of the DataSource port.
 *
 * `hexagonal-architecture` ("Testuj po obu stronach portu") asks that the port, not the adapter,
 * carries the promise the routes rely on. Everything asserted here is what a route may assume of
 * any implementation handed to it: the operations exist, unsent drafts round-trip in RAM, and the
 * three reads every composition starts with answer in the shape the decoders declare. The hosted
 * API adapter is the one production implementation; `fakeSource` is checked against the same list.
 *
 * It is a smoke suite over the port, not a second copy of the adapter's own tests.
 */
import { describe, expect, test } from 'vitest';
import { ApiClient } from '../api/client';
import { createApiDataSource } from './apiSource';
import { fakeResponse, portMethods } from '../test/fakes';
import type { DataSource } from './source';

const target = { org: 'meridian', repo: 'monorepo' };

/** Canned answers for the three reads below; every other path is out of this suite's scope. */
const stubbedFetch: typeof fetch = async url => {
  const at = new URL(String(url)).pathname;
  if (at.endsWith('/auth/providers')) {
    return fakeResponse({ mode: 'dev', providers: [{ id: 'google', label: 'Google', login_url: '/api/v1/auth/login/google' }] });
  }
  if (at.endsWith('/me')) {
    return fakeResponse({
      user: { id: 'u1', email: 'ada@example.test', name: 'Ada' }, identities: [],
      orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian Data', role: 'owner' }],
      csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
    });
  }
  if (at.endsWith('/skills')) {
    return fakeResponse({
      items: [{
        skill_id: 'urn:skill:meridian:forge.pipelines:pipeline-testing', name: 'pipeline-testing',
        description: '[forge.pipelines] test', scope: 'forge.pipelines', owner: 'pipelines-team',
        source_layer: 'team', knowledge_layer: 'unclassified', source_status: 'active',
        publication_status: 'draft', path: 'platforms/forge/SKILL.md', content_sha256: 's',
        revision_id: 'r', package_digest: null, commit: 'c', updated_at: null,
      }],
      next_cursor: null, snapshot_id: null, schema_version: 'mgmt-1', filters: {},
    });
  }
  return fakeResponse({});
};

const create = (): DataSource => createApiDataSource({ client: new ApiClient({ baseUrl: 'https://api.test', fetchImpl: stubbedFetch, delay: async () => {} }) });

describe('DataSource port, hosted API adapter', () => {
  test('every port operation is present and callable', () => {
    const source = create();
    for (const name of portMethods) expect(typeof source[name]).toBe('function');
  });

  test('a draft round-trips in memory and notifies its subscriber', () => {
    const source = create();
    const seen: number[] = [];
    const stop = source.drafts.subscribe(() => seen.push(1));
    source.drafts.save({ proposal: { candidate: '# unsent text', digest: 'd', reason: 'r' } });
    expect(source.drafts.get().proposal?.candidate).toBe('# unsent text');
    source.drafts.clear();
    expect(source.drafts.get()).toEqual({});
    stop();
    expect(seen.length).toBeGreaterThanOrEqual(2);
  });

  test('getMe answers an identity with a membership list', async () => {
    const me = await create().getMe();
    expect(typeof me.user.id).toBe('string');
    expect(Array.isArray(me.orgs)).toBe(true);
  });

  test('getAuthProviders answers providers from the closed domain', async () => {
    const providers = await create().getAuthProviders();
    expect(providers.providers.length).toBeGreaterThan(0);
    for (const provider of providers.providers) expect(['google', 'github']).toContain(provider.id);
  });

  test('listSkills answers a page whose items carry identity, scope and path', async () => {
    const page = await create().listSkills(target, {});
    expect(Array.isArray(page.items)).toBe(true);
    expect(page.items.length).toBeGreaterThan(0);
    for (const item of page.items) {
      expect(item.skill_id).toMatch(/^urn:skill:/);
      expect(typeof item.name).toBe('string');
      expect(typeof item.scope).toBe('string');
      expect(typeof item.path).toBe('string');
    }
    expect(typeof page.filters).toBe('object');
  });
});
