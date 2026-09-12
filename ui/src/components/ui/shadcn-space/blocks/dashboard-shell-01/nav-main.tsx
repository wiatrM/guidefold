// Adapted from shadcn-space dashboard-shell-01's nav-main.tsx (MIT). Source:
// https://shadcnspace.com/r/dashboard-shell-01.json (qa/spectrum-registry.json carries the
// review hash). Guidefold adaptation (2026-09-12): the demo's nested/collapsible sections
// and `next/navigation` active-path detection are dropped — Guidefold's four groups
// (Workspace/Knowledge/Review/Manage, app.tsx `navGroups`) are always flat, and the active
// item is the current `View`, decided by the caller (app.tsx), not by this component.
// 2026-09-12 (sidebar restyle, owner: "styles in the post-login menu links are terrible,
// wrong menu styles"): the group label drops `uppercase tracking-wide` and the full-opacity
// `text-sidebar-foreground` override — both fought the vendored SidebarGroupLabel's own
// sentence-case, reduced-opacity default (see docs sidebar-style-report). The active link
// also carries `aria-current="page"`, which the vendored block never set.
import {Link} from 'react-router-dom';
import {SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem} from '@/components/ui/sidebar';
import type {Icon as PhosphorIcon} from '@phosphor-icons/react';

export interface NavItem { label: string; href: string; icon: PhosphorIcon; active: boolean }
export interface NavGroup { label: string; items: NavItem[] }

export function NavMain({groups, onNavigate}: {groups: NavGroup[]; onNavigate?: () => void}) {
  return <>{groups.map(group => <SidebarGroup key={group.label} className="p-0 pt-4 first:pt-0">
    {/* transition-none: the default fade (200ms) leaves a mid-transition frame right after the
        collapse click where opacity is between 0 and 1 but the label is still in the a11y tree,
        which axe's color-contrast rule catches (e2e/spectrum-migration.spec.ts). An instant
        opacity change removes that window; `group-data-[collapsible=icon]:opacity-0` still hides
        the label once collapsed. */}
    <SidebarGroupLabel className="px-2 text-xs font-medium transition-none">{group.label}</SidebarGroupLabel>
    <SidebarMenu>
      {group.items.map(item => <SidebarMenuItem key={item.href}>
        <SidebarMenuButton isActive={item.active} aria-current={item.active ? 'page' : undefined} tooltip={item.label} onClick={onNavigate} render={<Link to={item.href} />}>
          <item.icon aria-hidden="true" weight={item.active ? 'duotone' : 'regular'} />
          <span>{item.label}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>)}
    </SidebarMenu>
  </SidebarGroup>)}</>;
}
