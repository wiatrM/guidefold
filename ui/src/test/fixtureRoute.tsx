/** Renders one fixture-mode route with an explicit context. No production module imports this file.
 *
 * Mirrors apiRoute.tsx's renderApi/apiContext, but for the six routes that read the public
 * Meridian fixture (`ctx.data`) instead of the hosted API (`ctx.source`). No existing test file
 * covered this composition before: LibraryRoute.test.tsx, SkillRoute.test.tsx, MapRoute.test.tsx,
 * UsageRoute.test.tsx and ProposalsRoute.test.tsx all exercise the Api* variant only.
 */
import { vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ComponentType } from 'react';
import { meridian } from '../data/meridian';
import { fakeSource } from './fakes';
import type { DataState, Params, RouteContext, Session, View } from '../domain';

export function fixtureContext(search = '', over: Partial<RouteContext> = {}): RouteContext {
  const params = new URLSearchParams(search);
  const href = (target: View, changes: Params = {}) => {
    const next = new URLSearchParams(search);
    Object.entries(changes).forEach(([key, value]) => (value === null || value === undefined) ? next.delete(key) : next.set(key, String(value)));
    const query = next.toString();
    return '/' + target + (query ? '?' + query : '');
  };
  return {
    data: meridian,
    source: fakeSource(),
    mode: 'fixture',
    params,
    state: 'ready' as DataState,
    view: 'library' as View,
    member: false,
    canWrite: true,
    canFeedback: true,
    memory: {} as Session,
    save: vi.fn(),
    href,
    go: vi.fn(),
    ...over,
  };
}

export function renderFixture(
  Component: ComponentType<{ ctx: RouteContext }>,
  search = '',
  over: Partial<RouteContext> = {},
) {
  const ctx = fixtureContext(search, over);
  return { ctx, ...render(<MemoryRouter><Component ctx={ctx} /></MemoryRouter>) };
}
