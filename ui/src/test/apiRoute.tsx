/** Renders one hosted API route with an explicit context. No production module imports this file. */
import { vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ComponentType } from 'react';
import type { AccessStatus } from '../api/access';
import type { Me } from '../api/decoders';
import type { DataSource } from '../data/source';
import type { ApiRouteContext, View } from '../domain';

export const me: Me = {
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada' },
  identities: [],
  orgs: [{ org_id: 'o1', slug: 'meridian', name: 'Meridian', role: 'owner' }],
  csrf_token: 'csrf-1',
  access: { checked_at: null, valid_for_s: 45 },
  link_suggestions: [],
};

export function apiContext(source: DataSource, search = '', over: Partial<ApiRouteContext> = {}): ApiRouteContext {
  const params = new URLSearchParams(search);
  return {
    source,
    access: { status: (over.access?.status ?? 'confirmed') as AccessStatus, me, checkedAt: 1 },
    me, org: 'meridian', repo: 'monorepo', role: 'owner', params,
    view: (over.view ?? 'library') as View,
    href: (view, changes = {}) => '/' + view + '?' + new URLSearchParams(
      Object.entries(changes).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, String(value)]),
    ).toString(),
    go: vi.fn(),
    ...over,
  };
}

export function renderApi(
  Component: ComponentType<{ ctx: ApiRouteContext }>,
  source: DataSource,
  search = '',
  over: Partial<ApiRouteContext> = {},
) {
  const ctx = apiContext(source, search, over);
  return { ctx, ...render(<MemoryRouter><Component ctx={ctx} /></MemoryRouter>) };
}
