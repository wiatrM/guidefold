import { describe, expect, test, vi } from 'vitest';
import { ApiClient, ApiError, StaleResponseError, buildQuery, isStale, retryAfterMs } from './client';
import * as d from './decoders';
import { abortable, deferred, fakeResponse } from '../test/fakes';

const failureOf = async (promise: Promise<unknown>): Promise<ApiError> => {
  try { await promise; } catch (error) { return error as ApiError; }
  throw new Error('The request was expected to fail.');
};

const payload = d.object<{ value: string }>({ value: d.str });
const client = (fetchImpl: typeof fetch, options = {}) =>
  new ApiClient({ baseUrl: 'https://api.test', fetchImpl, delay: async () => {}, ...options });

describe('URL and header contract', () => {
  test('query is sorted and empty values are dropped', () => {
    expect(buildQuery({ b: 2, a: 'x', c: null, d: '' })).toBe('?a=x&b=2');
    expect(buildQuery()).toBe('');
  });

  test('every request is same-site, credentialed and outside the HTTP cache', async () => {
    const calls: RequestInit[] = [];
    const api = client(async (_url, init) => { calls.push(init as RequestInit); return fakeResponse({ value: 'ok' }); });
    await api.request({ path: '/me', decode: payload, resource: 'me' });
    expect(calls[0].credentials).toBe('include');
    expect(calls[0].cache).toBe('no-store');
    expect((calls[0].headers as Record<string, string>)['Cache-Control']).toBe('no-store');
  });

  test('a mutation carries the caller Idempotency-Key and the CSRF token from the last /me', async () => {
    const calls: Record<string, string>[] = [];
    const api = client(async (_url, init) => { calls.push((init as RequestInit).headers as Record<string, string>); return fakeResponse({ value: 'ok' }); });
    api.setCsrfToken('csrf-1');
    await api.request({ path: '/orgs', method: 'POST', body: { slug: 'x' }, decode: payload, resource: 'orgs', idempotencyKey: 'create-org:x' });
    expect(calls[0]['Idempotency-Key']).toBe('create-org:x');
    expect(calls[0]['X-CSRF-Token']).toBe('csrf-1');
  });

  test('a mutation without an idempotency key is refused before it is sent', async () => {
    const fetchImpl = vi.fn(async () => fakeResponse({ value: 'ok' }));
    const api = client(fetchImpl as unknown as typeof fetch);
    api.setCsrfToken('csrf-1');
    await expect(api.request({ path: '/orgs', method: 'POST', decode: payload, resource: 'orgs' }))
      .rejects.toMatchObject({ code: 'idempotency_key_required' });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test('a mutation without a CSRF token is refused before it is sent, not sent unprotected', async () => {
    const fetchImpl = vi.fn(async () => fakeResponse({ value: 'ok' }));
    const api = client(fetchImpl as unknown as typeof fetch);
    await expect(api.request({ path: '/orgs', method: 'POST', body: {}, decode: payload, resource: 'orgs', idempotencyKey: 'create-org:x' }))
      .rejects.toMatchObject({ code: 'csrf_token_missing' });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test('a read needs no CSRF token', async () => {
    const api = client(async () => fakeResponse({ value: 'ok' }));
    expect((await api.request({ path: '/me', decode: payload, resource: 'me' })).value.value).toBe('ok');
  });
});

describe('generation and per-resource ordering', () => {
  test('a response that arrives after a generation bump is discarded', async () => {
    const gate = deferred<Response>();
    const api = client(async (_url, init) => abortable(gate.promise, init as RequestInit));
    const pending = api.request({ path: '/orgs/a/members', decode: payload, resource: 'members/a' });
    api.bumpGeneration('logout');
    gate.resolve(fakeResponse({ value: 'members of a' }));
    await expect(pending).rejects.toBeInstanceOf(StaleResponseError);
  });

  test('filters A then B: B resolves first and the late A is ignored', async () => {
    const gates = new Map<string, ReturnType<typeof deferred<Response>>>();
    const api = client(async (url, init) => {
      const filter = new URL(String(url)).searchParams.get('scope') as string;
      const gate = deferred<Response>();
      gates.set(filter, gate);
      return abortable(gate.promise, init as RequestInit);
    });
    const first = api.request({ path: '/skills', query: { scope: 'a' }, decode: payload, resource: 'skills' });
    const second = api.request({ path: '/skills', query: { scope: 'b' }, decode: payload, resource: 'skills' });
    gates.get('b')!.resolve(fakeResponse({ value: 'b' }));
    expect((await second).value.value).toBe('b');
    gates.get('a')!.resolve(fakeResponse({ value: 'a' }));
    await expect(first).rejects.toBeInstanceOf(StaleResponseError);
  });

  test('a superseded request does not report its own failure either', async () => {
    const gates: ReturnType<typeof deferred<Response>>[] = [];
    const api = client(async (_url, init) => { const gate = deferred<Response>(); gates.push(gate); return abortable(gate.promise, init as RequestInit); });
    const first = api.request({ path: '/skills', decode: payload, resource: 'skills', retries: 0 });
    const second = api.request({ path: '/skills', decode: payload, resource: 'skills', retries: 0 });
    gates[1].resolve(fakeResponse({ value: 'current' }));
    await second;
    gates[0].reject(new TypeError('network down'));
    await expect(first).rejects.toBeInstanceOf(StaleResponseError);
  });

  test('different resources do not supersede each other', async () => {
    const api = client(async url => fakeResponse({ value: String(url) }));
    const [a, b] = await Promise.all([
      api.request({ path: '/skills', decode: payload, resource: 'skills' }),
      api.request({ path: '/me', decode: payload, resource: 'me' }),
    ]);
    expect(a.value.value).toContain('/skills');
    expect(b.value.value).toContain('/me');
  });
});

describe('retry, timeout and confirmation', () => {
  test('Retry-After in seconds drives the backoff of a GET, capped at two retries', async () => {
    const waits: number[] = [];
    let attempt = 0;
    const api = client(async () => {
      attempt += 1;
      return attempt < 3 ? fakeResponse({ error: 'unavailable' }, { status: 503, headers: { 'Retry-After': '2' } }) : fakeResponse({ value: 'late' });
    }, { delay: async (ms: number) => { waits.push(ms); } });
    const result = await api.request({ path: '/skills', decode: payload, resource: 'skills' });
    expect(result.value.value).toBe('late');
    expect(waits).toEqual([2000, 2000]);
  });

  test('a GET gives up after two retries and reports the last status', async () => {
    let attempt = 0;
    const api = client(async () => { attempt += 1; return fakeResponse({ error: 'unavailable' }, { status: 503 }); });
    await expect(api.request({ path: '/skills', decode: payload, resource: 'skills' })).rejects.toMatchObject({ status: 503 });
    expect(attempt).toBe(3);
  });

  test('a mutation is never retried blindly: it is replayed with the same key and confirmed', async () => {
    const keys: string[] = [];
    let attempt = 0;
    const api = client(async (_url, init) => {
      keys.push(((init as RequestInit).headers as Record<string, string>)['Idempotency-Key']);
      attempt += 1;
      if (attempt === 1) throw new TypeError('connection reset');
      return fakeResponse({ value: 'created once' });
    });
    api.setCsrfToken('csrf-1');
    const result = await api.request({ path: '/orgs', method: 'POST', body: {}, decode: payload, resource: 'orgs', idempotencyKey: 'create-org:x' });
    expect(result.value.value).toBe('created once');
    expect(keys).toEqual(['create-org:x', 'create-org:x']);
  });

  test('a mutation whose re-read finds nothing is reported as unconfirmed, never as success', async () => {
    const api = client(async () => { throw new TypeError('connection reset'); });
    api.setCsrfToken('csrf-1');
    await expect(api.request({
      path: '/orgs', method: 'POST', body: {}, decode: payload, resource: 'orgs',
      idempotencyKey: 'create-org:x', confirm: async () => null,
    })).rejects.toMatchObject({ code: 'unconfirmed' });
  });

  test('a mutation confirmed by a re-read after a timeout succeeds', async () => {
    const gate = deferred<Response>();
    const api = client(async (_url, init) => abortable(gate.promise, init as RequestInit));
    api.setCsrfToken('csrf-1');
    const result = await api.request({
      path: '/orgs', method: 'POST', body: {}, decode: payload, resource: 'orgs',
      idempotencyKey: 'create-org:x', timeoutMs: 1, confirm: async () => ({ value: 'found by re-read' }),
    });
    expect(result.value.value).toBe('found by re-read');
    gate.resolve(fakeResponse({ value: 'late' }));
  });

  test('Retry-After accepts an HTTP date', () => {
    const now = Date.parse('2026-09-06T10:00:00Z');
    expect(retryAfterMs('Sun, 06 Sep 2026 10:00:03 GMT', now)).toBe(3000);
    expect(retryAfterMs(null, now)).toBeNull();
  });
});

describe('error envelope', () => {
  test('409 stale_revision surfaces the current revision in details', async () => {
    const api = client(async () => fakeResponse({
      error: 'stale_revision', message: 'The source moved on.', request_id: 'req-9',
      details: { current_revision: 'rev-2', expected_revision: 'rev-1' },
    }, { status: 409, headers: { 'X-Request-Id': 'req-9' } }));
    api.setCsrfToken('csrf-1');
    const failure = await failureOf(api.request({ path: '/proposals/p1/decision', method: 'POST', body: {}, decode: payload, resource: 'proposal/p1', idempotencyKey: 'decide:p1' }));
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.code).toBe('stale_revision');
    expect(failure.status).toBe(409);
    expect(failure.requestId).toBe('req-9');
    expect(failure.details?.current_revision).toBe('rev-2');
  });

  test('401 and 403 are marked as denials', async () => {
    for (const status of [401, 403]) {
      const api = client(async () => fakeResponse({ error: 'forbidden', message: 'no' }, { status }));
      const failure = await failureOf(api.request({ path: '/orgs/x/members', decode: payload, resource: 'm', retries: 0 }));
      expect(failure.denied).toBe(true);
    }
  });

  test('a body that does not match the contract becomes invalid_response, not a crash', async () => {
    const api = client(async () => fakeResponse({ value: 42 }));
    const failure = await failureOf(api.request({ path: '/me', decode: payload, resource: 'me' }));
    expect(failure.code).toBe('invalid_response');
    expect(failure.details?.path).toBe('value');
    expect(isStale(failure)).toBe(false);
  });
});
