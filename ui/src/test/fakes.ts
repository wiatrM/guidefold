/** Test doubles for the API boundary. No production module imports this file. */
import { ApiError } from '../api/client';
import type { DataSource } from '../data/source';
import type { Session } from '../domain';

export interface FakeResponseInit { status?: number; headers?: Record<string, string> }

/** Minimal Response shape the client reads: ok, status, headers.get, text(). */
export function fakeResponse(body: unknown, init: FakeResponseInit = {}): Response {
  const status = init.status ?? 200;
  const headers = new Map(Object.entries(init.headers ?? {}).map(([key, value]) => [key.toLowerCase(), value]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => headers.get(name.toLowerCase()) ?? null },
    text: async () => typeof body === 'string' ? body : JSON.stringify(body),
  } as unknown as Response;
}

export interface Deferred<T> { promise: Promise<T>; resolve: (value: T) => void; reject: (error: unknown) => void }
export function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

/** Rejects as soon as the caller's AbortController fires, like a real fetch. */
export function abortable<T>(promise: Promise<T>, init?: RequestInit): Promise<T> {
  const signal = init?.signal;
  if (!signal) return promise;
  return new Promise<T>((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return; }
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    promise.then(resolve, reject);
  });
}

const missing = (name: string) => async (): Promise<never> => {
  throw new ApiError({ status: 501, code: 'not_stubbed', message: name + ' is not stubbed in this test.' });
};

/** Every port operation, without the draft store and the two optional context hooks. */
type PortMethods = Omit<DataSource, 'drafts' | 'setContext' | 'revoke'>;

/**
 * The port's operation names. `satisfies` rejects a name that is not on the port and the
 * `Unlisted` alias below rejects a port method that is missing here, so adding an operation
 * to `DataSource` without stubbing it is a type error rather than a test that silently
 * hands routes an `undefined`.
 */
export const portMethods = [
  'getAuthProviders', 'startLogin', 'getMe', 'logout', 'startDeviceAuthorization', 'decideDevice', 'startIdentityLink',
  'listOrgs', 'getOrg', 'createOrg', 'listMembers', 'inviteMember', 'changeMemberRole', 'removeMember',
  'listInstallations', 'createInstallation', 'revokeInstallation', 'getAudit',
  'listRepos', 'createRepo', 'listImports', 'createImport', 'getImport', 'cancelImport', 'getImportPlan', 'generateProposals',
  'listSkills', 'getFacets', 'lookupFacet', 'getSkill', 'getRevision', 'getRevisionRaw', 'sendFeedback',
  'getMapRepository', 'getMapScopes', 'getMapLayers', 'getRelations', 'getModule',
  'listProposals', 'getProposal', 'decideProposal', 'exportProposal', 'getProposalPublication',
  'listSnapshots', 'activateSnapshot', 'publish',
  'getUsage', 'exportUsage', 'decideQueueItem',
] as const satisfies readonly (keyof PortMethods)[];

type Unlisted = Exclude<keyof PortMethods, typeof portMethods[number]>;
/** Reads as `true` only while the list above covers every port method. */
const everyPortMethodIsListed: Unlisted extends never ? true : never = true;
void everyPortMethodIsListed;

/** A DataSource whose every method rejects until the test overrides it. */
export function fakeSource(overrides: Partial<DataSource> = {}): DataSource {
  let drafts: Session = {};
  const listeners = new Set<() => void>();
  const base = {
    drafts: {
      get: () => drafts,
      subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
      save: (patch: Partial<Session>) => { drafts = { ...drafts, ...patch }; listeners.forEach(listener => listener()); },
      clear: () => { drafts = {}; listeners.forEach(listener => listener()); },
    },
  };
  const stubs = Object.fromEntries(portMethods.map(name => [name, missing(name)])) as unknown as PortMethods;
  return { ...base, ...stubs, ...overrides };
}
