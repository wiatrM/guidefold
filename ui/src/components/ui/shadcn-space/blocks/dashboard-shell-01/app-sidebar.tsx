// Adapted from shadcn-space dashboard-shell-01's app-sidebar.tsx (MIT). Source:
// https://shadcnspace.com/r/dashboard-shell-01.json (qa/spectrum-registry.json carries the
// review hash). Guidefold adaptation (2026-09-12): the demo nav data, "Grab Pro Now" upsell
// card and remote background image are dropped; the brand is Guidefold's own `<BrandMark/>`
// (not the shadcnspace logo asset, which was not carried over); the collapse trigger keeps
// its `aria-label="Collapse sidebar"/"Expand sidebar"` + `aria-expanded` contract
// (app.test.tsx) instead of the default sr-only "Toggle Sidebar"; the account dropdown
// stays inside the sidebar (`SidebarFooter`), not the header, so it is still found within
// `role=complementary`. 2026-09-12 (sidebar restyle, owner: "styles in the post-login menu
// links are terrible, wrong menu styles"): a `SidebarSeparator` hairline now sits above the
// footer account button, matching the pinned-footer layout in the restyle brief.
import type {ReactNode} from 'react';
import {Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarSeparator, useSidebar} from '@/components/ui/sidebar';
import {Button} from '@/components/ui/button';
import {SidebarSimpleIcon} from '@phosphor-icons/react';
import {NavMain, type NavGroup} from './nav-main';

function CollapseTrigger() {
  const {state, toggleSidebar} = useSidebar();
  const collapsed = state === 'collapsed';
  return <Button type="button" variant="ghost" size="icon-sm" className="hidden shrink-0 md:inline-flex" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} onClick={toggleSidebar}><SidebarSimpleIcon aria-hidden="true" /></Button>;
}

// `brand` and `railContext` are the caller's (app.tsx) own product markup — sized and
// spaced by App.module.css, not by this registry block — so this stays presentational.
export function AppSidebar({brand, groups, railContext, account, onNavigate}: {brand: ReactNode; groups: NavGroup[]; railContext: ReactNode; account: ReactNode; onNavigate?: () => void}) {
  return <Sidebar collapsible="icon" role="complementary" aria-label="Guidefold workspace">
    <SidebarHeader className="gap-3 group-data-[collapsible=icon]:items-center">
      <div className="flex items-center justify-between gap-2 group-data-[collapsible=icon]:flex-col">
        <div className="min-w-0 overflow-hidden group-data-[collapsible=icon]:hidden">{brand}</div>
        <CollapseTrigger />
      </div>
      <div className="group-data-[collapsible=icon]:hidden">{railContext}</div>
    </SidebarHeader>
    <SidebarContent className="gap-0 px-2"><nav aria-label="Main navigation"><NavMain groups={groups} onNavigate={onNavigate} /></nav></SidebarContent>
    <SidebarSeparator className="mx-0" />
    <SidebarFooter>{account}</SidebarFooter>
  </Sidebar>;
}
