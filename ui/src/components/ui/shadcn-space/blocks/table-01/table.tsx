// Adapted from shadcn-space table-01 (MIT). Source: https://shadcnspace.com/r/table-01.json
// (qa/spectrum-registry.json carries the review hash). Guidefold adaptation (2026-09-12):
// real skill rows (skill, recommendation, the four gates, an optional pull-share progress
// bar) replace the demo project list; no checkbox column, no per-row dropdown menu (nothing
// here is actionable from this table) and no avatar images. The Card chrome moved to the
// caller (HomeRoute) so the table itself stays a plain accessible region.
import {Link} from 'react-router-dom';
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from '@/components/ui/table';
import {Progress} from '@/components/ui/progress';
import {Badge} from '@/components/ui/badge';
import {cn} from '@/lib/utils';

const badgeTone: Record<string, string> = {
  system: 'bg-emerald-500/10 text-emerald-500',
  warning: 'bg-amber-500/10 text-amber-500',
  neutral: 'bg-muted text-muted-foreground',
};

export function GateBadge({label, tone}: {label: string; tone: 'system' | 'warning' | 'neutral'}) {
  return <Badge className={cn('font-normal', badgeTone[tone])}>{label}</Badge>;
}

export interface SkillRow {
  skillId: string; skillName: string; scope: string; href: string;
  recommendation: {label: string; tone: 'system' | 'warning' | 'neutral'};
  reach: {label: string; tone: 'system' | 'warning' | 'neutral'};
  pull: {label: string; tone: 'system' | 'warning' | 'neutral'}; pullShare: number | null;
  value: {label: string; tone: 'system' | 'warning' | 'neutral'};
  health: {label: string; tone: 'system' | 'warning' | 'neutral'};
}

export function SkillsTable({label, rows}: {label: string; rows: SkillRow[]}) {
  return <div role="region" aria-label={label} className="overflow-x-auto">
    <Table className="min-w-2xl">
      <TableHeader>
        <TableRow className="hover:bg-transparent!">
          <TableHead className="ps-6">Skill</TableHead>
          <TableHead>Recommendation</TableHead>
          <TableHead>Reach</TableHead>
          <TableHead>Pull</TableHead>
          <TableHead>Value</TableHead>
          <TableHead className="pe-6">Health</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(row => <TableRow key={row.skillId}>
          <TableCell className="ps-6">
            <Link to={row.href} className="text-sm font-medium underline-offset-4 hover:underline">{row.skillName}</Link>
            <p className="text-xs text-muted-foreground">{row.scope}</p>
          </TableCell>
          <TableCell><GateBadge {...row.recommendation} /></TableCell>
          <TableCell><GateBadge {...row.reach} /></TableCell>
          <TableCell>
            <div className="flex items-center gap-2">
              <GateBadge {...row.pull} />
              {row.pullShare !== null && <Progress value={row.pullShare} className="w-16" aria-label="Pull share" />}
            </div>
          </TableCell>
          <TableCell><GateBadge {...row.value} /></TableCell>
          <TableCell className="pe-6"><GateBadge {...row.health} /></TableCell>
        </TableRow>)}
      </TableBody>
    </Table>
  </div>;
}
