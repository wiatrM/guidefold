/** Access confirmation for private views (07-frontend "Odwołanie dostępu").
 *
 * `/me` is re-read at most every 25 s with a 5 s timeout while a private view is visible.
 * Data older than 45 s counted from the request start is masked until a check succeeds again,
 * a hidden tab must be reconfirmed before anything is revealed, and 401/403 clears the cache and
 * drafts, cancels in-flight requests and bumps the access generation. A network failure without a
 * denial keeps the session but never reveals unconfirmed data.
 */
import { createContext, createElement, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react';
import { ApiError } from './client';
import type { Me } from './decoders';

export const ACCESS_TTL_MS = 45000;
export const ACCESS_REFRESH_MS = 25000;
export const ACCESS_TIMEOUT_MS = 5000;

export type AccessStatus = 'confirmed' | 'stale' | 'checking' | 'denied' | 'offline';

export interface AccessState {
  status: AccessStatus;
  me: Me | null;
  checkedAt: number | null;
}

/** Only 'confirmed' may reveal private data; every other status masks the view. */
export const revealsData = (status: AccessStatus): boolean => status === 'confirmed';

export interface AccessDeps {
  /** Reads /me. Must reject with ApiError 401/403 on a denial. */
  fetchMe: (timeoutMs: number) => Promise<Me>;
  /** Clear cache and drafts, cancel in-flight requests, bump the generation. */
  onDenied: () => void;
  /** Called after every successful confirmation, with the fresh identity. */
  onConfirmed?: (me: Me) => void;
  now?: () => number;
}

export class AccessController {
  private readonly deps: AccessDeps;
  private readonly nowFn: () => number;
  private listeners = new Set<() => void>();
  private state: AccessState = { status: 'checking', me: null, checkedAt: null };
  private me: Me | null = null;
  private checkedAt: number | null = null;
  private lastAttemptAt: number | null = null;
  private lastFailureAt: number | null = null;
  private denied = false;
  private checking = false;
  private mustReconfirm = false;
  private visible = true;
  private pending: Promise<AccessState> | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private detach: (() => void) | null = null;

  constructor(deps: AccessDeps) {
    this.deps = deps;
    this.nowFn = deps.now ?? (() => Date.now());
  }

  getSnapshot = (): AccessState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  /** Starts the 1 s heartbeat and the visibility listener; safe to call twice. */
  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), 1000);
    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
      const onVisibility = () => this.setVisible(document.visibilityState !== 'hidden');
      document.addEventListener('visibilitychange', onVisibility);
      this.detach = () => document.removeEventListener('visibilitychange', onVisibility);
      this.visible = document.visibilityState !== 'hidden';
    }
    this.tick();
  }

  stop(): void {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    if (this.detach) { this.detach(); this.detach = null; }
  }

  setVisible(visible: boolean): void {
    if (this.visible === visible) return;
    this.visible = visible;
    if (!visible) {
      // A hidden tab may have missed a revocation; nothing is revealed before a new check.
      this.mustReconfirm = true;
      this.publish();
      return;
    }
    this.publish();
    void this.check(true);
  }

  /** Recomputes the derived status without starting a request. */
  refresh(): void { this.publish(); }

  /** Recomputes the derived status and starts a refresh when one is due. */
  tick(): void {
    this.publish();
    if (this.denied || this.checking || !this.visible) return;
    const now = this.nowFn();
    const due = this.mustReconfirm || this.checkedAt === null || now - this.checkedAt >= ACCESS_REFRESH_MS;
    if (due) void this.check(false);
  }

  async check(force: boolean): Promise<AccessState> {
    if (this.pending) return this.pending;
    const now = this.nowFn();
    if (!force && this.lastAttemptAt !== null && now - this.lastAttemptAt < ACCESS_REFRESH_MS) return this.state;
    const startedAt = now;
    this.lastAttemptAt = startedAt;
    this.checking = true;
    this.publish();
    this.pending = (async () => {
      try {
        const me = await this.deps.fetchMe(ACCESS_TIMEOUT_MS);
        this.me = me;
        this.checkedAt = startedAt;
        this.denied = false;
        this.mustReconfirm = false;
        this.lastFailureAt = null;
        this.deps.onConfirmed?.(me);
      } catch (error) {
        if (error instanceof ApiError && error.denied) {
          this.denied = true;
          this.me = null;
          this.checkedAt = null;
          this.deps.onDenied();
        } else {
          this.lastFailureAt = this.nowFn();
        }
      } finally {
        this.checking = false;
        this.pending = null;
        this.publish();
      }
      return this.state;
    })();
    return this.pending;
  }

  /** A denial observed by any other request, not only by the /me heartbeat. */
  reportDenied(): void {
    if (this.denied) return;
    this.denied = true;
    this.me = null;
    this.checkedAt = null;
    this.deps.onDenied();
    this.publish();
  }

  reset(): void {
    this.denied = false;
    this.mustReconfirm = true;
    this.checkedAt = null;
    this.lastAttemptAt = null;
    this.lastFailureAt = null;
    this.publish();
  }

  private derive(): AccessStatus {
    if (this.denied) return 'denied';
    if (this.mustReconfirm) return 'checking';
    if (this.checkedAt === null) return this.checking || this.lastFailureAt === null ? 'checking' : 'offline';
    if (this.nowFn() - this.checkedAt < ACCESS_TTL_MS) return 'confirmed';
    if (this.checking) return 'checking';
    return this.lastFailureAt !== null && this.lastFailureAt > this.checkedAt ? 'offline' : 'stale';
  }

  private publish(): void {
    const status = this.derive();
    // The identity itself stays available while the session lives; only `status` decides
    // whether the view may reveal organisation data.
    const next: AccessState = { status, me: status === 'denied' ? null : this.me, checkedAt: this.checkedAt };
    if (next.status === this.state.status && next.me === this.state.me && next.checkedAt === this.state.checkedAt) return;
    this.state = next;
    for (const listener of this.listeners) listener();
  }
}

const AccessContext = createContext<AccessController | null>(null);

export function AccessProvider({ controller, children }: { controller: AccessController; children: ReactNode }) {
  useEffect(() => {
    controller.start();
    return () => controller.stop();
  }, [controller]);
  return createElement(AccessContext.Provider, { value: controller }, children);
}

const offlineState: AccessState = { status: 'offline', me: null, checkedAt: null };
const noSubscription = () => () => {};

/** `{status, me, checkedAt}`; without a provider the view stays masked. */
export function useAccess(): AccessState {
  const controller = useContext(AccessContext);
  const store = useMemo(() => controller
    ? { subscribe: controller.subscribe, snapshot: controller.getSnapshot }
    : { subscribe: noSubscription, snapshot: () => offlineState },
  [controller]);
  return useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
}

export function useAccessController(): AccessController | null {
  return useContext(AccessContext);
}
