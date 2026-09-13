import {render, screen} from '@testing-library/react';
import {describe, it, expect} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import {OrgSwitcher} from './index';
import {orgSwitcherLinks} from '../../domain/orgSwitch';
import {SidebarProvider} from '@/components/ui/sidebar';
import type {OrgMembership} from '../../api/decoders';

// Base UI Menu hangs jsdom once opened (docs/ui/pipeline/08-components.md), like the account
// menu below this one in the sidebar (UserDropdown). So this suite renders the trigger CLOSED
// only; opening the menu and choosing an organisation is ui/e2e/org-switcher.spec.ts.
const meridian: OrgMembership = {org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', role: 'owner'};
const apex: OrgMembership = {org_id: 'o-2', slug: 'apex', name: 'Apex Systems', role: 'member'};
const buildHref = (changes: Record<string, unknown>) => '/library?org=' + changes.org;

function renderSwitcher(current: OrgMembership | null, orgs: OrgMembership[]) {
  return render(<MemoryRouter><SidebarProvider>
    <OrgSwitcher current={current} links={orgSwitcherLinks(orgs, current, buildHref)} createHref="/import?step=organization" />
  </SidebarProvider></MemoryRouter>);
}

describe('OrgSwitcher (closed)', () => {
  it('shows the organisation name and role on a focusable, labeled trigger', () => {
    renderSwitcher(meridian, [meridian, apex]);
    const trigger = screen.getByRole('button', {name: 'Switch organization'});
    expect(trigger).toBeInTheDocument();
    expect(trigger).not.toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByText('Meridian Data')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
    // The menu itself is not open in jsdom (Base UI Menu hangs once opened): only the trigger renders.
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(screen.queryByText('Apex Systems')).not.toBeInTheDocument();
  });
  it('falls back to the slug when the organisation has no name', () => {
    const noName = {...meridian, name: ''};
    renderSwitcher(noName, [noName]);
    expect(screen.getByText('meridian')).toBeInTheDocument();
  });
  it('still renders an open-able trigger with a single organisation', () => {
    renderSwitcher(meridian, [meridian]);
    expect(screen.getByRole('button', {name: 'Switch organization'})).toBeInTheDocument();
    expect(screen.getByText('Meridian Data')).toBeInTheDocument();
  });
  it('shows "No organization" with no current membership', () => {
    renderSwitcher(null, []);
    expect(screen.getByText('No organization')).toBeInTheDocument();
    expect(screen.queryByText('Owner')).not.toBeInTheDocument();
    expect(screen.queryByText('Member')).not.toBeInTheDocument();
  });
});
