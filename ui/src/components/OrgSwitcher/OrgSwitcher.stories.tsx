import {MemoryRouter} from 'react-router-dom';
import {OrgSwitcher} from './index';
import {orgSwitcherLinks} from '../../domain/orgSwitch';
import type {OrgMembership} from '../../api/decoders';

const meridian: OrgMembership = {org_id: 'o-1', slug: 'meridian', name: 'Meridian Data', role: 'owner'};
const apex: OrgMembership = {org_id: 'o-2', slug: 'apex', name: 'Apex Systems', role: 'member'};
const buildHref = (changes: Record<string, unknown>) => '/library?org=' + changes.org;

function Wrapped({current, orgs}: {current: OrgMembership | null; orgs: OrgMembership[]}) {
  return <MemoryRouter><OrgSwitcher current={current} links={orgSwitcherLinks(orgs, current, buildHref)} createHref="/import?step=organization" /></MemoryRouter>;
}

export default {title: 'Guidefold/OrgSwitcher', component: OrgSwitcher};
// The trigger shows the organisation's name and the user's role in it; opening it (closed here —
// Base UI Menu hangs jsdom, ui/e2e/org-switcher.spec.ts covers the open menu) lists every
// membership with the current one marked, ending in "Create organization".
export const Default = {render: () => <Wrapped current={meridian} orgs={[meridian, apex]} />};
// A single organisation still opens: the trigger and "Create organization" both work.
export const SingleOrganisation = {render: () => <Wrapped current={meridian} orgs={[meridian]} />};
export const NoOrganisation = {render: () => <Wrapped current={null} orgs={[]} />};
