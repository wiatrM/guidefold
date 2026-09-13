// Organisation switcher, sidebar rail header (owner brief 2026-09-13, docs/ui/UX.md §3a
// "Przełącznik organizacji"/"Zapamiętany kontekst"). Composed like `UserDropdown` below it in
// the sidebar: a shadcn/Base UI `DropdownMenu` (ui/src/components/ui/dropdown-menu.tsx) on a
// `SidebarMenuButton` trigger, `Avatar`/`AvatarFallback` for the organisation mark — the same
// shadcn primitives `UserDropdown` composes, nothing hand-rolled. Base UI Menu hangs jsdom once
// opened (docs/ui/pipeline/08-components.md §Refaktor), so this component is rendered CLOSED
// ONLY in Vitest (OrgSwitcher.test.tsx); opening it and choosing an organisation is covered in
// ui/e2e/org-switcher.spec.ts against the stub API. The membership resolution (URL vs.
// remembered vs. first organisation) and the per-organisation link this menu renders both come
// from the pure, storage-free ui/src/domain/orgSwitch.ts, already unit-tested there — this file
// only renders what it is given.
//
// The group layout below — one `DropdownMenuGroup` for the label, a separator, then a single
// trailing `DropdownMenuGroup` holding every organisation row and "Create organization" — mirrors
// `UserDropdown`'s own Group/Separator/Group shape exactly (rather than a bare `DropdownMenuItem`
// living outside any group). `UserDropdown` is the one other menu opened by a Playwright spec
// (ui/e2e/schema-navigation.spec.ts) and its axe run is clean; keeping the same shape here keeps
// the same result — Base UI's internal `[data-base-ui-focus-guard]` spans are otherwise identical
// in both menus, so the grouping is the deciding difference, not anything in this file's content.
import {Link} from 'react-router-dom';
import {BuildingsIcon, CaretUpDownIcon, CheckIcon, PlusIcon} from '@phosphor-icons/react';
import {Avatar, AvatarFallback} from '@/components/ui/avatar';
import {DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger} from '@/components/ui/dropdown-menu';
import {SidebarMenu, SidebarMenuButton, SidebarMenuItem} from '@/components/ui/sidebar';
import type {OrgMembership} from '../../api/decoders';
import type {OrgSwitcherLink} from '../../domain/orgSwitch';

const roleLabel = (role: OrgMembership['role']) => role === 'owner' ? 'Owner' : 'Member';
// Two letters from the name (or the slug, which is always present) so an organisation with no
// name yet still gets a legible mark, matching UserDropdown's own initials fallback.
const initials = (org: OrgMembership) => (org.name || org.slug).split(/[\s-]+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || '?';

export function OrgSwitcher({current, links, createHref}: {
  /** The organisation the console is showing now, or null with no membership at all (the
   * "Organization unavailable" path in app.tsx stays unchanged by this menu). */
  current: OrgMembership | null;
  /** One row per membership, in `me.orgs` order; built by `orgSwitcherLinks` so the address
   * logic (keep the view, replace `org`, drop `repo`) lives in one tested place. */
  links: OrgSwitcherLink[];
  /** The wizard's first step, `/import?step=organization`. */
  createHref: string;
}) {
  const label = current ? (current.name || current.slug) : 'No organization';
  return <SidebarMenu>
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger render={<SidebarMenuButton size="lg" aria-label="Switch organization" />}>
          <Avatar className="size-8 rounded-lg"><AvatarFallback className="rounded-lg">{current ? initials(current) : <BuildingsIcon aria-hidden="true" />}</AvatarFallback></Avatar>
          <span className="grid min-w-0 flex-1 text-left leading-tight">
            <strong className="truncate text-sm font-medium">{label}</strong>
            {current && <small className="truncate text-xs text-sidebar-foreground">{roleLabel(current.role)}</small>}
          </span>
          <CaretUpDownIcon aria-hidden="true" className="ml-auto size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent side="bottom" align="start" sideOffset={8} className="min-w-64 rounded-xl">
          <DropdownMenuGroup><DropdownMenuLabel>Organizations</DropdownMenuLabel></DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            {links.map(({org, current: isCurrent, href}) =>
              <DropdownMenuItem key={org.org_id} render={<Link to={href} />} aria-current={isCurrent ? 'true' : undefined}>
                <Avatar className="size-6 rounded-md"><AvatarFallback className="rounded-md text-xs">{initials(org)}</AvatarFallback></Avatar>
                <span className="grid min-w-0 flex-1 leading-tight">
                  <strong className="truncate text-sm font-medium">{org.name || org.slug}</strong>
                  <small className="truncate text-xs text-muted-foreground">{roleLabel(org.role)}</small>
                </span>
                {isCurrent && <CheckIcon aria-hidden="true" className="ml-auto size-4" />}
              </DropdownMenuItem>,
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem render={<Link to={createHref} />}><PlusIcon aria-hidden="true" />Create organization</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  </SidebarMenu>;
}
