import { describe, expect, test, vi } from 'vitest';
import { ApiClient, StaleResponseError } from '../api/client';
import { createApiDataSource, createApiRuntime, createMemoryDraftStore } from './apiSource';
import { abortable, deferred, fakeResponse } from '../test/fakes';

const members = (email: string) => [{ user_id: 'u1', email, name: null, role: 'owner', joined_at: null }];
const page = (name: string) => ({
  items: [{
    skill_id: 'urn:skill:meridian:a:' + name, name, description: '', scope: 'a', owner: 'o',
    source_layer: 'team', knowledge_layer: 'task', source_status: 'active', publication_status: 'draft',
    path: 'p/SKILL.md', content_sha256: 's', revision_id: 'r', package_digest: null, commit: 'c', updated_at: null,
  }],
  next_cursor: null, snapshot_id: null, schema_version: 'mgmt-1', filters: {},
});

function harness(fetchImpl: typeof fetch) {
  const client = new ApiClient({ baseUrl: 'https://api.test', fetchImpl, delay: async () => {} });
  // Every session mutation carries the token from the last /me; without it the client refuses to send.
  client.setCsrfToken('csrf-1');
  const drafts = createMemoryDraftStore();
  const onDenied = vi.fn();
  const source = createApiDataSource({ client, drafts, onDenied });
  return { client, drafts, source, onDenied };
}

describe('organisation boundary', () => {
  test('an answer from org A after switching to org B is discarded', async () => {
    const gate = deferred<Response>();
    const { source } = harness(async (_url, init) => abortable(gate.promise, init as RequestInit));
    source.setContext({ user: 'u1', org: 'org-a', repo: 'monorepo' });
    const pending = source.listMembers('org-a');
    source.setContext({ org: 'org-b' });
    gate.resolve(fakeResponse(members('ada@org-a.example')));
    await expect(pending).rejects.toBeInstanceOf(StaleResponseError);
  });

  test('there is no response cache: two identical reads issue two requests', async () => {
    let body = members('ada@org-a.example');
    const calls: string[] = [];
    const { source } = harness(async url => { calls.push(String(url)); return fakeResponse(body); });
    source.setContext({ user: 'u1', org: 'org-a' });
    expect((await source.listMembers('org-a'))[0].email).toBe('ada@org-a.example');
    // The service answers `Cache-Control: no-store` (§3), so a second read has to be a second request.
    body = members('ada.renamed@org-a.example');
    expect((await source.listMembers('org-a'))[0].email).toBe('ada.renamed@org-a.example');
    expect(calls).toHaveLength(2);
  });

  test('reading the same resource under another organisation never reuses the first answer', async () => {
    const bodies: Record<string, ReturnType<typeof members>> = {
      'org-a': members('ada@org-a.example'), 'org-b': members('bob@org-b.example'),
    };
    const { source } = harness(async url => fakeResponse(bodies[String(url).includes('org-b') ? 'org-b' : 'org-a']));
    source.setContext({ user: 'u1', org: 'org-a' });
    expect((await source.listMembers('org-a'))[0].email).toBe('ada@org-a.example');
    source.setContext({ org: 'org-b' });
    expect((await source.listMembers('org-b'))[0].email).toBe('bob@org-b.example');
  });
});

describe('snapshot activation', () => {
  const row = (over: Record<string, unknown> = {}) => ({
    publication_id: 'pub-1', snapshot_id: 'snap-1', state: 'active', active: true,
    import_id: 'im-1', job_id: 'j-1', commit: 'c0ffee', n_skills: 26, builder_sha256: 'sha-b',
    validation: { ok: true, findings: [] }, error: null,
    activated_at: null, created_at: '2026-09-06T09:00:00Z', ...over,
  });

  test('the rollback reason reaches the request body and the {snapshot} envelope is decoded', async () => {
    const bodies: string[] = [];
    const { source } = harness(async (_url, init) => {
      bodies.push(String((init as RequestInit).body));
      return fakeResponse({ schema_version: 'mgmt-1', org_id: 'o1', repo_id: 'monorepo', snapshot: row() });
    });
    const activated = await source.activateSnapshot(
      { org: 'org-a', repo: 'monorepo' }, 'snap-1', 'the new snapshot dropped the identity scope', 'activate:1',
    );
    expect(JSON.parse(bodies[0])).toEqual({ idempotency_key: 'activate:1', reason: 'the new snapshot dropped the identity scope' });
    expect(activated.snapshot_id).toBe('snap-1');
    expect(activated.active).toBe(true);
  });

  test('a building publication does not break the snapshot list', async () => {
    const { source } = harness(async () => fakeResponse({
      items: [row(), row({ publication_id: 'pub-2', snapshot_id: null, state: 'building', active: false, validation: null })],
      next_cursor: null,
    }));
    const rows = await source.listSnapshots({ org: 'org-a', repo: 'monorepo' });
    expect(rows.map(entry => entry.snapshot_id)).toEqual(['snap-1', null]);
  });
});

describe('reversed order inside one organisation', () => {
  test('filters A then B: the late A answer is dropped, never rendered over B', async () => {
    const gates = new Map<string, ReturnType<typeof deferred<Response>>>();
    const { source } = harness(async (url, init) => {
      const scope = new URL(String(url)).searchParams.get('scope') as string;
      const gate = deferred<Response>();
      gates.set(scope, gate);
      return abortable(gate.promise, init as RequestInit);
    });
    source.setContext({ user: 'u1', org: 'org-a', repo: 'monorepo' });
    const target = { org: 'org-a', repo: 'monorepo' };
    const first = source.listSkills(target, { scope: 'alpha' });
    const second = source.listSkills(target, { scope: 'beta' });
    gates.get('beta')!.resolve(fakeResponse(page('beta-skill')));
    expect((await second).items[0].name).toBe('beta-skill');
    gates.get('alpha')!.resolve(fakeResponse(page('alpha-skill')));
    await expect(first).rejects.toBeInstanceOf(StaleResponseError);
  });

  test('revision A then B for one skill: the late A revision is dropped', async () => {
    const gates = new Map<string, ReturnType<typeof deferred<Response>>>();
    const { source } = harness(async (url, init) => {
      const revision = String(url).split('/revisions/')[1];
      const gate = deferred<Response>();
      gates.set(revision, gate);
      return abortable(gate.promise, init as RequestInit);
    });
    const target = { org: 'org-a', repo: 'monorepo' };
    const body = (id: string) => ({
      revision_id: id, content_sha256: id, body: '# ' + id, frontmatter: null,
      source: null, references: [], requires: [], refines: [], relations: [], feedback: [],
      provenance: null, publication_status: 'published',
    });
    const first = source.getRevision(target, 's1', 'r1');
    const second = source.getRevision(target, 's1', 'r2');
    gates.get('r2')!.resolve(fakeResponse(body('r2')));
    expect((await second).revision_id).toBe('r2');
    gates.get('r1')!.resolve(fakeResponse(body('r1')));
    await expect(first).rejects.toBeInstanceOf(StaleResponseError);
  });
});

describe('revocation', () => {
  test('401 clears the drafts and cancels in-flight requests', async () => {
    let status = 200;
    const { source, drafts, client, onDenied } = harness(async () => status === 200
      ? fakeResponse(members('ada@org-a.example'))
      : fakeResponse({ error: 'unauthenticated', message: 'no session' }, { status }));
    source.setContext({ user: 'u1', org: 'org-a' });
    await source.listMembers('org-a');
    drafts.save({ proposal: { candidate: '# unsent text', digest: 'd', reason: 'r' } });
    const generation = client.generation;
    status = 401;
    await expect(source.listOrgs()).rejects.toMatchObject({ status: 401 });
    expect(onDenied).toHaveBeenCalledTimes(1);
    source.revoke('access_denied');
    expect(drafts.get()).toEqual({});
    expect(client.generation).toBeGreaterThan(generation);
    expect(client.csrfToken).toBeNull();
  });

  test('the runtime wires a denial to the access controller and back to a revoke', async () => {
    const client = new ApiClient({ baseUrl: 'https://api.test', fetchImpl: async () => fakeResponse({ error: 'forbidden', message: 'no' }, { status: 403 }), delay: async () => {} });
    client.setCsrfToken('csrf-1');
    const { source, access } = createApiRuntime({ client });
    const drafts = source.drafts;
    drafts.save({ proposal: { candidate: '# unsent text', digest: 'd', reason: 'r' } });
    await expect(source.listOrgs()).rejects.toMatchObject({ status: 403 });
    expect(access.getSnapshot().status).toBe('denied');
    expect(drafts.get()).toEqual({});
    expect(client.csrfToken).toBeNull();
  });
});

describe('idempotency and confirmation through the source', () => {
  test('repository access and reviewer operations use scoped paths and idempotency', async () => {
    const seen: { method: string; url: string; body: string | undefined; key: string | undefined }[] = [];
    const { source } = harness(async (url, init) => {
      const request = init as RequestInit;
      seen.push({ method: request.method ?? 'GET', url: String(url), body: request.body as string | undefined, key: (request.headers as Record<string, string>)['Idempotency-Key'] });
      if ((request.method ?? 'GET') === 'GET' && String(url).endsWith('/access')) return fakeResponse({ items: [{ user_id: 'u2', email: 'dev@example.com', name: 'Dev', access: 'read', created_at: null }] });
      if ((request.method ?? 'GET') === 'GET') return fakeResponse({ items: [{ user_id: 'u2', email: 'dev@example.com', name: 'Dev', assigned_at: null }] });
      if ((request.method ?? 'GET') === 'PUT' && String(url).includes('/access/')) return fakeResponse({ user_id: 'u2', email: 'dev@example.com', name: 'Dev', access: 'write', created_at: null });
      return fakeResponse({ ok: true });
    });
    const target = { org: 'acme', repo: 'payments' };
    expect((await source.listRepoAccess(target))[0].access).toBe('read');
    expect((await source.setRepoAccess(target, 'u2', 'write', 'access:1')).access).toBe('write');
    await source.removeRepoAccess(target, 'u2', 'access:2');
    expect((await source.listReviewers(target))[0].user_id).toBe('u2');
    await source.assignReviewer(target, 'u2', 'reviewer:1');
    await source.removeReviewer(target, 'u2', 'reviewer:2');
    expect(seen.map(item => item.method + ' ' + new URL(item.url).pathname)).toEqual([
      'GET /api/v1/orgs/acme/repos/payments/access',
      'PUT /api/v1/orgs/acme/repos/payments/access/u2',
      'DELETE /api/v1/orgs/acme/repos/payments/access/u2',
      'GET /api/v1/orgs/acme/repos/payments/reviewers',
      'PUT /api/v1/orgs/acme/repos/payments/reviewers/u2',
      'DELETE /api/v1/orgs/acme/repos/payments/reviewers/u2',
    ]);
    expect(seen[1].key).toBe('access:1');
    expect(JSON.parse(seen[1].body ?? '{}')).toEqual({ access: 'write' });
  });

  test('local package blob upload uses raw bytes and the finalizer decodes status', async () => {
    const seen: { body: unknown; contentType: string | undefined }[] = [];
    const { source } = harness(async (_url, init) => {
      seen.push({ body: (init as RequestInit).body, contentType: ((init as RequestInit).headers as Record<string, string>)['Content-Type'] });
      return fakeResponse({ import_id: 'i1', state: 'queued', manifest_digest: null, commit: null, complete: true, publish: true, counts: null, files: [], files_truncated: false, jobs: [], publication: null, error: null, reused_import_id: null, created_at: null, updated_at: null, finalized_at: null });
    });
    await source.uploadImportBlob({ org: 'org-a', repo: 'monorepo' }, 'i1', 'a'.repeat(64), new Uint8Array([1, 2, 3]));
    await source.finalizeImport({ org: 'org-a', repo: 'monorepo' }, 'i1', 'finalize:i1');
    expect(seen[0].contentType).toBe('application/octet-stream');
    expect(seen[0].body).toBeInstanceOf(Uint8Array);
    expect(seen[1].contentType).toBe('application/json');
  });

  test('creating an organisation reuses one key across the replay', async () => {
    const keys: (string | undefined)[] = [];
    let attempt = 0;
    const { source } = harness(async (_url, init) => {
      keys.push(((init as RequestInit).headers as Record<string, string>)['Idempotency-Key']);
      attempt += 1;
      if (attempt === 1) throw new TypeError('connection reset');
      return fakeResponse({ org_id: 'o1', slug: 'meridian', name: 'Meridian', my_role: 'owner' });
    });
    const created = await source.createOrg({ name: 'Meridian', slug: 'meridian' }, 'create-org:meridian');
    expect(created.slug).toBe('meridian');
    expect(keys).toEqual(['create-org:meridian', 'create-org:meridian']);
  });

  test('a repository create that times out is confirmed by re-reading the list, not assumed', async () => {
    const calls: string[] = [];
    const { source } = harness(async (url, init) => {
      const method = (init as RequestInit).method ?? 'GET';
      calls.push(method + ' ' + String(url));
      if (method === 'POST') throw new TypeError('connection reset');
      return fakeResponse([{ repo_id: 'monorepo', name: null, git_host_url: null, created_at: null }]);
    });
    const created = await source.createRepo('org-a', { repo_id: 'monorepo' }, 'create-repo:org-a:monorepo');
    expect(created.repo_id).toBe('monorepo');
    expect(calls.some(call => call.startsWith('GET') && call.includes('/repos'))).toBe(true);
  });

  test('a repository create whose re-read finds nothing is reported unconfirmed', async () => {
    const { source } = harness(async (_url, init) => {
      if (((init as RequestInit).method ?? 'GET') === 'POST') throw new TypeError('connection reset');
      return fakeResponse([]);
    });
    await expect(source.createRepo('org-a', { repo_id: 'monorepo' }, 'create-repo:org-a:monorepo'))
      .rejects.toMatchObject({ code: 'unconfirmed' });
  });

  test('a 409 on a decision keeps the unsent draft text intact', async () => {
    const { source, drafts } = harness(async () => fakeResponse({
      error: 'stale_revision', message: 'The source moved on.', details: { current_revision: 'rev-2' },
    }, { status: 409 }));
    drafts.save({ proposal: { candidate: '# text the operator typed', digest: 'rev-1', reason: 'because' } });
    await expect(source.decideProposal({ org: 'org-a', repo: 'monorepo' }, 'p1', { decision: 'approve', reason: 'r', expected_revision: 'rev-1' }, 'decide:p1'))
      .rejects.toMatchObject({ code: 'stale_revision', details: { current_revision: 'rev-2' } });
    expect(drafts.get().proposal?.candidate).toBe('# text the operator typed');
  });

  test('drafts in API mode never reach browser storage', () => {
    const { drafts } = harness(async () => fakeResponse({}));
    drafts.save({ proposal: { candidate: '# private', digest: 'd', reason: '' } });
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
  });
});
