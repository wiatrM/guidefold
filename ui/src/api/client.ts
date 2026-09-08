/** One fetch layer for the management API.
 *
 * Contract (docs/ui/pipeline/07-frontend.md "Granice danych", "Offline i awarie"):
 * - same-origin `/api/v1` unless VITE_GUIDEFOLD_API points elsewhere; cookies always sent;
 * - an access generation counter discards every response produced before a logout, a denial
 *   or a user/org/policy change; a per-resource request number discards a superseded response
 *   inside one generation (reversed filter or revision order);
 * - GET retries at most twice with backoff and honours Retry-After;
 * - a mutation that times out is re-read by its operation key before anything is called success;
 * - nothing is written to localStorage, sessionStorage or the HTTP cache.
 */
import { DecodeError, type Decoder } from './decoders';

export interface ApiErrorInit {
  status: number;
  code: string;
  message: string;
  requestId?: string | null;
  details?: Record<string, unknown> | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: Record<string, unknown> | null;
  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId ?? null;
    this.details = init.details ?? null;
  }
  /** 401 and 403 both mean "do not reveal this data"; 403 is also used for cross-org. */
  get denied(): boolean { return this.status === 401 || this.status === 403; }
}

/** A response the client refuses to hand back: its generation or resource turn has passed. */
export class StaleResponseError extends ApiError {
  constructor(reason: string) {
    super({ status: 0, code: 'stale_response', message: reason });
    this.name = 'StaleResponseError';
  }
}
export const isStale = (error: unknown): error is StaleResponseError => error instanceof StaleResponseError;

export interface ApiResult<T> {
  value: T;
  status: number;
  requestId: string | null;
  schemaVersion: string | null;
  orgId: string | null;
  repoId: string | null;
  snapshotId: string | null;
  noStore: boolean;
}

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
export type QueryValue = string | number | boolean | null | undefined;

export interface RequestSpec<T> {
  /** Resource path below /api/v1, for example `/orgs/meridian/members`. */
  path: string;
  method?: HttpMethod;
  query?: Record<string, QueryValue>;
  body?: unknown;
  decode: Decoder<T>;
  /** Stable identity of the thing being read or written; older answers for it are dropped. */
  resource: string;
  /** Required for every mutation; the caller supplies one stable key per draft. */
  idempotencyKey?: string;
  timeoutMs?: number;
  /** GET only, capped at 2. */
  retries?: number;
  signal?: AbortSignal;
  responseType?: 'json' | 'text';
  /** Re-read used after a mutation timeout. `null` means "the change is not there". */
  confirm?: () => Promise<T | null>;
}

export interface ApiClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  now?: () => number;
  delay?: (ms: number) => Promise<void>;
  defaultTimeoutMs?: number;
  mutationTimeoutMs?: number;
}

export type GenerationListener = (generation: number, reason: string) => void;

const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);
const MAX_GET_RETRIES = 2;
const BASE_BACKOFF_MS = 200;

/** Header value is either delta-seconds or an HTTP date. */
export function retryAfterMs(header: string | null, now: number): number | null {
  if (!header) return null;
  const seconds = Number(header.trim());
  if (Number.isFinite(seconds) && seconds >= 0) return Math.round(seconds * 1000);
  const date = Date.parse(header);
  if (Number.isNaN(date)) return null;
  return Math.max(0, date - now);
}

export function resolveBaseUrl(explicit?: string): string {
  if (typeof explicit === 'string') return explicit.replace(/\/+$/, '');
  const configured = import.meta.env?.VITE_GUIDEFOLD_API;
  return typeof configured === 'string' ? configured.replace(/\/+$/, '') : '';
}

export function buildQuery(query?: Record<string, QueryValue>): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const key of Object.keys(query).sort()) {
    const value = query[key];
    if (value === null || value === undefined || value === '') continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? '?' + text : '';
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly nowFn: () => number;
  private readonly delayFn: (ms: number) => Promise<void>;
  private readonly defaultTimeoutMs: number;
  private readonly mutationTimeoutMs: number;
  private generationValue = 1;
  /** Per-session CSRF token from the last /me. RAM only; never persisted, never logged. */
  private csrf: string | null = null;
  private readonly resourceTurn = new Map<string, number>();
  private readonly inflight = new Set<AbortController>();
  private readonly listeners = new Set<GenerationListener>();

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = resolveBaseUrl(options.baseUrl);
    this.fetchImpl = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
    this.nowFn = options.now ?? (() => Date.now());
    this.delayFn = options.delay ?? (ms => new Promise<void>(resolve => { setTimeout(resolve, ms); }));
    this.defaultTimeoutMs = options.defaultTimeoutMs ?? 15000;
    this.mutationTimeoutMs = options.mutationTimeoutMs ?? 20000;
  }

  get generation(): number { return this.generationValue; }
  get pendingRequests(): number { return this.inflight.size; }

  setCsrfToken(token: string | null): void { this.csrf = token; }
  get csrfToken(): string | null { return this.csrf; }

  onGenerationChange(listener: GenerationListener): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  /** Logout, 401/403 or a user/org/policy change. Cancels in-flight work and voids late answers. */
  bumpGeneration(reason: string): number {
    this.generationValue += 1;
    this.resourceTurn.clear();
    this.abortAll();
    for (const listener of this.listeners) listener(this.generationValue, reason);
    return this.generationValue;
  }

  abortAll(): void {
    for (const controller of this.inflight) controller.abort();
    this.inflight.clear();
  }

  url(path: string, query?: Record<string, QueryValue>): string {
    return this.baseUrl + '/api/v1' + path + buildQuery(query);
  }

  async request<T>(spec: RequestSpec<T>): Promise<ApiResult<T>> {
    const method = spec.method ?? 'GET';
    const mutation = method !== 'GET';
    const generation = this.generationValue;
    const turn = (this.resourceTurn.get(spec.resource) ?? 0) + 1;
    this.resourceTurn.set(spec.resource, turn);
    const maxRetries = mutation ? 0 : Math.min(spec.retries ?? MAX_GET_RETRIES, MAX_GET_RETRIES);
    let attempt = 0;
    for (;;) {
      let failure: unknown;
      try {
        const result = await this.send(spec, method);
        this.assertCurrent(spec.resource, turn, generation);
        return result;
      } catch (error) {
        if (isStale(error)) throw error;
        // A superseded request must not report its failure either.
        this.assertCurrent(spec.resource, turn, generation);
        failure = error;
      }
      const error = this.asApiError(failure);
      if (!mutation && attempt < maxRetries && this.retryable(error)) {
        attempt += 1;
        await this.delayFn(this.backoff(attempt, error));
        continue;
      }
      if (mutation && (error.code === 'timeout' || error.code === 'network_error')) {
        return await this.confirmMutation(spec, method, error, generation, turn);
      }
      throw error;
    }
  }

  /** GET helper that returns the decoded value only. */
  async get<T>(spec: Omit<RequestSpec<T>, 'method'>): Promise<T> {
    return (await this.request({ ...spec, method: 'GET' })).value;
  }

  private assertCurrent(resource: string, turn: number, generation: number): void {
    if (this.generationValue !== generation) throw new StaleResponseError('Access generation changed while the request was in flight.');
    if ((this.resourceTurn.get(resource) ?? 0) !== turn) throw new StaleResponseError('A newer request for ' + resource + ' has already been issued.');
  }

  private retryable(error: ApiError): boolean {
    return error.code === 'network_error' || error.code === 'timeout' || RETRYABLE_STATUS.has(error.status);
  }

  private backoff(attempt: number, error: ApiError): number {
    const advised = error.details && typeof error.details.retry_after_ms === 'number' ? error.details.retry_after_ms as number : null;
    if (advised !== null) return advised;
    return BASE_BACKOFF_MS * Math.pow(2, attempt - 1);
  }

  private asApiError(error: unknown): ApiError {
    if (error instanceof ApiError) return error;
    if (error instanceof DecodeError) {
      return new ApiError({ status: 0, code: 'invalid_response', message: 'The response did not match the contract: ' + error.message, details: { path: error.path } });
    }
    const message = error instanceof Error ? error.message : String(error);
    return new ApiError({ status: 0, code: 'network_error', message });
  }

  private async confirmMutation<T>(spec: RequestSpec<T>, method: HttpMethod, cause: ApiError, generation: number, turn: number): Promise<ApiResult<T>> {
    try {
      if (spec.confirm) {
        const value = await spec.confirm();
        this.assertCurrent(spec.resource, turn, generation);
        if (value !== null) {
          return { value, status: 200, requestId: null, schemaVersion: null, orgId: null, repoId: null, snapshotId: null, noStore: true };
        }
      } else {
        // The same Idempotency-Key replays the operation instead of repeating it.
        const replay = await this.send(spec, method);
        this.assertCurrent(spec.resource, turn, generation);
        return replay;
      }
    } catch (error) {
      if (isStale(error)) throw error;
    }
    throw new ApiError({
      status: cause.status,
      code: 'unconfirmed',
      message: 'The change was not confirmed. Re-read this resource before assuming it applied.',
      requestId: cause.requestId,
      details: { cause: cause.code },
    });
  }

  private async send<T>(spec: RequestSpec<T>, method: HttpMethod): Promise<ApiResult<T>> {
    const mutation = method !== 'GET';
    if (mutation && !spec.idempotencyKey) {
      throw new ApiError({ status: 0, code: 'idempotency_key_required', message: 'A mutation needs a stable Idempotency-Key.' });
    }
    // Contract §3: a session mutation carries `X-CSRF-Token`. Sending it without one is not a
    // weaker request, it is a request the service refuses with an undiagnosable 403, so the
    // client refuses it here and says which token is missing. Nothing was sent.
    if (mutation && !this.csrf) {
      throw new ApiError({
        status: 0, code: 'csrf_token_missing',
        message: 'This session has no CSRF token, so nothing was sent. Re-read /api/v1/me and retry.',
      });
    }
    const controller = new AbortController();
    this.inflight.add(controller);
    let timedOut = false;
    const timeoutMs = spec.timeoutMs ?? (mutation ? this.mutationTimeoutMs : this.defaultTimeoutMs);
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const forward = () => controller.abort();
    spec.signal?.addEventListener('abort', forward);
    try {
      const headers: Record<string, string> = {
        Accept: spec.responseType === 'text' ? 'application/octet-stream, text/plain' : 'application/json',
        'Cache-Control': 'no-store',
      };
      if (spec.body !== undefined) headers['Content-Type'] = 'application/json';
      if (mutation) {
        headers['Idempotency-Key'] = spec.idempotencyKey as string;
        headers['X-CSRF-Token'] = this.csrf as string;
      }
      const response = await this.fetchImpl(this.url(spec.path, spec.query), {
        method,
        headers,
        credentials: 'include',
        cache: 'no-store',
        signal: controller.signal,
        body: spec.body === undefined ? undefined : JSON.stringify(spec.body),
      });
      return await this.readResponse(spec, response);
    } catch (error) {
      if (timedOut) throw new ApiError({ status: 0, code: 'timeout', message: 'The request did not complete within ' + timeoutMs + ' ms.' });
      if (spec.signal?.aborted) throw new ApiError({ status: 0, code: 'aborted', message: 'The request was cancelled.' });
      if (controller.signal.aborted) throw new StaleResponseError('The request was cancelled by an access generation change.');
      throw error;
    } finally {
      clearTimeout(timer);
      this.inflight.delete(controller);
      spec.signal?.removeEventListener('abort', forward);
    }
  }

  private async readResponse<T>(spec: RequestSpec<T>, response: Response): Promise<ApiResult<T>> {
    const requestId = response.headers?.get?.('X-Request-Id') ?? null;
    const text = response.status === 204 ? '' : await response.text();
    let payload: unknown = undefined;
    if (spec.responseType === 'text') payload = text;
    else if (text.length) {
      try { payload = JSON.parse(text); }
      catch { payload = undefined; }
    }
    if (!response.ok) throw this.errorFrom(response, payload, requestId, text);
    const envelope = payload !== null && typeof payload === 'object' && !Array.isArray(payload) ? payload as Record<string, unknown> : null;
    const readString = (key: string) => envelope && typeof envelope[key] === 'string' ? envelope[key] as string : null;
    return {
      value: spec.decode(payload, ''),
      status: response.status,
      requestId: requestId ?? readString('request_id'),
      schemaVersion: readString('schema_version'),
      orgId: readString('org_id'),
      repoId: readString('repo_id'),
      snapshotId: readString('snapshot_id'),
      noStore: /no-store/i.test(response.headers?.get?.('Cache-Control') ?? ''),
    };
  }

  private errorFrom(response: Response, payload: unknown, requestId: string | null, text: string): ApiError {
    const body = payload !== null && typeof payload === 'object' && !Array.isArray(payload) ? payload as Record<string, unknown> : null;
    const details: Record<string, unknown> = body && typeof body.details === 'object' && body.details !== null ? { ...body.details as Record<string, unknown> } : {};
    const advised = retryAfterMs(response.headers?.get?.('Retry-After') ?? null, this.nowFn());
    if (advised !== null) details.retry_after_ms = advised;
    return new ApiError({
      status: response.status,
      code: body && typeof body.error === 'string' ? body.error : 'http_' + response.status,
      message: body && typeof body.message === 'string' ? body.message : (text || 'Request failed with status ' + response.status),
      requestId: requestId ?? (body && typeof body.request_id === 'string' ? body.request_id : null),
      details: Object.keys(details).length ? details : null,
    });
  }
}
