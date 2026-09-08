import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ACCESS_REFRESH_MS, ACCESS_TIMEOUT_MS, ACCESS_TTL_MS, AccessController, revealsData } from './access';
import { ApiError } from './client';
import type { Me } from './decoders';

const identity: Me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [], orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' }],
  csrf_token: 'csrf-1', access: { checked_at: null, valid_for_s: 45 }, link_suggestions: [],
};

function setup(fetchMe: (timeoutMs: number) => Promise<Me>) {
  let clock = 1_000_000;
  const onDenied = vi.fn();
  const onConfirmed = vi.fn();
  const controller = new AccessController({ fetchMe, onDenied, onConfirmed, now: () => clock });
  return { controller, onDenied, onConfirmed, advance: (ms: number) => { clock += ms; }, at: () => clock };
}

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });

describe('access confirmation', () => {
  test('starts unconfirmed, then confirms and records the request start', async () => {
    const { controller, at, onConfirmed } = setup(async () => identity);
    expect(controller.getSnapshot().status).toBe('checking');
    expect(revealsData(controller.getSnapshot().status)).toBe(false);
    const start = at();
    await controller.check(true);
    expect(controller.getSnapshot()).toMatchObject({ status: 'confirmed', checkedAt: start });
    expect(onConfirmed).toHaveBeenCalledWith(identity);
  });

  test('/me is asked with a 5 s timeout and not more often than every 25 s', async () => {
    const timeouts: number[] = [];
    const { controller, advance } = setup(async timeoutMs => { timeouts.push(timeoutMs); return identity; });
    await controller.check(true);
    advance(ACCESS_REFRESH_MS - 1000);
    await controller.check(false);
    expect(timeouts).toEqual([ACCESS_TIMEOUT_MS]);
    advance(2000);
    await controller.check(false);
    expect(timeouts).toEqual([ACCESS_TIMEOUT_MS, ACCESS_TIMEOUT_MS]);
  });

  test('data older than 45 s is masked until a check succeeds again', async () => {
    const { controller, advance } = setup(async () => identity);
    await controller.check(true);
    advance(ACCESS_TTL_MS - 1);
    controller.refresh();
    expect(controller.getSnapshot().status).toBe('confirmed');
    advance(2);
    controller.refresh();
    expect(controller.getSnapshot().status).toBe('stale');
    expect(revealsData(controller.getSnapshot().status)).toBe(false);
    await controller.check(true);
    expect(controller.getSnapshot().status).toBe('confirmed');
  });

  test('a network failure keeps the session but stops revealing data once it is stale', async () => {
    let fail = false;
    const { controller, advance, onDenied } = setup(async () => { if (fail) throw new ApiError({ status: 0, code: 'timeout', message: 'no answer' }); return identity; });
    await controller.check(true);
    fail = true;
    advance(ACCESS_TTL_MS + 1);
    await controller.check(true);
    expect(controller.getSnapshot().status).toBe('offline');
    expect(controller.getSnapshot().me).not.toBeNull();
    expect(onDenied).not.toHaveBeenCalled();
  });

  test('a hidden tab is reconfirmed before anything is revealed', async () => {
    const { controller } = setup(async () => identity);
    await controller.check(true);
    expect(controller.getSnapshot().status).toBe('confirmed');
    controller.setVisible(false);
    expect(controller.getSnapshot().status).toBe('checking');
    expect(revealsData(controller.getSnapshot().status)).toBe(false);
    controller.setVisible(true);
    await controller.check(true);
    expect(controller.getSnapshot().status).toBe('confirmed');
  });

  test('401 clears the session, calls the revocation hook and stays denied', async () => {
    const { controller, onDenied } = setup(async () => { throw new ApiError({ status: 401, code: 'unauthenticated', message: 'no session' }); });
    await controller.check(true);
    expect(onDenied).toHaveBeenCalledTimes(1);
    expect(controller.getSnapshot()).toMatchObject({ status: 'denied', me: null, checkedAt: null });
  });

  test('403 observed elsewhere denies once, not once per report', async () => {
    const { controller, onDenied } = setup(async () => identity);
    await controller.check(true);
    controller.reportDenied();
    controller.reportDenied();
    expect(onDenied).toHaveBeenCalledTimes(1);
    expect(controller.getSnapshot().status).toBe('denied');
  });

  test('subscribers are notified when the derived status changes', async () => {
    const { controller, advance } = setup(async () => identity);
    const listener = vi.fn();
    const stop = controller.subscribe(listener);
    await controller.check(true);
    const seen = listener.mock.calls.length;
    advance(ACCESS_TTL_MS + 1);
    controller.refresh();
    expect(listener.mock.calls.length).toBeGreaterThan(seen);
    stop();
  });
});
