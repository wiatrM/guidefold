/**
 * One behavioural suite for both sides of the DataSource port.
 *
 * `hexagonal-architecture` ("Testuj po obu stronach portu") asks that the port, not each adapter,
 * carries the promise the routes rely on. Everything asserted here is what a route may assume
 * whichever adapter it was given: the operations exist, unsent drafts round-trip in RAM, and the
 * three reads every composition starts with answer in the shape the decoders declare.
 *
 * It is a smoke suite over the port, not a second copy of each adapter's own tests.
 */
import { afterEach, describe, expect, test } from 'vitest';
import { ApiClient } from '../api/client';
import { createApiDataSource } from './apiSource';
import { createFixtureDataSource } from './fixtureSource';
import { meridian } from './meridian';
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

const adapters: [string, () => DataSource][] = [
  ['fixture', () => createFixtureDataSource(meridian)],
  ['api', () => createApiDataSource({ client: new ApiClient({ baseUrl: 'https://api.test', fetchImpl: stubbedFetch, delay: async () => {} }) })],
];

afterEach(() => { sessionStorage.clear(); });

describe.each(adapters)('DataSource port, %s adapter', (_name, create) => {
  test('every port operation is present and callable', () => {
    const source = create();
    for (const name of portMethods) expect(typeof source[name]).toBe('function');
    expect(['fixture', 'api']).toContain(source.mode);
  });

  test('a draft round-trips in memory and notifies its subscriber', () => {
    const source = create();
    const seen: number[] = [];
    const stop = source.drafts.subscribe(() => seen.push(1));
    source.drafts.save({ proposal: { stage: 'editing', candidate: '# unsent text', digest: 'd', reason: 'r' } });
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
