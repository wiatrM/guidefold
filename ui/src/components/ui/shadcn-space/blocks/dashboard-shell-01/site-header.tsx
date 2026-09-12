// Adapted from shadcn-space dashboard-shell-01's site-header.tsx (MIT). Source:
// https://shadcnspace.com/r/dashboard-shell-01.json (qa/spectrum-registry.json carries the
// review hash). Guidefold adaptation (2026-09-12): the demo search box and notification
// bell are dropped (no search index, no notification feed here); the account avatar stays
// in the sidebar footer, not the header, so `within(role=complementary)` still finds the
// "Open profile menu" trigger (app.test.tsx). The header carries the mobile menu trigger
// (text "Menu", not the desktop sr-only "Toggle Sidebar") and the organization/repository
// context that used to live in `.topbar`.
import {useSidebar} from '@/components/ui/sidebar';
import {Button} from '@/components/ui/button';
import {Badge} from '@/components/ui/badge';
import {ListIcon} from '@phosphor-icons/react';

function MobileMenuTrigger() {
  const {toggleSidebar} = useSidebar();
  return <Button type="button" variant="outline" size="sm" className="gap-2 md:hidden" aria-label="Menu" onClick={toggleSidebar}><ListIcon aria-hidden="true" />Menu</Button>;
}

export function SiteHeader({workspace, repo, masked}: {workspace: string; repo: string | null; masked: boolean}) {
  return <div className="flex w-full items-center gap-3">
    <MobileMenuTrigger />
    <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <span>{workspace}</span>
      {!masked && repo && <Badge variant="outline" className="font-mono text-xs"><code>{repo}</code></Badge>}
    </div>
  </div>;
}
