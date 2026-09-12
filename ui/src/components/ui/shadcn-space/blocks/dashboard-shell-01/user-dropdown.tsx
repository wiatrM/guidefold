// Adapted from shadcn-space dashboard-shell-01's user-dropdown.tsx (MIT). Source:
// https://shadcnspace.com/r/dashboard-shell-01.json (qa/spectrum-registry.json carries the
// review hash). Guidefold adaptation (2026-09-12): real session props (name/email/role)
// replace the "David McMichael" demo user and the remote avatar image; the menu keeps only
// the two real actions the account has ("Profile and organization", "Sign out" — no demo
// billing/subscription items) and the trigger keeps its `aria-label="Open profile menu"`
// contract (app.test.tsx, within the sidebar's `role=complementary`).
import {useState} from 'react';
import {Link} from 'react-router-dom';
import {Avatar, AvatarFallback} from '@/components/ui/avatar';
import {DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger} from '@/components/ui/dropdown-menu';
import {UserCircleIcon, SignOutIcon, CaretUpDownIcon} from '@phosphor-icons/react';
import {SidebarMenu, SidebarMenuButton, SidebarMenuItem} from '@/components/ui/sidebar';

export function UserDropdown({name, email, role, profileHref, onLogout}: {name: string; email: string; role: string; profileHref: string; onLogout: () => Promise<void>}) {
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || email.slice(0, 1).toUpperCase();
  const signOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setLogoutError('');
    try { await onLogout(); } catch { setLogoutError('Sign out failed. Try again.'); void import('sonner').then(({toast}) => toast.error('Sign out failed')); setSigningOut(false); }
  };
  return <SidebarMenu>
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger render={<SidebarMenuButton size="lg" aria-label="Open profile menu" />}>
          <Avatar className="size-8 rounded-lg"><AvatarFallback className="rounded-lg">{initials}</AvatarFallback></Avatar>
          <span className="grid min-w-0 flex-1 text-left leading-tight"><strong className="truncate text-sm font-medium">{name}</strong><small className="truncate text-xs text-sidebar-foreground">{role}</small></span>
          <CaretUpDownIcon aria-hidden="true" className="ml-auto size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" sideOffset={8} className="min-w-56 rounded-xl">
          <DropdownMenuGroup><DropdownMenuLabel className="flex items-center gap-2 p-2 font-normal"><Avatar className="size-8 rounded-lg"><AvatarFallback className="rounded-lg">{initials}</AvatarFallback></Avatar><span className="grid"><strong className="text-sm font-medium">{name}</strong><small className="text-xs text-muted-foreground">{email}</small></span></DropdownMenuLabel></DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem render={<Link to={profileHref} />}><UserCircleIcon aria-hidden="true" />Profile and organization</DropdownMenuItem>
            <DropdownMenuItem variant="destructive" disabled={signingOut} onClick={() => { void signOut(); }}><SignOutIcon aria-hidden="true" />{signingOut ? 'Signing out' : 'Sign out'}</DropdownMenuItem>
          </DropdownMenuGroup>
          {logoutError && <p role="status" className="px-2 py-1 text-xs text-destructive">{logoutError}</p>}
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  </SidebarMenu>;
}
