// Adapted from shadcn-space statistics-01 (MIT). Source: https://shadcnspace.com/r/statistics-01.json
// (qa/spectrum-registry.json carries the review hash). Guidefold adaptation (2026-09-12):
// real data props replace the demo "Earnings/Expense" content; the decorative background
// image is dropped; a trend renders "No previous window" in muted style, never a fake
// percentage, until usage.previous exists (contract 1.3.0, Task 8). Each metric's label and
// value are a real <dl><div><dt>/<dd></div></dl> pair (axe `definition-list`/`dlitem`: a
// <dl> may directly contain only <dt>/<dd>, so the trend badge and caption sit outside it,
// not interleaved inside) — `[data-slot=statistic] dd` (and plain `dd`) stay a stable,
// testable hook (HomeRoute.test.tsx).
import type {ReactNode} from 'react';
import {Badge} from '@/components/ui/badge';
import {Card, CardContent} from '@/components/ui/card';
import {Separator} from '@/components/ui/separator';
import type {LucideIcon} from 'lucide-react';
import {cn} from '@/lib/utils';

export interface StatTrend { label: string; positive: boolean }
export interface MainMetric { label: string; value: string; caption?: string; trend: StatTrend | null }
export interface StatItem { title: string; value: string; caption?: string; icon: LucideIcon; tone: 'system' | 'human' | 'warning' | 'neutral'; trend: StatTrend | null }

const toneClass: Record<StatItem['tone'], string> = {
  system: 'bg-chart-2/15 text-chart-2',
  human: 'bg-chart-3/15 text-chart-3',
  warning: 'bg-chart-5/15 text-chart-5',
  neutral: 'bg-muted text-muted-foreground',
};

function TrendBadge({trend}: {trend: StatTrend | null}) {
  if (!trend) return <Badge variant="outline" className="font-normal text-muted-foreground">No previous window</Badge>;
  return <Badge className={cn('font-normal', trend.positive ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500')}>{trend.label}</Badge>;
}

function Metric({label, value, caption}: {label: string; value: string; caption?: string}) {
  return <dl className="m-0"><div><dt className="text-xs font-normal text-muted-foreground">{label}</dt><dd className="m-0 text-2xl font-medium text-card-foreground" data-slot="statistic">{value}</dd></div></dl>;
}

export function StatisticsMain({title, description, metrics, link}: {title: ReactNode; description: string; metrics: [MainMetric, MainMetric]; link?: ReactNode}) {
  return <Card className="h-full rounded-xl border py-0 shadow-xs">
    <CardContent className="flex h-full flex-col justify-between gap-6 p-6">
      <div>
        <p className="text-lg font-medium text-card-foreground">{title}</p>
        <p className="text-xs font-normal text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-wrap gap-6">
        {metrics.map((metric, index) => <div key={metric.label} className="flex items-center gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Metric label={metric.label} value={metric.value} />
              <TrendBadge trend={metric.trend} />
            </div>
            {metric.caption && <p className="m-0 text-xs text-muted-foreground">{metric.caption}</p>}
          </div>
          {index === 0 && <Separator orientation="vertical" className="hidden h-12 sm:block" />}
        </div>)}
      </div>
      {link}
    </CardContent>
  </Card>;
}

export function StatisticsSecondary({title, value, caption, icon: Icon, tone, trend, link}: StatItem & {link?: ReactNode}) {
  return <Card className="rounded-xl border p-6 shadow-xs">
    <CardContent className="flex items-start justify-between gap-3 p-0">
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <Metric label={title} value={value} />
            <TrendBadge trend={trend} />
          </div>
          {caption && <p className="m-0 text-xs text-muted-foreground">{caption}</p>}
        </div>
        {link}
      </div>
      <div className={cn('rounded-full p-3', toneClass[tone])}><Icon size={20} aria-hidden="true" /></div>
    </CardContent>
  </Card>;
}
