// Adapted from shadcn-space empty-state-01 (MIT). Source: https://shadcnspace.com/r/empty-state-01.json
// (qa/spectrum-registry.json carries the review hash). Guidefold adaptation (2026-09-12):
// title/description/action are always caller-supplied (no "No projects yet" demo copy),
// EmptyTitle renders as a real <h2> so the block stays an accessible landmark, and a
// `compact` variant drops the entrance animation and outer padding for inline use inside
// an existing Card/Panel.
import type {ReactNode} from 'react';
import {motion} from 'motion/react';
import {ActionButton} from '@/components/ActionButton';
import {Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle} from '@/components/ui/empty';
import {cn} from '@/lib/utils';

export interface EmptyStateAction { label: string; href?: string; onClick?: () => void; tone?: 'system' | 'human' | 'neutral' }

export function EmptyStateBlock({icon, title, description, action, compact = false}: {icon: ReactNode; title: string; description: string; action?: EmptyStateAction; compact?: boolean}) {
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  return <motion.div initial={reduce ? false : {opacity: 0, y: 8}} animate={{opacity: 1, y: 0}} transition={{duration: reduce ? 0 : 0.32, ease: [0.16, 1, 0.3, 1]}} className={cn('w-full', !compact && 'rounded-xl border bg-card p-8 shadow-xs')}>
    <Empty className="gap-4 border-none p-0">
      <EmptyHeader className="gap-3">
        <EmptyMedia variant="icon" className="mb-0 size-11 rounded-xl bg-muted text-muted-foreground [&_svg:not([class*='size-'])]:size-5">{icon}</EmptyMedia>
        <div className="flex w-full flex-col items-center gap-1">
          <EmptyTitle render={<h2 />} className="text-base font-medium text-foreground">{title}</EmptyTitle>
          <EmptyDescription render={<p />} className="max-w-sm text-center">{description}</EmptyDescription>
        </div>
      </EmptyHeader>
      {action && <EmptyContent><ActionButton size="sm" tone={action.tone ?? 'system'} href={action.href} onClick={action.onClick}>{action.label}</ActionButton></EmptyContent>}
    </Empty>
  </motion.div>;
}
